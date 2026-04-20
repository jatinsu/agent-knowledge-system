from enum import Enum
from typing import Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session

from src.gateway.llm_gateway import LLMGateway
from src.graph.types import KnowledgeGraph
from src.graph.builders import FeatureBuilder, GraphBuilder
from src.graph.storage import GraphStorage
from src.agents.doc_generator import DocumentationGenerator
from src.ingestors.github_ingestor import GitHubIngestor
from src.ingestors.jira_ingestor import JiraIngestor


class TaskType(str, Enum):
    INGEST_GITHUB = "ingest_github"
    INGEST_JIRA = "ingest_jira"
    BUILD_FEATURES = "build_features"
    BUILD_GRAPH = "build_graph"
    GENERATE_DOCS = "generate_docs"
    RETRIEVE = "retrieve"
    VALIDATE = "validate"


class RouterOrchestrator:
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

        self.github_ingestor = GitHubIngestor(github_token) if github_token else None
        self.jira_ingestor = (
            JiraIngestor(jira_url, jira_email, jira_token)
            if jira_url and jira_email and jira_token
            else None
        )

        self.feature_builder = FeatureBuilder(db)
        self.graph_builder = GraphBuilder()
        self.graph_storage = GraphStorage()
        self.doc_generator = DocumentationGenerator(llm_gateway)

    async def execute_task(self, task_type: TaskType, params: dict[str, Any]) -> dict[str, Any]:
        if task_type == TaskType.INGEST_GITHUB:
            return await self._ingest_github(params)
        elif task_type == TaskType.INGEST_JIRA:
            return await self._ingest_jira(params)
        elif task_type == TaskType.BUILD_FEATURES:
            return await self._build_features(params)
        elif task_type == TaskType.BUILD_GRAPH:
            return await self._build_graph(params)
        elif task_type == TaskType.GENERATE_DOCS:
            return await self._generate_docs(params)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    async def _ingest_github(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.github_ingestor:
            raise ValueError("GitHub ingestor not configured")

        owner = params["owner"]
        repo = params["repo"]
        limit = params.get("limit", 100)

        prs = await self.github_ingestor.ingest_pull_requests(owner, repo, self.db, limit)

        return {"status": "success", "pr_count": len(prs)}

    async def _ingest_jira(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.jira_ingestor:
            raise ValueError("Jira ingestor not configured")

        if "keys" in params:
            issue_type = params.get("issue_type", "epic")
            records = await self.jira_ingestor.ingest_issues_by_keys(
                params["keys"], issue_type, self.db
            )
            return {"status": "success", "ticket_count": len(records)}

        counts = await self.jira_ingestor.ingest_from_prs(self.db)
        return {"status": "success", **counts}

    async def _build_features(self, params: dict[str, Any]) -> dict[str, Any]:
        repo_id = params["repo_id"]
        features = self.feature_builder.build_features_from_repo(repo_id)

        return {"status": "success", "feature_count": len(features)}

    async def _build_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        features = params["features"]

        graph = self.graph_builder.build_from_features(features, self.db)
        self.graph_storage.save(graph)

        validation = graph.validate_graph()

        return {
            "status": "success",
            "graph": graph,
            "validation": validation,
        }

    async def _generate_docs(self, params: dict[str, Any]) -> dict[str, Any]:
        graph: KnowledgeGraph = params["graph"]
        output_dir = Path(params.get("output_dir", "docs"))

        agents_path = await self.doc_generator.generate_agents_md(
            graph, output_dir / "AGENTS.md"
        )
        arch_path = await self.doc_generator.generate_architecture_md(
            graph, output_dir / "ARCHITECTURE.md"
        )

        return {
            "status": "success",
            "agents_md": str(agents_path),
            "architecture_md": str(arch_path),
        }
