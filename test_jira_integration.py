"""Integration test: seed PR table with real openshift/installer data,
run JiraIngestor.ingest_from_prs(), and verify issues/projects/issue_types
tables match live Jira."""

import asyncio
import httpx
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    Base, Repository, PullRequest,
    Project, IssueType, Issue, IssueLink,
)
from src.ingestors.jira_ingestor import JiraIngestor

JIRA_URL = "https://redhat.atlassian.net"
TEST_DB = "sqlite:///./test_jira_integration.db"

# Real PRs from openshift/installer with verified Jira issue types:
#   Epic:  MULTIARCH-5791, CNTRLPLANE-1735, MCO-2161
#   Story: MULTIARCH-5824, CNTRLPLANE-2012, MCO-2200
#   Bug:   OCPBUGS-83750, OCPBUGS-81622, CORS-3933
SEED_PRS = [
    {
        "pr_number": 10268,
        "title": "MULTIARCH-5824: PowerVS: Fix supported system types",
        "author": "test", "state": "open",
        "base_branch": "main", "head_branch": "fix-powervs",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "story_key": "MULTIARCH-5824",
        "epic_key": "MULTIARCH-5791",
    },
    {
        "pr_number": 10396,
        "title": "CNTRLPLANE-2012: Add configurable PKI support",
        "author": "test", "state": "open",
        "base_branch": "main", "head_branch": "pki-support",
        "created_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
        "story_key": "CNTRLPLANE-2012",
        "epic_key": "CNTRLPLANE-1735",
    },
    {
        "pr_number": 10481,
        "title": "MCO-2200: Add day-0 dual streams support",
        "author": "test", "state": "open",
        "base_branch": "main", "head_branch": "dual-streams",
        "created_at": datetime(2025, 1, 3, tzinfo=timezone.utc),
        "story_key": "MCO-2200",
        "epic_key": "MCO-2161",
    },
    {
        "pr_number": 10511,
        "title": "OCPBUGS-83750: Azure UPI ARM template fix",
        "author": "test", "state": "merged",
        "base_branch": "release-4.12", "head_branch": "fix-azure",
        "created_at": datetime(2025, 1, 4, tzinfo=timezone.utc),
        "task_key": "OCPBUGS-83750",
    },
    {
        "pr_number": 10501,
        "title": "OCPBUGS-81622: Include bootstrap gather in agent-gather",
        "author": "test", "state": "open",
        "base_branch": "main", "head_branch": "bootstrap-gather",
        "created_at": datetime(2025, 1, 5, tzinfo=timezone.utc),
        "task_key": "OCPBUGS-81622",
    },
    {
        "pr_number": 10463,
        "title": "CORS-3933: Add retry backoff for storage",
        "author": "test", "state": "open",
        "base_branch": "main", "head_branch": "retry-storage",
        "created_at": datetime(2025, 1, 6, tzinfo=timezone.utc),
        "task_key": "CORS-3933",
    },
]


def fetch_jira_issue_live(key: str) -> dict:
    r = httpx.get(
        f"{JIRA_URL}/rest/api/3/issue/{key}",
        params={"fields": "summary,description,issuetype,project,status,priority,parent"},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()


async def run_test():
    engine = create_engine(TEST_DB, echo=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Step 1: Seed repo and PRs
    repo = Repository(
        name="installer", owner="openshift",
        url="https://github.com/openshift/installer",
        default_branch="main",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db.add(repo)
    db.flush()

    for pr_data in SEED_PRS:
        db.add(PullRequest(repo_id=repo.id, **pr_data))
    db.commit()

    print(f"\n{'='*70}")
    print(f"SEEDED {db.query(PullRequest).count()} PRs into PR table")
    print(f"{'='*70}")

    # Step 2: Run the Jira ingestor
    ingestor = JiraIngestor(url=JIRA_URL, email="", api_token="")
    counts = await ingestor.ingest_from_prs(db)
    print(f"\nIngestion results: {counts}")

    # Step 3: Print table contents
    projects = db.query(Project).all()
    issue_types = db.query(IssueType).all()
    issues = db.query(Issue).all()
    links = db.query(IssueLink).all()

    print(f"\n{'='*70}")
    print(f"DATABASE CONTENTS")
    print(f"{'='*70}")

    print(f"\n--- projects ({len(projects)}) ---")
    print(f"  {'project_id':<12} {'project_key':<15} {'name'}")
    print(f"  {'-'*12} {'-'*15} {'-'*30}")
    for p in projects:
        print(f"  {p.project_id:<12} {p.project_key:<15} {p.name}")

    print(f"\n--- issue_types ({len(issue_types)}) ---")
    print(f"  {'id':<6} {'name':<20} {'hierarchy_level'}")
    print(f"  {'-'*6} {'-'*20} {'-'*15}")
    for it in sorted(issue_types, key=lambda x: x.hierarchy_level):
        print(f"  {it.issue_type_id:<6} {it.name:<20} {it.hierarchy_level}")

    print(f"\n--- issues ({len(issues)}) ---")
    print(f"  {'key':<20} {'type':<20} {'status':<15} {'parent':<20} {'summary'}")
    print(f"  {'-'*20} {'-'*20} {'-'*15} {'-'*20} {'-'*40}")
    for i in sorted(issues, key=lambda x: (x.issue_type.hierarchy_level if x.issue_type else 0, x.key)):
        parent_key = i.parent.key if i.parent else "-"
        type_name = i.issue_type.name if i.issue_type else "?"
        print(f"  {i.key:<20} {type_name:<20} {(i.status or '-'):<15} {parent_key:<20} {i.summary[:50]}")

    if links:
        print(f"\n--- issue_links ({len(links)}) ---")
        for lnk in links:
            src = db.get(Issue, lnk.source_issue_id)
            tgt = db.get(Issue, lnk.target_issue_id)
            print(f"  {src.key if src else '?'} --[{lnk.link_type}]--> {tgt.key if tgt else '?'}")

    # Step 4: Verify against live Jira
    print(f"\n{'='*70}")
    print(f"VERIFICATION AGAINST LIVE JIRA")
    print(f"{'='*70}")

    all_ok = True
    for issue in issues:
        try:
            live = fetch_jira_issue_live(issue.key)
            live_fields = live["fields"]

            checks = {
                "summary": issue.summary == live_fields["summary"],
                "status": issue.status == live_fields.get("status", {}).get("name"),
                "issue_type": issue.issue_type.name == live_fields["issuetype"]["name"],
                "project": issue.project.project_key == live_fields["project"]["key"],
            }

            live_parent = live_fields.get("parent", {}).get("key")
            db_parent = issue.parent.key if issue.parent else None
            checks["parent"] = db_parent == live_parent

            failed = [k for k, v in checks.items() if not v]
            status = "PASS" if not failed else "FAIL"
            if failed:
                all_ok = False

            print(f"\n  [{status}] {issue.key} ({issue.issue_type.name})")
            if failed:
                for f in failed:
                    if f == "summary":
                        print(f"    summary DB:   {issue.summary[:60]}")
                        print(f"    summary Live: {live_fields['summary'][:60]}")
                    elif f == "parent":
                        print(f"    parent DB: {db_parent}, Live: {live_parent}")
                    else:
                        print(f"    {f} mismatch")
            else:
                print(f"    summary: {issue.summary[:60]}")
                print(f"    parent: {db_parent or '-'}")
        except Exception as e:
            print(f"\n  [ERROR] {issue.key}: {e}")
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
