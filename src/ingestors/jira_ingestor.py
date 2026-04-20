from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.db.models import PullRequest, JiraProject, JiraEpic, JiraStory, JiraTask
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

JIRA_TABLE_MAP = {
    "epic": JiraEpic,
    "story": JiraStory,
    "task": JiraTask,
}


class JiraIngestor:
    def __init__(self, url: str, email: str, api_token: str):
        self.url = url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    async def fetch_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a single Jira issue."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching Jira issue {issue_key}")
            response = await client.get(
                f"{self.url}/rest/api/3/issue/{issue_key}",
                auth=self.auth,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_project(self, project_key: str) -> dict[str, Any]:
        """Fetch Jira project details."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching Jira project {project_key}")
            response = await client.get(
                f"{self.url}/rest/api/3/project/{project_key}",
                auth=self.auth,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    def _extract_project_key(self, issue_key: str) -> str:
        """Extract project key from issue key (e.g. 'OCPBUGS-123' -> 'OCPBUGS')."""
        return issue_key.rsplit("-", 1)[0]

    def _extract_description_text(self, description: Any) -> str | None:
        """Extract plain text from Jira API v3 ADF description or plain string."""
        if description is None:
            return None
        if isinstance(description, str):
            return description
        if isinstance(description, dict):
            try:
                return description["content"][0]["content"][0]["text"]
            except (KeyError, IndexError, TypeError):
                return None
        return None

    def _upsert_project(self, project_key: str, project_data: dict[str, Any], db: Session) -> JiraProject:
        """Insert or update a Jira project record."""
        project = db.get(JiraProject, project_key)
        if not project:
            project = JiraProject(
                id=project_key,
                title=project_data.get("name", project_key),
                description=project_data.get("description"),
                date=datetime.now(timezone.utc),
            )
            db.add(project)
        else:
            project.title = project_data.get("name", project_key)
            project.description = project_data.get("description")
        return project

    def _upsert_issue(self, issue_key: str, issue_data: dict[str, Any], issue_type: str, db: Session) -> JiraEpic | JiraStory | JiraTask:
        """Insert or update a Jira issue into the appropriate type table."""
        model_class = JIRA_TABLE_MAP.get(issue_type)
        if not model_class:
            raise ValueError(f"Unknown issue type: {issue_type}")

        fields = issue_data.get("fields", {})
        title = fields.get("summary", "")
        description = self._extract_description_text(fields.get("description"))

        record = db.get(model_class, issue_key)
        if not record:
            record = model_class(
                id=issue_key,
                title=title,
                description=description,
            )
            db.add(record)
        else:
            record.title = title
            record.description = description

        return record

    def _collect_jira_keys_from_prs(self, db: Session) -> dict[str, set[str]]:
        """Query PR_TBL for all non-null jira keys, grouped by type."""
        keys_by_type: dict[str, set[str]] = {
            "epic": set(),
            "story": set(),
            "task": set(),
        }

        prs = db.query(PullRequest).filter(
            (PullRequest.epic_key.isnot(None))
            | (PullRequest.story_key.isnot(None))
            | (PullRequest.task_key.isnot(None))
        ).all()

        for pr in prs:
            if pr.epic_key:
                keys_by_type["epic"].add(pr.epic_key)
            if pr.story_key:
                keys_by_type["story"].add(pr.story_key)
            if pr.task_key:
                keys_by_type["task"].add(pr.task_key)

        return keys_by_type

    async def ingest_from_prs(self, db: Session) -> dict[str, int]:
        """Main entry point: query PR table for jira keys, fetch from Jira, populate JIRA_DB tables.

        Returns a summary dict with counts per type.
        """
        keys_by_type = self._collect_jira_keys_from_prs(db)

        total_keys = sum(len(v) for v in keys_by_type.values())
        if total_keys == 0:
            logger.info("No Jira keys found in PR table")
            return {"epic": 0, "story": 0, "task": 0, "project": 0}

        logger.info(
            f"Found Jira keys in PR table: "
            f"{len(keys_by_type['epic'])} epics, "
            f"{len(keys_by_type['story'])} stories, "
            f"{len(keys_by_type['task'])} tasks"
        )

        project_keys_seen: set[str] = set()
        counts = {"epic": 0, "story": 0, "task": 0, "project": 0}

        for issue_type, keys in keys_by_type.items():
            for key in keys:
                try:
                    issue_data = await self.fetch_issue(key)
                    self._upsert_issue(key, issue_data, issue_type, db)
                    counts[issue_type] += 1

                    project_key = self._extract_project_key(key)
                    if project_key not in project_keys_seen:
                        project_keys_seen.add(project_key)
                        try:
                            project_data = await self.fetch_project(project_key)
                            self._upsert_project(project_key, project_data, db)
                            counts["project"] += 1
                        except httpx.HTTPStatusError as e:
                            logger.warning(f"Failed to fetch project {project_key}: {e.response.status_code}")
                except httpx.HTTPStatusError as e:
                    logger.warning(f"Failed to fetch Jira issue {key}: {e.response.status_code}")
                except Exception as e:
                    logger.warning(f"Unexpected error fetching {key}: {e}")

        db.commit()

        logger.info(
            f"Jira ingestion complete: "
            f"{counts['epic']} epics, {counts['story']} stories, "
            f"{counts['task']} tasks, {counts['project']} projects"
        )
        return counts

    async def ingest_issues_by_keys(
        self, issue_keys: list[str], issue_type: str, db: Session
    ) -> list[JiraEpic | JiraStory | JiraTask]:
        """Ingest specific Jira issues by their keys into the given type table."""
        records = []
        for key in issue_keys:
            try:
                issue_data = await self.fetch_issue(key)
                record = self._upsert_issue(key, issue_data, issue_type, db)
                records.append(record)

                project_key = self._extract_project_key(key)
                try:
                    project_data = await self.fetch_project(project_key)
                    self._upsert_project(project_key, project_data, db)
                except httpx.HTTPStatusError:
                    pass
            except Exception as e:
                logger.warning(f"Failed to ingest Jira issue {key}: {e}")

        db.commit()
        logger.info(f"Ingested {len(records)}/{len(issue_keys)} Jira {issue_type}s")
        return records
