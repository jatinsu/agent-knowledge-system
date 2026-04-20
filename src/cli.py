import asyncio
from pathlib import Path
import warnings

# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import click

from src.config import settings
from src.db.database import init_db, SessionLocal
from src.gateway.llm_gateway import LLMGateway
from src.agents.router import RouterOrchestrator, TaskType
from src.agents.multi_repo_coordinator import MultiRepoCoordinator
from src.graph.storage import GraphStorage
from src.agents.retrieval import RetrievalAgent
from src.agents.validation import ValidationAgent


@click.group()
def cli():
    """Agent Knowledge System - Agentic Documentation Generator"""
    pass


@cli.command()
def init():
    """Initialize the database"""
    click.echo("Initializing database...")
    init_db()
    click.echo("Database initialized successfully!")


@cli.command()
@click.option("--owner", required=True, help="GitHub repository owner")
@click.option("--repo", required=True, help="GitHub repository name")
@click.option("--limit", default=100, help="Number of PRs to ingest")
def ingest_github(owner: str, repo: str, limit: int):
    """Ingest data from GitHub repository"""

    async def run():
        db = SessionLocal()
        try:
            gateway = LLMGateway()
            orchestrator = RouterOrchestrator(
                gateway, db, github_token=settings.github_token
            )

            click.echo(f"Ingesting PRs from {owner}/{repo}...")
            result = await orchestrator.execute_task(
                TaskType.INGEST_GITHUB, {"owner": owner, "repo": repo, "limit": limit}
            )
            click.echo(f"Ingested {result['pr_count']} pull requests")
        finally:
            db.close()

    asyncio.run(run())


@cli.command()
@click.option("--keys", help="Comma-separated Jira issue keys (requires --type)")
@click.option("--type", "issue_type", type=click.Choice(["epic", "story", "task"]), help="Issue type for --keys")
def ingest_jira(keys: str | None, issue_type: str | None):
    """Ingest Jira data from keys found in PR table, or by explicit keys."""

    async def run():
        db = SessionLocal()
        try:
            gateway = LLMGateway()
            orchestrator = RouterOrchestrator(
                gateway,
                db,
                jira_url=settings.jira_url,
                jira_email=settings.jira_email,
                jira_token=settings.jira_api_token,
            )

            params: dict = {}
            if keys:
                if not issue_type:
                    click.echo("Error: --type is required when using --keys")
                    return
                params["keys"] = keys.split(",")
                params["issue_type"] = issue_type

            click.echo("Ingesting Jira issues...")
            result = await orchestrator.execute_task(TaskType.INGEST_JIRA, params)

            if "ticket_count" in result:
                click.echo(f"Ingested {result['ticket_count']} tickets")
            else:
                click.echo(
                    f"Ingested: {result.get('epic', 0)} epics, "
                    f"{result.get('story', 0)} stories, "
                    f"{result.get('task', 0)} tasks, "
                    f"{result.get('project', 0)} projects"
                )
        finally:
            db.close()

    asyncio.run(run())


@cli.command()
@click.option("--repo-id", required=True, type=int, help="Repository ID")
def build_features(repo_id: int):
    """Build features from ingested data"""

    async def run():
        db = SessionLocal()
        try:
            gateway = LLMGateway()
            orchestrator = RouterOrchestrator(gateway, db)

            click.echo(f"Building features for repo {repo_id}...")
            result = await orchestrator.execute_task(
                TaskType.BUILD_FEATURES, {"repo_id": repo_id}
            )
            click.echo(f"Built {result['feature_count']} features")
        finally:
            db.close()

    asyncio.run(run())


@cli.command()
@click.option("--repo-id", required=True, type=int, help="Repository ID")
def build_graph(repo_id: int):
    """Build knowledge graph from features"""

    async def run():
        db = SessionLocal()
        try:
            gateway = LLMGateway()
            orchestrator = RouterOrchestrator(gateway, db)

            from src.db.models import Feature

            features = db.query(Feature).filter(Feature.repo_id == repo_id).all()

            click.echo(f"Building knowledge graph from {len(features)} features...")
            result = await orchestrator.execute_task(
                TaskType.BUILD_GRAPH, {"features": features}
            )

            validation = result["validation"]
            click.echo(f"Graph built: {validation['node_count']} nodes, {validation['edge_count']} edges")
            click.echo(f"Valid: {validation['valid']}")
            if validation["orphan_nodes"]:
                click.echo(f"Warning: {len(validation['orphan_nodes'])} orphan nodes")
        finally:
            db.close()

    asyncio.run(run())


@cli.command()
@click.option("--output-dir", default="docs", help="Output directory")
def generate_docs(output_dir: str):
    """Generate documentation from knowledge graph"""

    async def run():
        storage = GraphStorage()
        graph = storage.load()

        gateway = LLMGateway()
        db = SessionLocal()
        try:
            orchestrator = RouterOrchestrator(gateway, db)

            click.echo("Generating documentation...")
            result = await orchestrator.execute_task(
                TaskType.GENERATE_DOCS, {"graph": graph, "output_dir": output_dir}
            )

            click.echo(f"Generated:")
            click.echo(f"  - {result['agents_md']}")
            click.echo(f"  - {result['architecture_md']}")
        finally:
            db.close()

    asyncio.run(run())


@cli.command()
@click.argument("query")
def retrieve(query: str):
    """Retrieve context from knowledge graph"""

    async def run():
        storage = GraphStorage()
        graph = storage.load()

        gateway = LLMGateway()
        retrieval_agent = RetrievalAgent(gateway, graph)

        click.echo(f"Query: {query}")
        result = await retrieval_agent.retrieve(query)

        click.echo(f"\nIntent: {result['intent']}")
        click.echo(f"Entities: {', '.join(result['entities'])}")
        click.echo(f"Matched nodes: {result['matched_nodes']}")
        click.echo(f"Related nodes: {result['related_nodes']}")
        click.echo(f"Context lines: {result['context_lines']}")
        click.echo(f"\n--- Context ---\n{result['context'][:500]}...")

    asyncio.run(run())


@cli.command()
def validate():
    """Validate knowledge graph"""

    async def run():
        storage = GraphStorage()
        graph = storage.load()

        gateway = LLMGateway()
        validation_agent = ValidationAgent(gateway)

        click.echo("Validating knowledge graph...")
        result = validation_agent.validate_graph(graph)

        click.echo(f"Graph valid: {result['graph_valid']}")
        click.echo(f"Nodes: {result['node_count']}")
        click.echo(f"Edges: {result['edge_count']}")
        click.echo(f"\nCoverage:")
        click.echo(f"  Concepts: {result['coverage']['concepts']}")
        click.echo(f"  ADRs: {result['coverage']['adrs']}")
        click.echo(f"  Plans: {result['coverage']['plans']}")
        click.echo(f"  Meets minimum: {result['coverage']['meets_minimum']}")

        if result["orphan_nodes"]:
            click.echo(f"\nWarning: {len(result['orphan_nodes'])} orphan nodes")

    asyncio.run(run())


@cli.command()
@click.option("--owner", required=True, help="GitHub repository owner")
@click.option("--repo", required=True, help="GitHub repository name")
@click.option("--output-dir", default="docs", help="Output directory")
def full_workflow(owner: str, repo: str, output_dir: str):
    """Run the complete workflow: ingest -> features -> graph -> docs"""

    async def run():
        db = SessionLocal()
        try:
            gateway = LLMGateway()
            orchestrator = RouterOrchestrator(
                gateway, db, github_token=settings.github_token
            )

            click.echo("Step 1: Ingesting GitHub data...")
            github_result = await orchestrator.execute_task(
                TaskType.INGEST_GITHUB, {"owner": owner, "repo": repo, "limit": 50}
            )
            click.echo(f"  ✓ Ingested {github_result['pr_count']} PRs")

            from src.db.models import Repository

            repository = (
                db.query(Repository)
                .filter(Repository.owner == owner, Repository.name == repo)
                .first()
            )

            click.echo("Step 2: Building features...")
            features_result = await orchestrator.execute_task(
                TaskType.BUILD_FEATURES, {"repo_id": repository.id}
            )
            click.echo(f"  ✓ Built {features_result['feature_count']} features")

            from src.db.models import Feature

            features = db.query(Feature).filter(Feature.repo_id == repository.id).all()

            click.echo("Step 3: Building knowledge graph...")
            graph_result = await orchestrator.execute_task(
                TaskType.BUILD_GRAPH, {"features": features}
            )
            validation = graph_result["validation"]
            click.echo(f"  ✓ Graph: {validation['node_count']} nodes, {validation['edge_count']} edges")

            click.echo("Step 4: Generating documentation...")
            docs_result = await orchestrator.execute_task(
                TaskType.GENERATE_DOCS,
                {"graph": graph_result["graph"], "output_dir": output_dir},
            )
            click.echo(f"  ✓ Generated documentation in {output_dir}/")

            click.echo("\n✓ Workflow complete!")
        finally:
            db.close()

    asyncio.run(run())


if __name__ == "__main__":
    cli()
