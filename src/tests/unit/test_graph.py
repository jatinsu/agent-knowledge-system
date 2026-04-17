import pytest

from src.graph.types import (
    KnowledgeGraph,
    Node,
    Edge,
    NodeType,
    EdgeType,
)
from src.graph.builders import GraphBuilder


def test_knowledge_graph_creation():
    graph = KnowledgeGraph()
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert graph.version == "0.1.0"


def test_add_node():
    graph = KnowledgeGraph()
    node = Node(
        id="test_1",
        type=NodeType.CONCEPT,
        title="Test Concept",
        description="A test concept",
    )
    graph.add_node(node)

    assert len(graph.nodes) == 1
    assert graph.get_node("test_1") == node


def test_add_duplicate_node():
    graph = KnowledgeGraph()
    node1 = Node(id="test_1", type=NodeType.CONCEPT, title="Test")
    node2 = Node(id="test_1", type=NodeType.CONCEPT, title="Test Duplicate")

    graph.add_node(node1)
    graph.add_node(node2)

    assert len(graph.nodes) == 1


def test_add_edge():
    graph = KnowledgeGraph()
    node1 = Node(id="node1", type=NodeType.CONCEPT, title="Node 1")
    node2 = Node(id="node2", type=NodeType.CONCEPT, title="Node 2")

    graph.add_node(node1)
    graph.add_node(node2)

    edge = Edge(id="edge1", type=EdgeType.RELATED, source="node1", target="node2")
    graph.add_edge(edge)

    assert len(graph.edges) == 1
    assert graph.get_edges_from("node1")[0] == edge
    assert graph.get_edges_to("node2")[0] == edge


def test_validate_graph_no_orphans():
    graph = KnowledgeGraph()
    node1 = Node(id="node1", type=NodeType.ENTRY_POINT, title="Entry")
    node2 = Node(id="node2", type=NodeType.CONCEPT, title="Concept")

    graph.add_node(node1)
    graph.add_node(node2)

    edge = Edge(id="edge1", type=EdgeType.INDEXES, source="node1", target="node2")
    graph.add_edge(edge)

    validation = graph.validate_graph()
    assert validation["valid"] is True
    assert len(validation["orphan_nodes"]) == 0


def test_validate_graph_with_orphans():
    graph = KnowledgeGraph()
    node1 = Node(id="node1", type=NodeType.CONCEPT, title="Orphan")
    graph.add_node(node1)

    validation = graph.validate_graph()
    assert validation["valid"] is False
    assert "node1" in validation["orphan_nodes"]


def test_graph_builder():
    builder = GraphBuilder()

    concept = builder.create_concept_node("Authentication", "User auth system")
    adr = builder.create_adr_node("ADR: OAuth2", "Decision to use OAuth2")

    builder.link_nodes(concept.id, adr.id, EdgeType.DECIDED_BY)

    assert len(builder.graph.nodes) == 2
    assert len(builder.graph.edges) == 1
    assert builder.graph.get_node(concept.id) is not None


def test_graph_builder_unique_ids():
    builder = GraphBuilder()

    node1 = builder.create_concept_node("Concept 1", "Description 1")
    node2 = builder.create_concept_node("Concept 2", "Description 2")

    assert node1.id != node2.id
