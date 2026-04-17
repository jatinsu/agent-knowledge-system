import asyncio
from typing import Any
from pathlib import Path

from sqlalchemy.orm import Session

from src.gateway.llm_gateway import LLMGateway
from src.agents.router import RouterOrchestrator, TaskType
from src.graph.builders import GraphBuilder
from src.graph.storage import GraphStorage
from src.db.models import Repository
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MultiRepoCoordinator:
    """Coordinates ingestion and processing of multiple repositories."""

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db: Session,
        github_token: str | None = None,
        jira_url: str | None = None,
        jira_email: str | None = None,
        jira_token: str | None = None,
    ):
        self.gateway = llm_gateway
        self.db = db
        self.orchestrator = RouterOrchestrator(
            llm_gateway, db, github_token, jira_url, jira_email, jira_token
        )

    async def ingest_multiple_repos(
        self, repo_specs: list[dict[str, Any]], limit_per_repo: int = 50
    ) -> dict[str, Any]:
        """
        Ingest multiple repositories in parallel.

        Args:
            repo_specs: List of dicts with 'owner' and 'repo' keys
            limit_per_repo: Max PRs to ingest per repository

        Returns:
            Summary of ingestion results
        """
        logger.info(f"Starting multi-repo ingestion for {len(repo_specs)} repositories")

        tasks = []
        for spec in repo_specs:
            task = self._ingest_single_repo(
                spec["owner"], spec["repo"], limit_per_repo
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []

        for i, result in enumerate(results):
            repo_spec = repo_specs[i]
            repo_name = f"{repo_spec['owner']}/{repo_spec['repo']}"

            if isinstance(result, Exception):
                logger.error(f"Failed to ingest {repo_name}: {result}")
                failed.append({"repo": repo_name, "error": str(result)})
            else:
                logger.info(f"Successfully ingested {repo_name}")
                successful.append({"repo": repo_name, **result})

        logger.info(
            f"Multi-repo ingestion complete: {len(successful)} succeeded, {len(failed)} failed"
        )

        return {
            "total": len(repo_specs),
            "successful": len(successful),
            "failed": len(failed),
            "results": successful,
            "errors": failed,
        }

    async def _ingest_single_repo(
        self, owner: str, repo: str, limit: int
    ) -> dict[str, Any]:
        """Ingest a single repository."""
        logger.info(f"Ingesting {owner}/{repo}...")

        result = await self.orchestrator.execute_task(
            TaskType.INGEST_GITHUB,
            {"owner": owner, "repo": repo, "limit": limit},
        )

        return {"pr_count": result["pr_count"]}

    async def build_unified_graph(self, repo_ids: list[int]) -> dict[str, Any]:
        """
        Build a unified knowledge graph from multiple repositories.

        Args:
            repo_ids: List of repository IDs to include

        Returns:
            Graph build results
        """
        logger.info(f"Building unified graph from {len(repo_ids)} repositories")

        all_features = []
        repo_names = []

        for repo_id in repo_ids:
            repo = self.db.query(Repository).filter(Repository.id == repo_id).first()
            if not repo:
                logger.warning(f"Repository {repo_id} not found")
                continue

            repo_names.append(f"{repo.owner}/{repo.name}")

            # Build features for this repo
            feature_result = await self.orchestrator.execute_task(
                TaskType.BUILD_FEATURES, {"repo_id": repo_id}
            )

            # Get the features
            from src.db.models import Feature

            features = (
                self.db.query(Feature).filter(Feature.repo_id == repo_id).all()
            )
            all_features.extend(features)

            logger.info(
                f"Added {len(features)} features from {repo.owner}/{repo.name}"
            )

        # Build unified graph
        logger.info(f"Building graph from {len(all_features)} total features")
        graph_result = await self.orchestrator.execute_task(
            TaskType.BUILD_GRAPH, {"features": all_features}
        )

        return {
            "repositories": repo_names,
            "total_features": len(all_features),
            "graph": graph_result["graph"],
            "validation": graph_result["validation"],
        }

    async def process_multiple_repos(
        self, repo_specs: list[dict[str, Any]], output_dir: str = "docs"
    ) -> dict[str, Any]:
        """
        Complete workflow for multiple repositories: ingest, build features, create graph, generate docs.

        Args:
            repo_specs: List of dicts with 'owner' and 'repo' keys
            output_dir: Output directory for documentation

        Returns:
            Complete workflow results
        """
        logger.info("="*60)
        logger.info(f"Starting multi-repo workflow for {len(repo_specs)} repositories")
        logger.info("="*60)

        # Step 1: Ingest all repositories
        logger.info("\n[Step 1] Ingesting repositories...")
        ingest_results = await self.ingest_multiple_repos(repo_specs)

        if ingest_results["failed"] > 0:
            logger.warning(
                f"{ingest_results['failed']} repositories failed to ingest"
            )

        # Step 2: Get repository IDs
        repo_ids = []
        for spec in repo_specs:
            repo = (
                self.db.query(Repository)
                .filter(
                    Repository.owner == spec["owner"],
                    Repository.name == spec["repo"],
                )
                .first()
            )
            if repo:
                repo_ids.append(repo.id)

        logger.info(f"Found {len(repo_ids)} repositories in database")

        # Step 3: Build unified graph
        logger.info("\n[Step 2] Building unified knowledge graph...")
        graph_result = await self.build_unified_graph(repo_ids)

        # Step 4: Generate documentation
        logger.info("\n[Step 3] Generating documentation...")
        docs_result = await self.orchestrator.execute_task(
            TaskType.GENERATE_DOCS,
            {"graph": graph_result["graph"], "output_dir": output_dir},
        )

        logger.info("\n" + "="*60)
        logger.info("Multi-repo workflow complete!")
        logger.info("="*60)
        logger.info(f"Repositories: {', '.join(graph_result['repositories'])}")
        logger.info(f"Features: {graph_result['total_features']}")
        logger.info(
            f"Graph: {graph_result['validation']['node_count']} nodes, "
            f"{graph_result['validation']['edge_count']} edges"
        )
        logger.info(f"Documentation: {output_dir}/")

        return {
            "ingestion": ingest_results,
            "graph": graph_result,
            "documentation": docs_result,
        }
