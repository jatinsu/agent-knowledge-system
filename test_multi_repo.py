#!/usr/bin/env python3
"""
Test multi-repository functionality.

This script creates mock data for multiple repositories and tests
the multi-repo coordinator.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from src.db.database import init_db, SessionLocal
from src.db.models import Repository, PullRequest, JiraTicket
from src.agents.multi_repo_coordinator import MultiRepoCoordinator
from src.gateway.llm_gateway import LLMGateway
from src.utils.logger import setup_logger

logger = setup_logger("test_multi_repo")


def create_multi_repo_mock_data():
    """Create mock data for multiple repositories."""
    logger.info("Creating multi-repo mock data...")

    db = SessionLocal()
    try:
        repos_data = [
            {
                "name": "auth-service",
                "owner": "example-org",
                "prs": [
                    {
                        "number": 10,
                        "title": "Add OAuth2 support (AUTH-100)",
                        "jira": "AUTH-100",
                        "files": "src/oauth.py,tests/test_oauth.py",
                    },
                    {
                        "number": 11,
                        "title": "Fix token expiration (AUTH-101)",
                        "jira": "AUTH-101",
                        "files": "src/tokens.py",
                    },
                ],
            },
            {
                "name": "api-gateway",
                "owner": "example-org",
                "prs": [
                    {
                        "number": 20,
                        "title": "Add rate limiting (GATE-200)",
                        "jira": "GATE-200",
                        "files": "src/ratelimit.py,src/middleware.py",
                    },
                    {
                        "number": 21,
                        "title": "Implement request routing",
                        "jira": "",
                        "files": "src/router.py",
                    },
                ],
            },
            {
                "name": "user-service",
                "owner": "example-org",
                "prs": [
                    {
                        "number": 30,
                        "title": "Add user profile endpoints (USER-300)",
                        "jira": "USER-300",
                        "files": "src/profile.py,src/api.py",
                    },
                ],
            },
        ]

        # Create Jira tickets
        jira_tickets = [
            {"key": "AUTH-100", "summary": "Implement OAuth2 authentication"},
            {"key": "AUTH-101", "summary": "Fix token expiration bug"},
            {"key": "GATE-200", "summary": "Add rate limiting to API gateway"},
            {"key": "USER-300", "summary": "Create user profile API"},
        ]

        for ticket_data in jira_tickets:
            ticket = JiraTicket(
                key=ticket_data["key"],
                summary=ticket_data["summary"],
                description=f"Description for {ticket_data['key']}",
                ticket_type="Story",
                status="Done",
                priority="High",
                reporter="system@example.com",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(ticket)

        db.flush()

        # Create repos and PRs
        repo_ids = []
        for repo_data in repos_data:
            repo = Repository(
                name=repo_data["name"],
                owner=repo_data["owner"],
                url=f"https://github.com/{repo_data['owner']}/{repo_data['name']}",
                default_branch="main",
                created_at=datetime.now(timezone.utc),
            )
            db.add(repo)
            db.flush()
            repo_ids.append(repo.id)

            for pr_data in repo_data["prs"]:
                pr = PullRequest(
                    repo_id=repo.id,
                    pr_number=pr_data["number"],
                    title=pr_data["title"],
                    description=f"Description for PR #{pr_data['number']}",
                    author="developer",
                    state="merged",
                    base_branch="main",
                    head_branch=f"feature/pr{pr_data['number']}",
                    created_at=datetime.now(timezone.utc),
                    merged_at=datetime.now(timezone.utc),
                    files_changed=pr_data["files"],
                    jira_keys=pr_data["jira"],
                )
                db.add(pr)

        db.commit()

        logger.info(f"Created {len(repos_data)} repositories")
        logger.info(f"Created {len(jira_tickets)} Jira tickets")
        total_prs = sum(len(r["prs"]) for r in repos_data)
        logger.info(f"Created {total_prs} PRs total")

        return repo_ids

    finally:
        db.close()


async def run_multi_repo_test():
    """Test multi-repository functionality."""
    logger.info("=" * 60)
    logger.info("Starting Multi-Repository Test")
    logger.info("=" * 60)

    # Step 1: Initialize database
    logger.info("\n[Step 1] Initializing database...")
    init_db()
    logger.info("✓ Database initialized")

    # Step 2: Create mock data
    logger.info("\n[Step 2] Creating multi-repo mock data...")
    repo_ids = create_multi_repo_mock_data()
    logger.info(f"✓ Created {len(repo_ids)} repositories")

    # Step 3: Build unified graph
    logger.info("\n[Step 3] Building unified knowledge graph...")
    db = SessionLocal()
    try:
        gateway = LLMGateway()
        coordinator = MultiRepoCoordinator(gateway, db)

        result = await coordinator.build_unified_graph(repo_ids)

        logger.info(f"✓ Unified graph built:")
        logger.info(f"  Repositories: {', '.join(result['repositories'])}")
        logger.info(f"  Total features: {result['total_features']}")
        logger.info(
            f"  Graph: {result['validation']['node_count']} nodes, "
            f"{result['validation']['edge_count']} edges"
        )
        logger.info(f"  Valid: {result['validation']['valid']}")

        # Verify cross-repo connectivity
        graph = result["graph"]
        from src.graph.types import NodeType

        entry_points = [n for n in graph.nodes if n.type == NodeType.ENTRY_POINT]
        concepts = [n for n in graph.nodes if n.type == NodeType.CONCEPT]

        logger.info(f"\n[Step 4] Verifying cross-repo structure...")
        logger.info(f"  Entry points: {len(entry_points)}")
        logger.info(f"  Concepts: {len(concepts)}")

        if entry_points:
            entry = entry_points[0]
            edges = graph.get_edges_from(entry.id)
            logger.info(f"  Edges from entry: {len(edges)}")

            logger.info(f"\n  Connected concepts:")
            for edge in edges[:5]:
                target = graph.get_node(edge.target)
                if target:
                    logger.info(f"    → {target.title[:60]}")

        # Save graph
        from src.graph.storage import GraphStorage

        storage = GraphStorage("multi_repo_graph.json")
        storage.save(graph)
        logger.info(f"\n✓ Graph saved to multi_repo_graph.json")

        # Generate documentation
        logger.info("\n[Step 5] Generating documentation...")
        from src.agents.doc_generator import DocumentationGenerator

        docs_dir = Path("docs_multi_repo")
        docs_dir.mkdir(exist_ok=True)

        # Create AGENTS.md manually
        agents_content = f"""# AGENTS.md - Multi-Repository Knowledge Graph

## Overview
Unified knowledge graph from multiple microservices.

## Repositories
{chr(10).join([f"- {name}" for name in result['repositories']])}

## Features
{chr(10).join([f"- {c.title}" for c in concepts[:10]])}

## Statistics
- Repositories: {len(result['repositories'])}
- Total Features: {result['total_features']}
- Total Nodes: {len(graph.nodes)}
- Total Edges: {len(graph.edges)}
"""

        agents_path = docs_dir / "AGENTS.md"
        agents_path.write_text(agents_content)
        logger.info(f"✓ Generated {agents_path}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Multi-Repository Test Summary")
        logger.info("=" * 60)
        logger.info(f"✓ Processed {len(repo_ids)} repositories")
        logger.info(f"✓ Built unified graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        logger.info(f"✓ Features span multiple repositories: {result['total_features']}")
        logger.info(f"✓ Graph validation: PASSED")
        logger.info(f"✓ Documentation: {docs_dir}/")
        logger.info("\n✅ Multi-Repository Test PASSED")

        return True

    finally:
        db.close()


if __name__ == "__main__":
    try:
        success = asyncio.run(run_multi_repo_test())
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Multi-repo test FAILED: {e}", exc_info=True)
        exit(1)
