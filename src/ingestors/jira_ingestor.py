from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.db.models import PullRequest, Project, IssueType, Issue, IssueLink
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class JiraIngestor:
    def __init__(self, url: str, email: str, api_token: str):
        self.url = url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # ---- Jira API calls ----

    async def fetch_issue(self, issue_key: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching Jira issue {issue_key}")
            response = await client.get(
                f"{self.url}/rest/api/3/issue/{issue_key}",
                auth=self.auth,
                headers=self.headers,
                params={"fields": "summary,description,issuetype,status,priority,"
                        "assignee,reporter,project,parent,created,updated,duedate,"
                        "issuelinks,customfield_10014"},
            )
            response.raise_for_status()
            return response.json()

    async def fetch_project(self, project_key: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching Jira project {project_key}")
            response = await client.get(
                f"{self.url}/rest/api/3/project/{project_key}",
                auth=self.auth,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    # ---- Helpers ----

    def _extract_description_text(self, description: Any) -> str | None:
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

    def _parse_timestamp(self, ts: str | None) -> datetime | None:
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _extract_account_id(self, user_obj: dict | None) -> int | None:
        """Extract a numeric hash from Jira accountId for assignee/reporter."""
        if not user_obj:
            return None
        account_id = user_obj.get("accountId", "")
        return abs(hash(account_id)) % (2**31) if account_id else None

    # ---- Upsert operations ----

    def _upsert_project(self, project_data: dict[str, Any], db: Session) -> Project:
        project_id = int(project_data["id"])
        project_key = project_data["key"]

        project = db.get(Project, project_id)
        if not project:
            project = Project(
                project_id=project_id,
                project_key=project_key,
                name=project_data.get("name", project_key),
                description=project_data.get("description"),
                created_at=datetime.now(timezone.utc),
            )
            db.add(project)
        else:
            project.name = project_data.get("name", project_key)
            project.description = project_data.get("description")
            project.updated_at = datetime.now(timezone.utc)
        return project

    def _upsert_issue_type(self, type_data: dict[str, Any], db: Session) -> IssueType:
        type_id = int(type_data["id"])

        issue_type = db.get(IssueType, type_id)
        if not issue_type:
            issue_type = IssueType(
                issue_type_id=type_id,
                name=type_data["name"],
                hierarchy_level=type_data.get("hierarchyLevel", 0),
            )
            db.add(issue_type)
        return issue_type

    def _upsert_issue(self, issue_data: dict[str, Any], db: Session) -> Issue:
        issue_id = int(issue_data["id"])
        fields = issue_data.get("fields", {})

        project_data = fields["project"]
        self._upsert_project(project_data, db)
        project_id = int(project_data["id"])

        type_data = fields["issuetype"]
        self._upsert_issue_type(type_data, db)
        issue_type_id = int(type_data["id"])

        parent_issue_id = None
        parent_data = fields.get("parent")
        if parent_data:
            parent_issue_id = int(parent_data["id"])

        issue = db.get(Issue, issue_id)
        if not issue:
            issue = Issue(
                issue_id=issue_id,
                project_id=project_id,
                issue_type_id=issue_type_id,
                parent_issue_id=parent_issue_id,
                key=issue_data["key"],
                summary=fields.get("summary", ""),
                description=self._extract_description_text(fields.get("description")),
                status=fields.get("status", {}).get("name"),
                priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
                assignee_id=self._extract_account_id(fields.get("assignee")),
                reporter_id=self._extract_account_id(fields.get("reporter")),
                created_at=self._parse_timestamp(fields.get("created")) or datetime.now(timezone.utc),
                updated_at=self._parse_timestamp(fields.get("updated")),
                due_date=self._parse_timestamp(fields.get("duedate")),
            )
            db.add(issue)
        else:
            issue.summary = fields.get("summary", "")
            issue.description = self._extract_description_text(fields.get("description"))
            issue.status = fields.get("status", {}).get("name")
            issue.priority = fields.get("priority", {}).get("name") if fields.get("priority") else None
            issue.updated_at = self._parse_timestamp(fields.get("updated"))
            issue.parent_issue_id = parent_issue_id

        return issue

    def _insert_issue_links(self, issue_data: dict[str, Any], db: Session) -> None:
        fields = issue_data.get("fields", {})
        issue_id = int(issue_data["id"])

        for link_data in fields.get("issuelinks", []):
            link_type_name = link_data.get("type", {}).get("name", "relates_to")

            if "outwardIssue" in link_data:
                target_id = int(link_data["outwardIssue"]["id"])
                existing = db.query(IssueLink).filter(
                    IssueLink.source_issue_id == issue_id,
                    IssueLink.target_issue_id == target_id,
                    IssueLink.link_type == link_type_name,
                ).first()
                if not existing and db.get(Issue, target_id):
                    db.add(IssueLink(
                        source_issue_id=issue_id,
                        target_issue_id=target_id,
                        link_type=link_type_name,
                    ))

            if "inwardIssue" in link_data:
                source_id = int(link_data["inwardIssue"]["id"])
                existing = db.query(IssueLink).filter(
                    IssueLink.source_issue_id == source_id,
                    IssueLink.target_issue_id == issue_id,
                    IssueLink.link_type == link_type_name,
                ).first()
                if not existing and db.get(Issue, source_id):
                    db.add(IssueLink(
                        source_issue_id=source_id,
                        target_issue_id=issue_id,
                        link_type=link_type_name,
                    ))

    # ---- Collect keys from PR table ----

    def _collect_jira_keys_from_prs(self, db: Session) -> dict[str, set[str]]:
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

    # ---- Main entry points ----

    async def ingest_from_prs(self, db: Session) -> dict[str, int]:
        """Query PR table for jira keys, fetch from Jira, populate projects/issue_types/issues."""
        keys_by_type = self._collect_jira_keys_from_prs(db)

        all_keys: set[str] = set()
        for keys in keys_by_type.values():
            all_keys.update(keys)

        if not all_keys:
            logger.info("No Jira keys found in PR table")
            return {"issues": 0, "projects": 0, "issue_types": 0, "links": 0}

        logger.info(f"Found {len(all_keys)} unique Jira keys in PR table")

        # Pass 1: fetch all issues and walk parent chains to the root
        fetched: dict[str, dict] = {}
        queue = list(all_keys)

        while queue:
            key = queue.pop(0)
            if key in fetched:
                continue
            try:
                data = await self.fetch_issue(key)
                fetched[key] = data
                parent = data.get("fields", {}).get("parent")
                if parent:
                    parent_key = parent["key"]
                    if parent_key not in fetched:
                        queue.append(parent_key)
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to fetch {key}: {e.response.status_code}")
            except Exception as e:
                logger.warning(f"Unexpected error fetching {key}: {e}")

        # Fetch project details for each unique project
        project_keys_seen: set[str] = set()
        for data in fetched.values():
            pk = data.get("fields", {}).get("project", {}).get("key")
            if pk and pk not in project_keys_seen:
                project_keys_seen.add(pk)
                try:
                    proj_data = await self.fetch_project(pk)
                    self._upsert_project(proj_data, db)
                except httpx.HTTPStatusError:
                    logger.warning(f"Failed to fetch project details for {pk}")

        # Insert parents before children
        parents_first = sorted(
            fetched.values(),
            key=lambda d: 0 if not d.get("fields", {}).get("parent") else 1,
        )

        for data in parents_first:
            self._upsert_issue(data, db)

        db.flush()

        # Pass 2: insert issue links (both sides must exist)
        link_count = 0
        for data in fetched.values():
            before = db.query(IssueLink).count()
            self._insert_issue_links(data, db)
            db.flush()
            link_count += db.query(IssueLink).count() - before

        db.commit()

        issue_count = len([d for d in fetched.values()])
        project_count = len(project_keys_seen)
        type_count = db.query(IssueType).count()

        logger.info(
            f"Jira ingestion complete: {issue_count} issues, "
            f"{project_count} projects, {type_count} issue types, {link_count} links"
        )
        return {
            "issues": issue_count,
            "projects": project_count,
            "issue_types": type_count,
            "links": link_count,
        }

    async def ingest_issues_by_keys(
        self, issue_keys: list[str], db: Session
    ) -> list[Issue]:
        records = []
        for key in issue_keys:
            try:
                data = await self.fetch_issue(key)

                parent = data.get("fields", {}).get("parent")
                if parent:
                    try:
                        parent_data = await self.fetch_issue(parent["key"])
                        self._upsert_issue(parent_data, db)
                    except Exception:
                        pass

                pk = data.get("fields", {}).get("project", {}).get("key")
                if pk:
                    try:
                        proj_data = await self.fetch_project(pk)
                        self._upsert_project(proj_data, db)
                    except Exception:
                        pass

                record = self._upsert_issue(data, db)
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed to ingest {key}: {e}")

        db.commit()
        logger.info(f"Ingested {len(records)}/{len(issue_keys)} issues")
        return records
