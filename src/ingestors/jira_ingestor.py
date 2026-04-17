from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.db.models import JiraTicket
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class JiraIngestor:
    def __init__(self, url: str, email: str, api_token: str):
        self.url = url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    async def fetch_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a single Jira issue."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching Jira issue {issue_key}")
                response = await client.get(
                    f"{self.url}/rest/api/3/issue/{issue_key}",
                    auth=self.auth,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Jira {issue_key}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching Jira {issue_key}: {e}")
            raise

    async def search_issues(self, jql: str, max_results: int = 100) -> list[dict[str, Any]]:
        """Search Jira issues using JQL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Searching Jira with JQL: {jql}")
                response = await client.post(
                    f"{self.url}/rest/api/3/search",
                    auth=self.auth,
                    headers=self.headers,
                    json={"jql": jql, "maxResults": max_results, "fields": ["*all"]},
                )
                response.raise_for_status()
                data = response.json()
                issues = data.get("issues", [])
                logger.info(f"Found {len(issues)} Jira issues")
                return issues
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching Jira: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error searching Jira: {e}")
            raise

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
        """Ingest multiple Jira issues by their keys."""
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
