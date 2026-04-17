"""NetworkX adapter for knowledge graph analysis."""

import time
from typing import Any, List, Dict, Set
import networkx as nx

from src.graph.types import KnowledgeGraph, Node, NodeType, EdgeType
from src.utils.logger import setup_logger, log_networkx_query

logger = setup_logger(__name__)


class NetworkXGraphAdapter:
    """
    Adapter to convert KnowledgeGraph to NetworkX for advanced analysis.

    Provides graph algorithms, path finding, centrality measures, and
    community detection on the knowledge graph.
    """

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.nx_graph = self._build_networkx_graph()
        logger.info(f"NetworkX graph created: {len(self.nx_graph.nodes())} nodes, {len(self.nx_graph.edges())} edges")

    def _build_networkx_graph(self) -> nx.DiGraph:
        """Convert KnowledgeGraph to NetworkX DiGraph."""
        start_time = time.time()
        G = nx.DiGraph()

        # Add nodes with attributes
        for node in self.kg.nodes:
            G.add_node(
                node.id,
                type=node.type.value,
                title=node.title,
                description=node.description,
                metadata=node.metadata,
            )

        # Add edges with attributes
        for edge in self.kg.edges:
            G.add_edge(
                edge.source,
                edge.target,
                type=edge.type.value,
                edge_id=edge.id,
                metadata=edge.metadata,
            )

        duration_ms = (time.time() - start_time) * 1000
        log_networkx_query(
            "build_graph",
            {"nodes": len(G.nodes()), "edges": len(G.edges())},
            result_count=len(G.nodes())
        )

        return G

    def find_shortest_path(self, source_id: str, target_id: str) -> List[str]:
        """Find shortest path between two nodes."""
        start_time = time.time()

        try:
            path = nx.shortest_path(self.nx_graph, source_id, target_id)
            duration_ms = (time.time() - start_time) * 1000

            log_networkx_query(
                "shortest_path",
                {"source": source_id, "target": target_id},
                result_count=len(path)
            )

            logger.info(f"Shortest path: {len(path)} hops from {source_id} to {target_id}")
            return path
        except nx.NetworkXNoPath:
            logger.warning(f"No path found from {source_id} to {target_id}")
            return []
        except nx.NodeNotFound as e:
            logger.error(f"Node not found: {e}")
            return []

    def find_all_paths(self, source_id: str, target_id: str, cutoff: int = 5) -> List[List[str]]:
        """Find all paths between two nodes up to a cutoff length."""
        start_time = time.time()

        try:
            paths = list(nx.all_simple_paths(self.nx_graph, source_id, target_id, cutoff=cutoff))
            duration_ms = (time.time() - start_time) * 1000

            log_networkx_query(
                "all_paths",
                {"source": source_id, "target": target_id, "cutoff": cutoff},
                result_count=len(paths)
            )

            logger.info(f"Found {len(paths)} paths from {source_id} to {target_id}")
            return paths
        except nx.NodeNotFound as e:
            logger.error(f"Node not found: {e}")
            return []

    def get_node_centrality(self, metric: str = "betweenness") -> Dict[str, float]:
        """
        Calculate node centrality measures.

        Args:
            metric: One of 'betweenness', 'closeness', 'degree', 'pagerank'

        Returns:
            Dictionary mapping node IDs to centrality scores
        """
        start_time = time.time()

        if metric == "betweenness":
            centrality = nx.betweenness_centrality(self.nx_graph)
        elif metric == "closeness":
            centrality = nx.closeness_centrality(self.nx_graph)
        elif metric == "degree":
            centrality = nx.degree_centrality(self.nx_graph)
        elif metric == "pagerank":
            centrality = nx.pagerank(self.nx_graph)
        else:
            raise ValueError(f"Unknown metric: {metric}")

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            f"{metric}_centrality",
            {"metric": metric},
            result_count=len(centrality)
        )

        # Log top 5
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info(f"{metric.capitalize()} centrality (top 5):")
        for node_id, score in top_nodes:
            node = self.kg.get_node(node_id)
            title = node.title if node else node_id
            logger.info(f"  {title[:50]}: {score:.4f}")

        return centrality

    def get_connected_components(self) -> List[Set[str]]:
        """Get weakly connected components."""
        start_time = time.time()

        components = list(nx.weakly_connected_components(self.nx_graph))
        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "connected_components",
            {},
            result_count=len(components)
        )

        logger.info(f"Found {len(components)} connected components")
        for i, comp in enumerate(components, 1):
            logger.info(f"  Component {i}: {len(comp)} nodes")

        return components

    def get_neighbors(self, node_id: str, depth: int = 1) -> Set[str]:
        """Get all neighbors within a given depth."""
        start_time = time.time()

        if node_id not in self.nx_graph:
            logger.warning(f"Node {node_id} not in graph")
            return set()

        neighbors = set([node_id])

        for _ in range(depth):
            new_neighbors = set()
            for n in neighbors:
                # Both predecessors and successors
                new_neighbors.update(self.nx_graph.predecessors(n))
                new_neighbors.update(self.nx_graph.successors(n))
            neighbors.update(new_neighbors)

        neighbors.remove(node_id)  # Remove the starting node

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "get_neighbors",
            {"node_id": node_id, "depth": depth},
            result_count=len(neighbors)
        )

        logger.info(f"Found {len(neighbors)} neighbors within depth {depth}")

        return neighbors

    def get_subgraph_by_type(self, node_types: List[NodeType]) -> nx.DiGraph:
        """Extract a subgraph containing only specific node types."""
        start_time = time.time()

        type_values = [t.value for t in node_types]
        nodes_to_include = [
            n for n, attrs in self.nx_graph.nodes(data=True)
            if attrs.get("type") in type_values
        ]

        subgraph = self.nx_graph.subgraph(nodes_to_include).copy()

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "subgraph_by_type",
            {"types": [t.value for t in node_types]},
            result_count=len(subgraph.nodes())
        )

        logger.info(
            f"Subgraph created: {len(subgraph.nodes())} nodes, "
            f"{len(subgraph.edges())} edges"
        )

        return subgraph

    def find_hubs(self, top_n: int = 10) -> List[tuple[str, int]]:
        """Find hub nodes (nodes with highest degree)."""
        start_time = time.time()

        degrees = dict(self.nx_graph.degree())
        hubs = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:top_n]

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "find_hubs",
            {"top_n": top_n},
            result_count=len(hubs)
        )

        logger.info(f"Top {top_n} hubs:")
        for node_id, degree in hubs:
            node = self.kg.get_node(node_id)
            title = node.title if node else node_id
            logger.info(f"  {title[:50]}: degree={degree}")

        return hubs

    def analyze_graph_metrics(self) -> Dict[str, Any]:
        """Compute comprehensive graph metrics."""
        start_time = time.time()

        metrics = {
            "nodes": len(self.nx_graph.nodes()),
            "edges": len(self.nx_graph.edges()),
            "density": nx.density(self.nx_graph),
            "is_directed": self.nx_graph.is_directed(),
            "is_dag": nx.is_directed_acyclic_graph(self.nx_graph),
        }

        # Components
        try:
            components = list(nx.weakly_connected_components(self.nx_graph))
            metrics["num_components"] = len(components)
            metrics["largest_component_size"] = len(max(components, key=len))
        except:
            metrics["num_components"] = 0
            metrics["largest_component_size"] = 0

        # Average degree
        degrees = [d for n, d in self.nx_graph.degree()]
        if degrees:
            metrics["average_degree"] = sum(degrees) / len(degrees)
        else:
            metrics["average_degree"] = 0

        # Clustering (for undirected version)
        try:
            undirected = self.nx_graph.to_undirected()
            metrics["average_clustering"] = nx.average_clustering(undirected)
        except:
            metrics["average_clustering"] = 0

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "analyze_metrics",
            {},
            result_count=len(metrics)
        )

        logger.info("Graph Metrics:")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value}")

        return metrics

    def find_cycles(self, max_cycles: int = 10) -> List[List[str]]:
        """Find cycles in the graph."""
        start_time = time.time()

        try:
            cycles = list(nx.simple_cycles(self.nx_graph))[:max_cycles]
        except:
            cycles = []

        duration_ms = (time.time() - start_time) * 1000

        log_networkx_query(
            "find_cycles",
            {"max_cycles": max_cycles},
            result_count=len(cycles)
        )

        logger.info(f"Found {len(cycles)} cycles (showing up to {max_cycles})")

        return cycles
