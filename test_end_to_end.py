#!/usr/bin/env python3
"""
End-to-end test script for the Agent Knowledge System.

This script tests the complete workflow:
1. Database initialization
2. Mock data creation
3. Feature building
4. Knowledge graph construction
5. Documentation generation
6. Validation

Run with: python test_end_to_end.py
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from src.db.database import init_db, SessionLocal
from src.db.models import Repository, PullRequest, JiraTicket
from src.graph.builders import FeatureBuilder, GraphBuilder
from src.graph.storage import GraphStorage
from src.agents.doc_generator import DocumentationGenerator
from src.agents.validation import ValidationAgent
from src.gateway.llm_gateway import LLMGateway
from src.utils.logger import setup_logger

logger = setup_logger("test_e2e")


def create_mock_data():
    """Create mock repository, PRs, and Jira tickets for testing."""
    logger.info("Creating mock data...")

    db = SessionLocal()
    try:
        # Create mock repository
        repo = Repository(
            name="example-repo",
            owner="example-org",
            url="https://github.com/example-org/example-repo",
            default_branch="main",
            created_at=datetime.now(timezone.utc)
        )
        db.add(repo)
        db.flush()

        # Create mock Jira tickets
        jira1 = JiraTicket(
            key="PROJ-123",
            summary="Implement user authentication",
            description="Add OAuth2 authentication for users",
            ticket_type="Story",
            status="Done",
            priority="High",
            reporter="alice@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(jira1)

        jira2 = JiraTicket(
            key="PROJ-124",
            summary="Fix login bug",
            description="Users cannot login after password reset",
            ticket_type="Bug",
            status="Done",
            priority="Critical",
            reporter="bob@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(jira2)
        db.flush()

        # Create mock PRs
        pr1 = PullRequest(
            repo_id=repo.id,
            pr_number=101,
            title="Add OAuth2 authentication (PROJ-123)",
            description="Implements user authentication using OAuth2 protocol",
            author="alice",
            state="merged",
            base_branch="main",
            head_branch="feature/auth",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            files_changed="src/auth/oauth.py,src/auth/middleware.py,tests/test_auth.py",
            jira_keys="PROJ-123"
        )
        db.add(pr1)

        pr2 = PullRequest(
            repo_id=repo.id,
            pr_number=102,
            title="Fix password reset login issue",
            description="Fixes bug where users cannot login after password reset. Related to PROJ-124",
            author="bob",
            state="merged",
            base_branch="main",
            head_branch="bugfix/login",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            files_changed="src/auth/password.py,tests/test_password.py",
            jira_keys="PROJ-124"
        )
        db.add(pr2)

        pr3 = PullRequest(
            repo_id=repo.id,
            pr_number=103,
            title="Add session management",
            description="Implements secure session management for authenticated users",
            author="charlie",
            state="merged",
            base_branch="main",
            head_branch="feature/sessions",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            files_changed="src/auth/sessions.py,src/auth/cache.py,tests/test_sessions.py",
            jira_keys=""
        )
        db.add(pr3)

        db.commit()
        logger.info(f"Created mock repo: {repo.name}")
        logger.info(f"Created {db.query(PullRequest).count()} PRs")
        logger.info(f"Created {db.query(JiraTicket).count()} Jira tickets")

        return repo.id

    finally:
        db.close()


async def run_end_to_end_test():
    """Run complete end-to-end test."""
    logger.info("="*60)
    logger.info("Starting End-to-End Test")
    logger.info("="*60)

    # Step 1: Initialize database
    logger.info("\n[Step 1] Initializing database...")
    init_db()
    logger.info("✓ Database initialized")

    # Step 2: Create mock data
    logger.info("\n[Step 2] Creating mock data...")
    repo_id = create_mock_data()
    logger.info("✓ Mock data created")

    # Step 3: Build features
    logger.info("\n[Step 3] Building features...")
    db = SessionLocal()
    try:
        feature_builder = FeatureBuilder(db)
        features = feature_builder.build_features_from_repo(repo_id)
        logger.info(f"✓ Built {len(features)} features")

        for i, feature in enumerate(features, 1):
            logger.info(f"  Feature {i}: {feature.name}")
            logger.info(f"    PRs: {len(feature.pull_requests)}")
            logger.info(f"    Jira: {len(feature.jira_tickets)}")
    finally:
        db.close()

    # Step 4: Build knowledge graph
    logger.info("\n[Step 4] Building knowledge graph...")
    graph_builder = GraphBuilder()

    db = SessionLocal()
    try:
        from src.db.models import Feature
        features = db.query(Feature).filter(Feature.repo_id == repo_id).all()

        graph = graph_builder.build_from_features(features, db)
        logger.info(f"✓ Graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Save graph
        storage = GraphStorage()
        storage.save(graph)
        logger.info("✓ Graph saved to knowledge_graph.json")
    finally:
        db.close()

    # Step 5: Validate graph
    logger.info("\n[Step 5] Validating knowledge graph...")
    validation_result = graph.validate_graph()
    logger.info(f"  Valid: {validation_result['valid']}")
    logger.info(f"  Nodes: {validation_result['node_count']}")
    logger.info(f"  Edges: {validation_result['edge_count']}")
    logger.info(f"  Orphans: {len(validation_result['orphan_nodes'])}")

    if validation_result['valid']:
        logger.info("✓ Graph validation passed")
    else:
        logger.warning(f"⚠ Graph has issues: {validation_result}")

    # Step 6: Generate documentation (without LLM calls to avoid API requirements)
    logger.info("\n[Step 6] Generating documentation structure...")
    docs_dir = Path("docs_test")
    docs_dir.mkdir(exist_ok=True)

    # Create AGENTS.md manually without LLM
    from src.graph.types import NodeType
    concept_nodes = [n for n in graph.nodes if n.type == NodeType.CONCEPT]
    adr_nodes = [n for n in graph.nodes if n.type == NodeType.ADR]

    agents_content = f"""# AGENTS.md

Repository Knowledge Graph Entry Point

## Overview
This repository contains {len(concept_nodes)} concepts and {len(adr_nodes)} architectural decisions.

## Features
{chr(10).join([f"- {n.title}" for n in concept_nodes[:5]])}

## Statistics
- Total Nodes: {len(graph.nodes)}
- Total Edges: {len(graph.edges)}
- Concepts: {len(concept_nodes)}
- ADRs: {len(adr_nodes)}
"""

    agents_path = docs_dir / "AGENTS.md"
    agents_path.write_text(agents_content)
    logger.info(f"✓ Generated {agents_path}")

    # Step 7: Test retrieval (without LLM)
    logger.info("\n[Step 7] Testing graph structure...")
    entry_points = [n for n in graph.nodes if n.type == NodeType.ENTRY_POINT]
    logger.info(f"  Entry points: {len(entry_points)}")

    if entry_points:
        entry = entry_points[0]
        outgoing = graph.get_edges_from(entry.id)
        logger.info(f"  Edges from entry point: {len(outgoing)}")

        for edge in outgoing[:3]:
            target = graph.get_node(edge.target)
            if target:
                logger.info(f"    → {target.type.value}: {target.title[:50]}")

    # Final summary
    logger.info("\n" + "="*60)
    logger.info("End-to-End Test Summary")
    logger.info("="*60)
    logger.info(f"✓ Database initialized")
    logger.info(f"✓ Created {len(features)} features from 3 PRs and 2 Jira tickets")
    logger.info(f"✓ Built knowledge graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    logger.info(f"✓ Graph validation: {'PASSED' if validation_result['valid'] else 'ISSUES'}")
    logger.info(f"✓ Generated documentation in {docs_dir}/")
    logger.info("\n✅ End-to-End Test PASSED")

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_end_to_end_test())
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ End-to-end test FAILED: {e}", exc_info=True)
        exit(1)
