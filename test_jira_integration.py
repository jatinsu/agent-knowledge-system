"""Integration test: seed PR table with real openshift/installer data,
run JiraIngestor.ingest_from_prs(), and verify JIRA_DB tables match live Jira."""

import asyncio
import httpx
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    Base, Repository, PullRequest,
    JiraProject, JiraEpic, JiraStory, JiraTask,
)
from src.ingestors.jira_ingestor import JiraIngestor

JIRA_URL = "https://redhat.atlassian.net"
TEST_DB = "sqlite:///./test_jira_integration.db"

# Real PRs from openshift/installer with verified Jira issue types:
#   Epic:  MULTIARCH-5791, CNTRLPLANE-1735, MCO-2161
#   Story: MULTIARCH-5824, CNTRLPLANE-2012, MCO-2200, SPLAT-2719
#   Task/Bug: OCPBUGS-83750, OCPBUGS-81622, CORS-3933
SEED_PRS = [
    {
        "pr_number": 10268,
        "title": "MULTIARCH-5824: PowerVS: Fix supported system types",
        "author": "test",
        "state": "open",
        "base_branch": "main",
        "head_branch": "fix-powervs",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "story_key": "MULTIARCH-5824",
        "epic_key": "MULTIARCH-5791",
    },
    {
        "pr_number": 10396,
        "title": "CNTRLPLANE-2012: Add configurable PKI support",
        "author": "test",
        "state": "open",
        "base_branch": "main",
        "head_branch": "pki-support",
        "created_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
        "story_key": "CNTRLPLANE-2012",
        "epic_key": "CNTRLPLANE-1735",
    },
    {
        "pr_number": 10481,
        "title": "MCO-2200: Add day-0 dual streams support",
        "author": "test",
        "state": "open",
        "base_branch": "main",
        "head_branch": "dual-streams",
        "created_at": datetime(2025, 1, 3, tzinfo=timezone.utc),
        "story_key": "MCO-2200",
        "epic_key": "MCO-2161",
    },
    {
        "pr_number": 10511,
        "title": "OCPBUGS-83750: Azure UPI ARM template fix",
        "author": "test",
        "state": "merged",
        "base_branch": "release-4.12",
        "head_branch": "fix-azure",
        "created_at": datetime(2025, 1, 4, tzinfo=timezone.utc),
        "task_key": "OCPBUGS-83750",
    },
    {
        "pr_number": 10501,
        "title": "OCPBUGS-81622: Include bootstrap gather in agent-gather",
        "author": "test",
        "state": "open",
        "base_branch": "main",
        "head_branch": "bootstrap-gather",
        "created_at": datetime(2025, 1, 5, tzinfo=timezone.utc),
        "task_key": "OCPBUGS-81622",
    },
    {
        "pr_number": 10463,
        "title": "CORS-3933: Add retry backoff for storage",
        "author": "test",
        "state": "open",
        "base_branch": "main",
        "head_branch": "retry-storage",
        "created_at": datetime(2025, 1, 6, tzinfo=timezone.utc),
        "task_key": "CORS-3933",
    },
]


def fetch_jira_issue_live(key: str) -> dict:
    """Fetch issue directly from Jira REST API for comparison."""
    r = httpx.get(
        f"{JIRA_URL}/rest/api/3/issue/{key}",
        params={"fields": "summary,description,issuetype,project"},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()


def extract_description_text(desc) -> str | None:
    if desc is None:
        return None
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        try:
            return desc["content"][0]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None
    return None


async def run_test():
    engine = create_engine(TEST_DB, echo=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Step 1: Seed repo and PRs
    repo = Repository(
        name="installer",
        owner="openshift",
        url="https://github.com/openshift/installer",
        default_branch="main",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db.add(repo)
    db.flush()

    for pr_data in SEED_PRS:
        pr = PullRequest(repo_id=repo.id, **pr_data)
        db.add(pr)
    db.commit()

    pr_count = db.query(PullRequest).count()
    print(f"\n{'='*70}")
    print(f"SEEDED {pr_count} PRs into PR table")
    print(f"{'='*70}")

    # Step 2: Run the Jira ingestor
    ingestor = JiraIngestor(url=JIRA_URL, email="", api_token="")
    counts = await ingestor.ingest_from_prs(db)

    print(f"\nIngestion results: {counts}")

    # Step 3: Verify each table
    epics = db.query(JiraEpic).all()
    stories = db.query(JiraStory).all()
    tasks = db.query(JiraTask).all()
    projects = db.query(JiraProject).all()

    print(f"\n{'='*70}")
    print(f"DATABASE CONTENTS")
    print(f"{'='*70}")

    print(f"\n--- JIRA_PROJECTS ({len(projects)}) ---")
    for p in projects:
        print(f"  {p.id:20s} | {p.title}")

    print(f"\n--- JIRA_EPICS ({len(epics)}) ---")
    for e in epics:
        print(f"  {e.id:20s} | {e.title}")

    print(f"\n--- JIRA_STORIES ({len(stories)}) ---")
    for s in stories:
        print(f"  {s.id:20s} | {s.title}")

    print(f"\n--- JIRA_TASKS ({len(tasks)}) ---")
    for t in tasks:
        print(f"  {t.id:20s} | {t.title}")

    # Step 4: Verify against live Jira
    print(f"\n{'='*70}")
    print(f"VERIFICATION AGAINST LIVE JIRA")
    print(f"{'='*70}")

    all_ok = True

    def verify_record(key: str, db_record, issue_type_label: str):
        nonlocal all_ok
        try:
            live = fetch_jira_issue_live(key)
            live_title = live["fields"]["summary"]
            live_desc = extract_description_text(live["fields"].get("description"))

            title_match = db_record.title == live_title
            desc_match = db_record.description == live_desc

            status = "PASS" if (title_match and desc_match) else "FAIL"
            if status == "FAIL":
                all_ok = False

            print(f"\n  [{status}] {key} ({issue_type_label})")
            print(f"    DB title:   {db_record.title[:80]}")
            print(f"    Live title: {live_title[:80]}")
            print(f"    Title match: {title_match}")
            if not desc_match:
                print(f"    DB desc:   {(db_record.description or 'None')[:80]}")
                print(f"    Live desc: {(live_desc or 'None')[:80]}")
                print(f"    Desc match: {desc_match}")
        except Exception as e:
            print(f"\n  [ERROR] {key}: {e}")
            all_ok = False

    for epic in epics:
        verify_record(epic.id, epic, "Epic")

    for story in stories:
        verify_record(story.id, story, "Story")

    for task in tasks:
        verify_record(task.id, task, "Task")

    # Verify projects
    for project in projects:
        try:
            r = httpx.get(
                f"{JIRA_URL}/rest/api/3/project/{project.id}",
                timeout=15.0,
            )
            r.raise_for_status()
            live_proj = r.json()
            title_match = project.title == live_proj["name"]
            status = "PASS" if title_match else "FAIL"
            if not title_match:
                all_ok = False
            print(f"\n  [{status}] Project {project.id}")
            print(f"    DB title:   {project.title}")
            print(f"    Live title: {live_proj['name']}")
        except Exception as e:
            print(f"\n  [ERROR] Project {project.id}: {e}")
            all_ok = False

    print(f"\n{'='*70}")
    print(f"OVERALL: {'ALL PASSED' if all_ok else 'SOME FAILURES'}")
    print(f"{'='*70}\n")

    db.close()
    engine.dispose()
    return all_ok


if __name__ == "__main__":
    ok = asyncio.run(run_test())
    exit(0 if ok else 1)
