from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from src.db.models import JiraTicket
from src.ingestors.mcp_client import MCPClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

JIRA_MCP_COMMAND = "npx"
JIRA_MCP_ARGS = ["-y", "@aashari/mcp-server-atlassian-jira"]


class JiraIngestor:
    def __init__(self, url: str, email: str, api_token: str):
        self.url = url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self._client: MCPClient | None = None

    def _site_name(self) -> str:
        """Extract Atlassian site name from URL (e.g. 'myteam' from 'https://myteam.atlassian.net')."""
        hostname = urlparse(self.url).hostname or ""
        return hostname.split(".")[0]

    async def __aenter__(self) -> "JiraIngestor":
        self._client = MCPClient(
            command=JIRA_MCP_COMMAND,
            args=JIRA_MCP_ARGS,
            env={
                "ATLASSIAN_SITE_NAME": self._site_name(),
                "ATLASSIAN_USER_EMAIL": self.email,
                "ATLASSIAN_API_TOKEN": self.api_token,
            },
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.__aexit__(*exc)
        self._client = None

    async def fetch_issue(self, issue_key: str) -> dict[str, Any]:
        logger.info(f"Fetching Jira issue {issue_key}")
        try:
            return await self._client.call_tool(
                "jira_get",
                {
                    "path": f"/rest/api/3/issue/{issue_key}",
                    "outputFormat": "json",
                },
            )
        except Exception as e:
            logger.warning(f"MCP jira_get failed, falling back to httpx: {e}")
            return await self._fetch_issue_httpx(issue_key)

    async def _fetch_issue_httpx(self, issue_key: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.url}/rest/api/3/issue/{issue_key}",
                auth=(self.email, self.api_token),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def search_issues(
        self, jql: str, max_results: int = 100
    ) -> list[dict[str, Any]]:
        logger.info(f"Searching Jira with JQL: {jql}")
        try:
            result = await self._client.call_tool(
                "jira_get",
                {
                    "path": "/rest/api/3/search/jql",
                    "queryParams": {"jql": jql, "maxResults": str(max_results), "fields": "*all"},
                    "outputFormat": "json",
                },
            )
            if isinstance(result, dict):
                issues = result.get("issues", [])
            elif isinstance(result, list):
                issues = result
            else:
                raise ValueError(f"Unexpected response type: {type(result)}")
        except Exception as e:
            logger.warning(f"MCP jira_get search failed, falling back to httpx: {e}")
            issues = await self._search_issues_httpx(jql, max_results)
        logger.info(f"Found {len(issues)} Jira issues")
        return issues

    async def _search_issues_httpx(
        self, jql: str, max_results: int
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.url}/rest/api/3/search/jql",
                auth=(self.email, self.api_token),
                headers={"Accept": "application/json"},
                params={"jql": jql, "maxResults": max_results, "fields": "*all"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("issues", [])

    def normalize_ticket(self, data: dict[str, Any], db: Session) -> JiraTicket:
        fields = data["fields"]

        ticket = db.query(JiraTicket).filter(JiraTicket.key == data["key"]).first()

        epic_link = fields.get("customfield_10014") or fields.get("parent", {}).get("key")

        if not ticket:
            ticket = JiraTicket(
                key=data["key"],
                summary=fields["summary"],
                description=fields.get("description", {}).get("content", [{}])[0]
                .get("content", [{}])[0]
                .get("text")
                if isinstance(fields.get("description"), dict)
                else fields.get("description"),
                ticket_type=fields["issuetype"]["name"],
                status=fields["status"]["name"],
                priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
                assignee=(
                    fields["assignee"]["displayName"] if fields.get("assignee") else None
                ),
                reporter=fields["reporter"]["displayName"],
                created_at=datetime.fromisoformat(fields["created"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(fields["updated"].replace("Z", "+00:00")),
                epic_key=epic_link,
            )
            db.add(ticket)
        else:
            ticket.summary = fields["summary"]
            ticket.status = fields["status"]["name"]
            ticket.updated_at = datetime.fromisoformat(fields["updated"].replace("Z", "+00:00"))

        db.commit()
        db.refresh(ticket)
        return ticket

    async def ingest_issue(self, issue_key: str, db: Session) -> JiraTicket:
        issue_data = await self.fetch_issue(issue_key)
        return self.normalize_ticket(issue_data, db)

    async def ingest_issues_by_jql(
        self, jql: str, db: Session, max_results: int = 100
    ) -> list[JiraTicket]:
        issues_data = await self.search_issues(jql, max_results)

        tickets = []
        for issue_data in issues_data:
            ticket = self.normalize_ticket(issue_data, db)
            tickets.append(ticket)

        return tickets

    async def ingest_issues_by_keys(
        self, issue_keys: list[str], db: Session
    ) -> list[JiraTicket]:
        tickets = []
        for key in issue_keys:
            try:
                ticket = await self.ingest_issue(key, db)
                tickets.append(ticket)
            except Exception as e:
                logger.warning(f"Failed to ingest Jira issue {key}: {e}")
                continue

        logger.info(f"Ingested {len(tickets)}/{len(issue_keys)} Jira tickets")
        return tickets
