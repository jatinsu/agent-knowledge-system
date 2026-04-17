import pytest
from unittest.mock import Mock, AsyncMock

from src.graph.types import KnowledgeGraph, NodeType
from src.graph.builders import GraphBuilder
from src.agents.validation import ValidationAgent


@pytest.mark.asyncio
async def test_minimum_coverage():
    builder = GraphBuilder()

    entry = builder.create_entry_point_node("AGENTS.md", "Entry")

    for i in range(5):
        concept = builder.create_concept_node(f"Concept {i}", f"Description {i}")
        builder.link_nodes(entry.id, concept.id, "INDEXES")

    for i in range(3):
        adr = builder.create_adr_node(f"ADR {i}", f"Content {i}")
        builder.link_nodes(entry.id, adr.id, "INDEXES")

    mock_gateway = Mock()
    validator = ValidationAgent(mock_gateway)

    result = validator.validate_graph(builder.graph)

    assert result["coverage"]["concepts"] >= 5
    assert result["coverage"]["adrs"] >= 3
    assert result["coverage"]["meets_minimum"] is True


@pytest.mark.asyncio
async def test_context_budget_compliance():
    from src.agents.retrieval import RetrievalAgent

    builder = GraphBuilder()
    entry = builder.create_entry_point_node("AGENTS.md", "Entry")

    for i in range(20):
        concept = builder.create_concept_node(
            f"Concept {i}", "Description " * 100
        )
        builder.link_nodes(entry.id, concept.id, "INDEXES")

    mock_gateway = Mock()
    mock_gateway.generate = AsyncMock(return_value="CONCEPT")
    retrieval = RetrievalAgent(mock_gateway, builder.graph)

    result = await retrieval.retrieve("test query")

    assert result["context_lines"] <= 700


@pytest.mark.asyncio
async def test_token_usage_measurement():
    mock_gateway = Mock()
    mock_gateway.generate = AsyncMock(return_value='["test"]')
    mock_gateway.request_log = []

    from src.agents.retrieval import RetrievalAgent

    builder = GraphBuilder()
    entry = builder.create_entry_point_node("AGENTS.md", "Entry")
    concept = builder.create_concept_node("Test", "Description")
    builder.link_nodes(entry.id, concept.id, "INDEXES")

    retrieval = RetrievalAgent(mock_gateway, builder.graph)

    await retrieval.retrieve("test query")

    assert mock_gateway.generate.call_count >= 1
