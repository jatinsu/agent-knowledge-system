from typing import Any
from sqlalchemy.orm import Session

from src.db.models import Feature, PullRequest, Issue, FeaturePRAssociation
from src.graph.types import Node, Edge, NodeType, EdgeType, KnowledgeGraph


class FeatureBuilder:
    def __init__(self, db: Session):
        self.db = db

    def get_jira_records_for_pr(self, pr: PullRequest) -> list[dict[str, Any]]:
        records = []
        for key in [pr.epic_key, pr.story_key, pr.task_key]:
            if key:
                issue = self.db.query(Issue).filter(Issue.key == key).first()
                if issue:
                    records.append({
                        "key": issue.key,
                        "title": issue.summary,
                        "type": issue.issue_type.name if issue.issue_type else "Unknown",
                        "status": issue.status,
                    })
        return records

    def build_feature_from_pr(self, pr: PullRequest) -> Feature:
        existing_feature = (
            self.db.query(Feature)
            .join(FeaturePRAssociation)
            .filter(FeaturePRAssociation.pr_id == pr.id)
            .first()
        )

        if existing_feature:
            return existing_feature

        feature = Feature(
            repo_id=pr.repo_id,
            name=pr.title,
            description=pr.description,
            components=pr.files_changed,
        )
        self.db.add(feature)
        self.db.flush()

        assoc = FeaturePRAssociation(feature_id=feature.id, pr_id=pr.id)
        self.db.add(assoc)

        self.db.commit()
        self.db.refresh(feature)
        return feature

    def build_features_from_repo(self, repo_id: int) -> list[Feature]:
        prs = self.db.query(PullRequest).filter(PullRequest.repo_id == repo_id).all()

        features = []
        for pr in prs:
            feature = self.build_feature_from_pr(pr)
            features.append(feature)

        return features


class GraphBuilder:
    def __init__(self):
        self.graph = KnowledgeGraph()
        self.node_counter = 0
        self.edge_counter = 0

    def _generate_node_id(self, prefix: str = "node") -> str:
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"

    def _generate_edge_id(self) -> str:
        self.edge_counter += 1
        return f"edge_{self.edge_counter}"

    def create_concept_node(
        self, title: str, description: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("concept"),
            type=NodeType.CONCEPT,
            title=title,
            description=description,
            metadata=metadata or {},
        )
        self.graph.add_node(node)
        return node

    def create_workflow_node(
        self, title: str, description: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("workflow"),
            type=NodeType.WORKFLOW,
            title=title,
            description=description,
            metadata=metadata or {},
        )
        self.graph.add_node(node)
        return node

    def create_adr_node(
        self, title: str, content: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("adr"),
            type=NodeType.ADR,
            title=title,
            content=content,
            metadata=metadata or {},
        )
        self.graph.add_node(node)
        return node

    def create_execution_plan_node(
        self, title: str, content: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("plan"),
            type=NodeType.EXECUTION_PLAN,
            title=title,
            content=content,
            metadata=metadata or {},
        )
        self.graph.add_node(node)
        return node

    def create_entry_point_node(
        self, title: str, description: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("entry"),
            type=NodeType.ENTRY_POINT,
            title=title,
            description=description,
            metadata=metadata or {},
        )
        self.graph.add_node(node)
        return node

    def create_document_node(
        self, title: str, file_path: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        node = Node(
            id=self._generate_node_id("doc"),
            type=NodeType.DOCUMENT,
            title=title,
            metadata={**(metadata or {}), "file_path": file_path},
        )
        self.graph.add_node(node)
        return node

    def link_nodes(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        metadata: dict[str, Any] | None = None,
    ) -> Edge:
        edge = Edge(
            id=self._generate_edge_id(),
            type=edge_type,
            source=source_id,
            target=target_id,
            metadata=metadata or {},
        )
        self.graph.add_edge(edge)
        return edge

    def build_feature_subgraph(self, feature: Feature, db: Session) -> Node:
        feature_builder = FeatureBuilder(db)
        jira_records = []
        for pr in feature.pull_requests:
            jira_records.extend(feature_builder.get_jira_records_for_pr(pr))

        feature_concept = self.create_concept_node(
            title=feature.name,
            description=feature.description or "Feature implementation",
            metadata={
                "feature_id": feature.id,
                "components": feature.components,
                "pr_count": len(feature.pull_requests),
                "jira_count": len(jira_records),
            },
        )

        for pr in feature.pull_requests:
            pr_node = Node(
                id=self._generate_node_id("pr"),
                type=NodeType.SECTION,
                title=f"PR #{pr.pr_number}: {pr.title}",
                metadata={
                    "pr_id": pr.id,
                    "pr_number": pr.pr_number,
                    "author": pr.author,
                    "files_changed": pr.files_changed,
                },
            )
            self.graph.add_node(pr_node)
            self.link_nodes(feature_concept.id, pr_node.id, EdgeType.REFERENCES)

        for jira_rec in jira_records:
            ticket_node = Node(
                id=self._generate_node_id("jira"),
                type=NodeType.SECTION,
                title=f"{jira_rec['key']}: {jira_rec['title']}",
                metadata={
                    "key": jira_rec["key"],
                    "type": jira_rec["type"],
                },
            )
            self.graph.add_node(ticket_node)
            self.link_nodes(feature_concept.id, ticket_node.id, EdgeType.DECIDED_BY)

        return feature_concept

    def build_from_features(self, features: list[Feature], db: Session) -> KnowledgeGraph:
        agents_entry = self.create_entry_point_node(
            title="AGENTS.md",
            description="Repository documentation entry point",
            metadata={"file_path": "docs/AGENTS.md"},
        )

        for feature in features:
            feature_node = self.build_feature_subgraph(feature, db)
            self.link_nodes(agents_entry.id, feature_node.id, EdgeType.INDEXES)

        return self.graph
