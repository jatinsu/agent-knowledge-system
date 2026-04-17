import json
import time
from typing import Any, List, Tuple
from collections import deque

from src.gateway.llm_gateway import LLMGateway
from src.graph.types import KnowledgeGraph, Node, NodeType, EdgeType
from src.config import settings
from src.utils.logger import setup_logger, log_graph_query

logger = setup_logger(__name__)


class RetrievalAgent:
    def __init__(self, llm_gateway: LLMGateway, graph: KnowledgeGraph):
        self.gateway = llm_gateway
        self.graph = graph
        self.agent_id = "retrieval_agent"
        self.max_hops = settings.max_graph_hops
        self.max_context_lines = settings.max_context_lines

    async def classify_intent(self, query: str) -> str:
        system_prompt = """Classify the user's query intent into one of these categories:
- CONCEPT: Looking for understanding of a domain concept or abstraction
- WORKFLOW: Looking for process flows or interaction patterns
- DECISION: Looking for why something was decided (ADR)
- IMPLEMENTATION: Looking for how to implement something (Execution Plan)
- GENERAL: General exploration or unclear intent

Respond with only the category name."""

        intent = await self.gateway.generate(
            f"{system_prompt}\n\nQuery: {query}",
            agent_id=self.agent_id,
            task_type="intent_classification",
            temperature=0.3,
        )

        return intent.strip().upper()

    async def extract_entities(self, query: str) -> list[str]:
        """Extract key entities from query using LLM."""
        system_prompt = """Extract key entities, terms, or concepts from the query.
Return a JSON list of strings representing the main entities.
Example: ["authentication", "user login", "session management"]"""

        entities_json = await self.gateway.generate(
            f"{system_prompt}\n\nQuery: {query}",
            agent_id=self.agent_id,
            task_type="entity_extraction",
            temperature=0.3,
        )

        try:
            entities = json.loads(entities_json)
            return entities if isinstance(entities, list) else []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse entities JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error extracting entities: {e}")
            return []

    def resolve_nodes(self, entities: list[str]) -> list[Node]:
        matched_nodes = []

        for entity in entities:
            entity_lower = entity.lower()
            for node in self.graph.nodes:
                if (
                    entity_lower in node.title.lower()
                    or (node.description and entity_lower in node.description.lower())
                ):
                    if node not in matched_nodes:
                        matched_nodes.append(node)

        return matched_nodes

    def _calculate_relevance_score(self, node: Node, entities: list[str]) -> float:
        """
        Calculate relevance score for a node based on entity matches.

        Returns a score between 0.0 and 1.0.
        """
        score = 0.0
        text = f"{node.title} {node.description or ''} {str(node.metadata)}".lower()

        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in text:
                # Title match worth more than description
                if entity_lower in node.title.lower():
                    score += 0.5
                else:
                    score += 0.2

        return min(score, 1.0)

    def bfs_traverse(self, start_nodes: list[Node], max_hops: int = 3, entities: list[str] = None) -> list[Node]:
        """
        BFS traversal with relevance filtering to avoid pulling entire graph.

        Args:
            start_nodes: Starting points for traversal
            max_hops: Maximum hops from start nodes
            entities: Query entities for relevance scoring

        Returns:
            List of relevant nodes
        """
        start_time = time.time()

        if max_hops > self.max_hops:
            max_hops = self.max_hops

        if entities is None:
            entities = []

        visited = set()
        result_with_scores: List[Tuple[Node, float, int]] = []  # (node, score, depth)
        queue: deque[tuple[Node, int]] = deque()

        # Initialize with start nodes
        for node in start_nodes:
            queue.append((node, 0))
            visited.add(node.id)

        max_results = 50  # Limit total results to avoid pulling entire graph

        while queue and len(result_with_scores) < max_results:
            current_node, depth = queue.popleft()

            # Calculate relevance score
            relevance = self._calculate_relevance_score(current_node, entities)

            # Add to results
            result_with_scores.append((current_node, relevance, depth))

            if depth >= max_hops:
                continue

            # Prioritize certain edge types for traversal
            priority_edges = [EdgeType.DEEP_DIVE, EdgeType.DECIDED_BY, EdgeType.PLANNED_IN]

            # Get outgoing edges
            outgoing_edges = self.graph.get_edges_from(current_node.id)

            # Sort edges by priority
            sorted_edges = sorted(
                outgoing_edges,
                key=lambda e: 0 if e.type in priority_edges else 1
            )

            for edge in sorted_edges:
                target_node = self.graph.get_node(edge.target)
                if target_node and target_node.id not in visited:
                    # Skip entry point nodes unless at depth 0
                    if target_node.type == NodeType.ENTRY_POINT and depth > 0:
                        continue

                    visited.add(target_node.id)
                    queue.append((target_node, depth + 1))

            # Get incoming edges (more selective)
            incoming_edges = self.graph.get_edges_to(current_node.id)

            # Only follow high-priority incoming edges
            for edge in incoming_edges:
                if edge.type not in priority_edges:
                    continue

                source_node = self.graph.get_node(edge.source)
                if source_node and source_node.id not in visited:
                    if source_node.type == NodeType.ENTRY_POINT and depth > 0:
                        continue

                    visited.add(source_node.id)
                    queue.append((source_node, depth + 1))

        # Sort by relevance score
        result_with_scores.sort(key=lambda x: (x[1], -x[2]), reverse=True)

        # Extract just the nodes
        result = [node for node, score, depth in result_with_scores]

        duration_ms = (time.time() - start_time) * 1000

        log_graph_query(
            "bfs_traverse",
            f"start_nodes={len(start_nodes)}, max_hops={max_hops}",
            result_count=len(result),
            duration_ms=duration_ms
        )

        logger.info(
            f"BFS traversal: {len(start_nodes)} start nodes → {len(result)} results "
            f"(max_hops={max_hops}, visited={len(visited)})"
        )

        return result

    def compress_context(self, nodes: list[Node]) -> str:
        lines = []

        for node in nodes:
            lines.append(f"# {node.type.value}: {node.title}")
            if node.description:
                lines.append(f"Description: {node.description}")
            if node.content:
                content_lines = node.content.split("\n")[:20]
                lines.extend(content_lines)
            lines.append("")

            if len(lines) >= self.max_context_lines:
                break

        return "\n".join(lines[: self.max_context_lines])

    async def retrieve(self, query: str) -> dict[str, Any]:
        """Retrieve relevant context from knowledge graph for a query."""
        start_time = time.time()

        logger.info(f"Retrieving context for query: {query[:100]}")

        intent = await self.classify_intent(query)
        entities = await self.extract_entities(query)

        start_nodes = self.resolve_nodes(entities)

        if not start_nodes:
            logger.info("No direct entity matches, using entry points")
            start_nodes = [n for n in self.graph.nodes if n.type == NodeType.ENTRY_POINT][:1]

        related_nodes = self.bfs_traverse(start_nodes, max_hops=self.max_hops, entities=entities)

        context = self.compress_context(related_nodes)

        duration_ms = (time.time() - start_time) * 1000

        log_graph_query(
            "retrieve",
            query[:100],
            result_count=len(related_nodes),
            duration_ms=duration_ms
        )

        logger.info(
            f"Retrieved {len(related_nodes)} nodes, {len(context.split('\n'))} lines "
            f"in {duration_ms:.2f}ms"
        )

        return {
            "intent": intent,
            "entities": entities,
            "matched_nodes": len(start_nodes),
            "related_nodes": len(related_nodes),
            "context": context,
            "context_lines": len(context.split("\n")),
        }
