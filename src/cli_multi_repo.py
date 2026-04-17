"""Multi-repository CLI commands for Agent Knowledge System."""

import asyncio
import json
import warnings

# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import click

from src.config import settings
from src.db.database import init_db, SessionLocal
from src.gateway.llm_gateway import LLMGateway
from src.agents.multi_repo_coordinator import MultiRepoCoordinator


@click.group()
def multi_repo_cli():
    """Multi-repository operations"""
    pass


@multi_repo_cli.command(name="ingest")
@click.option("--repos-file", required=True, help="JSON file with repository list")
@click.option("--limit", default=50, help="PRs per repository")
def ingest_multi(repos_file: str, limit: int):
    """
    Ingest multiple repositories from a JSON file.

    Example repos.json:
    [
        {"owner": "org1", "repo": "repo1"},
        {"owner": "org2", "repo": "repo2"}
    ]
    """

    async def run():
        db = SessionLocal()
        try:
            # Load repository specs
            with open(repos_file, "r") as f:
                repo_specs = json.load(f)

            click.echo(f"Loading {len(repo_specs)} repositories from {repos_file}")

            gateway = LLMGateway()
            coordinator = MultiRepoCoordinator(
                gateway, db, github_token=settings.github_token
            )

            click.echo("Starting multi-repo ingestion...")
            result = await coordinator.ingest_multiple_repos(repo_specs, limit)

            click.echo(f"\n✓ Multi-repo ingestion complete:")
            click.echo(f"  Total: {result['total']}")
            click.echo(f"  Successful: {result['successful']}")
            click.echo(f"  Failed: {result['failed']}")

            if result["successful"] > 0:
                click.echo(f"\nSuccessful repositories:")
                for item in result["results"]:
                    click.echo(f"  - {item['repo']}: {item['pr_count']} PRs")

            if result["failed"] > 0:
                click.echo(f"\nFailed repositories:")
                for item in result["errors"]:
                    click.echo(f"  - {item['repo']}: {item['error']}")

        finally:
            db.close()

    asyncio.run(run())


@multi_repo_cli.command(name="build-graph")
@click.option("--repo-ids", required=True, help="Comma-separated repository IDs")
def build_unified_graph(repo_ids: str):
    """Build unified knowledge graph from multiple repositories"""

    async def run():
        db = SessionLocal()
        try:
            ids = [int(id.strip()) for id in repo_ids.split(",")]

            click.echo(f"Building unified graph from {len(ids)} repositories...")

            gateway = LLMGateway()
            coordinator = MultiRepoCoordinator(
                gateway, db, github_token=settings.github_token
            )

            result = await coordinator.build_unified_graph(ids)

            click.echo(f"\n✓ Unified graph built:")
            click.echo(f"  Repositories: {', '.join(result['repositories'])}")
            click.echo(f"  Features: {result['total_features']}")
            click.echo(
                f"  Graph: {result['validation']['node_count']} nodes, "
                f"{result['validation']['edge_count']} edges"
            )
            click.echo(f"  Valid: {result['validation']['valid']}")

        finally:
            db.close()

    asyncio.run(run())


@multi_repo_cli.command(name="workflow")
@click.option("--repos-file", required=True, help="JSON file with repository list")
@click.option("--output-dir", default="docs", help="Output directory")
def full_multi_workflow(repos_file: str, output_dir: str):
    """Complete workflow for multiple repositories"""

    async def run():
        db = SessionLocal()
        try:
            # Load repository specs
            with open(repos_file, "r") as f:
                repo_specs = json.load(f)

            click.echo(f"Starting workflow for {len(repo_specs)} repositories...")

            gateway = LLMGateway()
            coordinator = MultiRepoCoordinator(
                gateway, db, github_token=settings.github_token
            )

            result = await coordinator.process_multiple_repos(repo_specs, output_dir)

            click.echo(f"\n✓ Multi-repo workflow complete!")
            click.echo(f"\nIngestion:")
            click.echo(f"  Successful: {result['ingestion']['successful']}")
            click.echo(f"  Failed: {result['ingestion']['failed']}")

            click.echo(f"\nKnowledge Graph:")
            click.echo(
                f"  Repositories: {', '.join(result['graph']['repositories'])}"
            )
            click.echo(f"  Features: {result['graph']['total_features']}")
            click.echo(
                f"  Nodes: {result['graph']['validation']['node_count']}"
            )
            click.echo(
                f"  Edges: {result['graph']['validation']['edge_count']}"
            )

            click.echo(f"\nDocumentation: {output_dir}/")
            click.echo(f"  - {result['documentation']['agents_md']}")
            click.echo(f"  - {result['documentation']['architecture_md']}")

        finally:
            db.close()

    asyncio.run(run())


@multi_repo_cli.command(name="create-config")
@click.option("--output", default="repos.json", help="Output file")
def create_config(output: str):
    """Create a sample multi-repo configuration file"""

    sample_config = [
        {"owner": "facebook", "repo": "react"},
        {"owner": "vercel", "repo": "next.js"},
        {"owner": "vuejs", "repo": "core"},
    ]

    with open(output, "w") as f:
        json.dump(sample_config, f, indent=2)

    click.echo(f"Created sample configuration: {output}")
    click.echo("\nEdit this file and add your repositories:")
    click.echo(json.dumps(sample_config, indent=2))


if __name__ == "__main__":
    multi_repo_cli()
