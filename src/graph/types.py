from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    CONCEPT = "Concept"
    WORKFLOW = "Workflow"
    ADR = "ADR"
    EXECUTION_PLAN = "ExecutionPlan"
    ENTRY_POINT = "EntryPoint"
    DOCUMENT = "Document"
    SECTION = "Section"


class EdgeType(str, Enum):
    DEEP_DIVE = "DEEP_DIVE"
    RELATED = "RELATED"
    DECIDED_BY = "DECIDED_BY"
    PLANNED_IN = "PLANNED_IN"
    REFERENCES = "REFERENCES"
    INDEXES = "INDEXES"


class Node(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    type: NodeType
    title: str
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: Optional[str] = None


class Edge(BaseModel):
    id: str = Field(..., description="Unique edge identifier")
    type: EdgeType
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        if not any(e.id == edge.id for e in self.edges):
            self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_edges_from(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def validate_graph(self) -> dict[str, Any]:
        orphan_nodes = []
        for node in self.nodes:
            incoming = self.get_edges_to(node.id)
            outgoing = self.get_edges_from(node.id)
            if not incoming and not outgoing and node.type != NodeType.ENTRY_POINT:
                orphan_nodes.append(node.id)

        dangling_edges = []
        for edge in self.edges:
            if not self.get_node(edge.source) or not self.get_node(edge.target):
                dangling_edges.append(edge.id)

        return {
            "valid": len(orphan_nodes) == 0 and len(dangling_edges) == 0,
            "orphan_nodes": orphan_nodes,
            "dangling_edges": dangling_edges,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }
