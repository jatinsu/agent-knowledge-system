import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.db.models import Repository, PullRequest
from src.ingestors.mcp_client import MCPClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

GITHUB_MCP_COMMAND = "npx"
GITHUB_MCP_ARGS = ["-y", "@modelcontextprotocol/server-github"]


class GitHubIngestor:
    def __init__(self, token: str):
        self.token = token
        self._client: MCPClient | None = None

    async def __aenter__(self) -> "GitHubIngestor":
        self._client = MCPClient(
            command=GITHUB_MCP_COMMAND,
            args=GITHUB_MCP_ARGS,
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": self.token},
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.__aexit__(*exc)
        self._client = None

    async def fetch_repository(self, owner: str, repo: str) -> dict[str, Any]:
        logger.info(f"Fetching repository {owner}/{repo}")
        try:
            return await self._client.call_tool(
                "get_repository", {"owner": owner, "repo": repo}
            )
        except Exception:
            logger.info("get_repository tool not available, using constructed data")
            return {
                "name": repo,
                "owner": {"login": owner},
                "html_url": f"https://github.com/{owner}/{repo}",
                "default_branch": "main",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

    async def fetch_pull_requests(
        self, owner: str, repo: str, state: str = "all", limit: int = 100
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching PRs for {owner}/{repo} (limit={limit})")
        try:
            result = await self._client.call_tool(
                "list_pull_requests",
                {
                    "owner": owner,
                    "repo": repo,
                    "state": state,
                    "per_page": min(limit, 100),
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            prs = result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"MCP list_pull_requests failed, falling back to httpx: {e}")
            prs = await self._fetch_pull_requests_httpx(owner, repo, state, limit)
        logger.info(f"Fetched {len(prs)} PRs from {owner}/{repo}")
        return prs

    async def _fetch_pull_requests_httpx(
        self, owner: str, repo: str, state: str, limit: int
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                },
                params={
                    "state": state,
                    "per_page": min(limit, 100),
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            response.raise_for_status()
            return response.json()

    async def fetch_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        try:
            result = await self._client.call_tool(
                "get_pull_request_files",
                {"owner": owner, "repo": repo, "pull_number": pr_number},
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"MCP get_pull_request_files failed for PR #{pr_number}, falling back to httpx: {e}")
            return await self._fetch_pr_files_httpx(owner, repo, pr_number)

    async def _fetch_pr_files_httpx(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"httpx fallback also failed for PR #{pr_number} files: {e}")
            return []

    @staticmethod
    def extract_jira_keys(text: str | None) -> list[str]:
        if not text:
            return []
        pattern = r"\b[A-Z]{2,}-\d+\b"
        return list(set(re.findall(pattern, text)))

    def normalize_repository(self, data: dict[str, Any], db: Session) -> Repository:
        repo = (
            db.query(Repository)
            .filter(Repository.owner == data["owner"]["login"], Repository.name == data["name"])
            .first()
        )

        if not repo:
            repo = Repository(
                name=data["name"],
                owner=data["owner"]["login"],
                url=data["html_url"],
                default_branch=data.get("default_branch", "main"),
                created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

        return repo

    async def normalize_pull_request(
        self, pr_data: dict[str, Any], repo: Repository, db: Session
    ) -> PullRequest:
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.repo_id == repo.id, PullRequest.pr_number == pr_data["number"])
            .first()
        )

        files = await self.fetch_pr_files(repo.owner, repo.name, pr_data["number"])
        files_changed = ",".join([f["filename"] for f in files])

        jira_keys_from_title = self.extract_jira_keys(pr_data.get("title"))
        jira_keys_from_body = self.extract_jira_keys(pr_data.get("body"))
        jira_keys = list(set(jira_keys_from_title + jira_keys_from_body))

        if not pr:
            pr = PullRequest(
                repo_id=repo.id,
                pr_number=pr_data["number"],
                title=pr_data["title"],
                description=pr_data.get("body"),
                author=pr_data["user"]["login"],
                state=pr_data["state"],
                base_branch=pr_data["base"]["ref"],
                head_branch=pr_data["head"]["ref"],
                created_at=datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00")),
                merged_at=(
                    datetime.fromisoformat(pr_data["merged_at"].replace("Z", "+00:00"))
                    if pr_data.get("merged_at")
                    else None
                ),
                files_changed=files_changed,
                jira_keys=",".join(jira_keys) if jira_keys else None,
            )
            db.add(pr)
        else:
            pr.state = pr_data["state"]
            pr.files_changed = files_changed
            pr.jira_keys = ",".join(jira_keys) if jira_keys else None

        db.commit()
        db.refresh(pr)
        return pr

    async def ingest_repository(self, owner: str, repo: str, db: Session) -> Repository:
        repo_data = await self.fetch_repository(owner, repo)
        return self.normalize_repository(repo_data, db)

    async def ingest_pull_requests(
        self, owner: str, repo: str, db: Session, limit: int = 100
    ) -> list[PullRequest]:
        repository = await self.ingest_repository(owner, repo, db)
        prs_data = await self.fetch_pull_requests(owner, repo, limit=limit)

        prs = []
        for pr_data in prs_data:
            pr = await self.normalize_pull_request(pr_data, repository, db)
            prs.append(pr)

        return prs
