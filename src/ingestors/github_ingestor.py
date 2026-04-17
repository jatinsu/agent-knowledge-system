import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.db.models import Repository, PullRequest
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class GitHubIngestor:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def fetch_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Fetch repository information from GitHub API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching repository {owner}/{repo}")
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}", headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching repo {owner}/{repo}: {e.response.status_code}")
            raise
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching repo {owner}/{repo}")
            raise
        except Exception as e:
            logger.error(f"Error fetching repo {owner}/{repo}: {e}")
            raise

    async def fetch_pull_requests(
        self, owner: str, repo: str, state: str = "all", limit: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch pull requests from GitHub API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching PRs for {owner}/{repo} (limit={limit})")
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls",
                    headers=self.headers,
                    params={"state": state, "per_page": min(limit, 100), "sort": "updated", "direction": "desc"},
                )
                response.raise_for_status()
                prs = response.json()
                logger.info(f"Fetched {len(prs)} PRs from {owner}/{repo}")
                return prs
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching PRs: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching PRs: {e}")
            raise

    async def fetch_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch files changed in a pull request."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching PR #{pr_number} files: {e.response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Error fetching PR #{pr_number} files: {e}")
            return []

    def extract_jira_keys(self, text: str | None) -> list[str]:
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
