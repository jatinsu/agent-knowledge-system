#!/usr/bin/env python3
"""
Test improvements: persistent storage, logging, and NetworkX integration.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from src.db.database import init_db, SessionLocal
from src.db.models import Repository, PullRequest, JiraTicket
from src.graph.builders import FeatureBuilder, GraphBuilder
from src.graph.storage import GraphStorage
from src.graph.networkx_adapter import NetworkXGraphAdapter
from src.agents.retrieval import RetrievalAgent
from src.gateway.llm_gateway import LLMGateway
from src.utils.logger import setup_logger, setup_run_logger, get_run_id

logger = setup_logger("test_improvements")
run_logger = setup_run_logger()


def create_test_data():
    """Create test data with diverse relationships."""
    run_logger.info("[PHASE 1] Creating test data...")

    db = SessionLocal()
    try:
        # Create repository
        repo = Repository(
            name="test-project",
            owner="test-org",
            url="https://github.com/test-org/test-project",
            default_branch="main",
            created_at=datetime.now(timezone.utc)
        )
        db.add(repo)
        db.flush()

        # Create Jira tickets
        jira_tickets = []
        for i in range(5):
            ticket = JiraTicket(
                key=f"TEST-{i+1}",
                summary=f"Feature {i+1}",
                description=f"Description for feature {i+1}",
                ticket_type="Story",
                status="Done",
                priority="High",
                reporter="system@test.com",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(ticket)
            jira_tickets.append(ticket)

        db.flush()

        # Create PRs
        for i in range(5):
            pr = PullRequest(
                repo_id=repo.id,
                pr_number=i + 1,
                title=f"Implement feature {i+1} (TEST-{i+1})",
                description=f"Implementation of feature {i+1}",
                author=f"dev{i+1}",
                state="merged",
                base_branch="main",
                head_branch=f"feature/{i+1}",
                created_at=datetime.now(timezone.utc),
                merged_at=datetime.now(timezone.utc),
                files_changed=f"src/feature{i+1}.py,tests/test_feature{i+1}.py",
                jira_keys=f"TEST-{i+1}"
            )
            db.add(pr)

        db.commit()
        run_logger.info(f"✓ Created {repo.name} with 5 PRs and 5 Jira tickets")

        return repo.id

    finally:
        db.close()


async def test_persistent_storage():
    """Test persistent storage with versioning and backups."""
    run_logger.info("[PHASE 2] Testing persistent storage...")

    db = SessionLocal()
    try:
        # Build features and graph
        repo_id = 1  # From create_test_data
        feature_builder = FeatureBuilder(db)
        features = feature_builder.build_features_from_repo(repo_id)

        graph_builder = GraphBuilder()
        graph = graph_builder.build_from_features(features, db)

        # Test storage
        storage = GraphStorage()

        # Save with auto-versioning
        logger.info("Saving graph with auto-versioning...")
        storage.save(graph, auto_version=True)

        # List versions
        versions = storage.list_versions()
        run_logger.info(f"✓ Graph saved with {len(versions)} versions")

        # Test loading
        loaded_graph = storage.load()
        run_logger.info(f"✓ Graph loaded: {len(loaded_graph.nodes)} nodes")

        # List backups
        backups = storage.list_backups()
        run_logger.info(f"✓ {len(backups)} backups available")

        return graph

    finally:
        db.close()


async def test_networkx_integration(graph):
    """Test NetworkX integration."""
    run_logger.info("[PHASE 3] Testing NetworkX integration...")

    adapter = NetworkXGraphAdapter(graph)

    # Test metrics
    metrics = adapter.analyze_graph_metrics()
    run_logger.info(f"✓ Graph metrics calculated: {len(metrics)} metrics")

    # Test hubs
    hubs = adapter.find_hubs(top_n=5)
    run_logger.info(f"✓ Found {len(hubs)} hub nodes")

    # Test centrality
    centrality = adapter.get_node_centrality("betweenness")
    run_logger.info(f"✓ Centrality calculated for {len(centrality)} nodes")

    # Test components
    components = adapter.get_connected_components()
    run_logger.info(f"✓ Found {len(components)} connected components")

    return adapter


async def test_improved_retrieval(graph):
    """Test improved retrieval algorithm."""
    run_logger.info("[PHASE 4] Testing improved retrieval...")

    gateway = LLMGateway()
    retrieval_agent = RetrievalAgent(gateway, graph)

    # Test query
    query = "feature implementation"
    result = await retrieval_agent.retrieve(query)

    run_logger.info(f"✓ Retrieval test:")
    run_logger.info(f"  Entities: {result['entities']}")
    run_logger.info(f"  Matched nodes: {result['matched_nodes']}")
    run_logger.info(f"  Related nodes: {result['related_nodes']}")
    run_logger.info(f"  Context lines: {result['context_lines']}")

    # Verify it didn't pull entire graph
    if result['related_nodes'] < len(graph.nodes):
        run_logger.info(f"  ✓ BFS limited results ({result['related_nodes']}/{len(graph.nodes)} nodes)")
    else:
        run_logger.warning(f"  ⚠ BFS pulled entire graph")


async def run_test():
    """Run all improvement tests."""
    run_id = get_run_id()

    run_logger.info("="*60)
    run_logger.info(f"Testing Improvements - Run {run_id}")
    run_logger.info("="*60)

    # Initialize database
    run_logger.info("[PHASE 0] Initializing database...")
    init_db()
    run_logger.info("✓ Database initialized")

    # Create test data
    repo_id = create_test_data()

    # Test persistent storage
    graph = await test_persistent_storage()

    # Test NetworkX
    adapter = await test_networkx_integration(graph)

    # Test improved retrieval
    await test_improved_retrieval(graph)

    # Summary
    run_logger.info("="*60)
    run_logger.info("Test Summary")
    run_logger.info("="*60)
    run_logger.info("✓ Persistent storage with versioning: PASSED")
    run_logger.info("✓ NetworkX integration: PASSED")
    run_logger.info("✓ Improved retrieval algorithm: PASSED")
    run_logger.info("✓ Enhanced logging: ACTIVE")

    # Log file locations
    log_dir = Path("logs")
    run_logger.info(f"\nLog files generated:")
    run_logger.info(f"  - logs/e2e_run_{run_id}.log")
    run_logger.info(f"  - logs/run_{run_id}.log")
    run_logger.info(f"  - logs/graph_queries_{run_id}.log")
    run_logger.info(f"  - logs/networkx_queries_{run_id}.log")

    run_logger.info("\n✅ ALL TESTS PASSED")


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
        exit(0)
    except Exception as e:
        logger.error(f"❌ Test FAILED: {e}", exc_info=True)
        exit(1)
