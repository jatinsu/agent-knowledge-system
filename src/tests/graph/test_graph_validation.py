import pytest

from src.graph.types import KnowledgeGraph, Node, Edge, NodeType, EdgeType
from src.graph.builders import GraphBuilder


def test_no_orphan_nodes():
    builder = GraphBuilder()

    entry = builder.create_entry_point_node("AGENTS.md", "Entry point")
    concept1 = builder.create_concept_node("Feature A", "Description A")
    concept2 = builder.create_concept_node("Feature B", "Description B")

    builder.link_nodes(entry.id, concept1.id, EdgeType.INDEXES)
    builder.link_nodes(entry.id, concept2.id, EdgeType.INDEXES)

    validation = builder.graph.validate_graph()
    assert validation["valid"] is True
    assert len(validation["orphan_nodes"]) == 0


def test_reachability_within_3_hops():
    builder = GraphBuilder()

    entry = builder.create_entry_point_node("AGENTS.md", "Entry")
    concept = builder.create_concept_node("Concept", "A concept")
    adr = builder.create_adr_node("ADR", "A decision")
    plan = builder.create_execution_plan_node("Plan", "An execution plan")

    builder.link_nodes(entry.id, concept.id, EdgeType.INDEXES)
    builder.link_nodes(concept.id, adr.id, EdgeType.DECIDED_BY)
    builder.link_nodes(adr.id, plan.id, EdgeType.PLANNED_IN)

    from collections import deque

    visited = set()
    queue = deque([(entry.id, 0)])
    visited.add(entry.id)

    max_depth = 0
    while queue:
        node_id, depth = queue.popleft()
        max_depth = max(max_depth, depth)

        edges = builder.graph.get_edges_from(node_id)
        for edge in edges:
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append((edge.target, depth + 1))

    assert max_depth <= 3
    assert len(visited) == 4


def test_node_edge_typing():
    builder = GraphBuilder()

    concept = builder.create_concept_node("Test", "Test")
    assert concept.type == NodeType.CONCEPT

    adr = builder.create_adr_node("ADR", "ADR")
    assert adr.type == NodeType.ADR

    edge = builder.link_nodes(concept.id, adr.id, EdgeType.DECIDED_BY)
    assert edge.type == EdgeType.DECIDED_BY


def test_dangling_edges():
    graph = KnowledgeGraph()

    node = Node(id="node1", type=NodeType.CONCEPT, title="Test")
    graph.add_node(node)

    edge = Edge(id="edge1", type=EdgeType.RELATED, source="node1", target="nonexistent")
    graph.add_edge(edge)

    validation = graph.validate_graph()
    assert validation["valid"] is False
    assert "edge1" in validation["dangling_edges"]
