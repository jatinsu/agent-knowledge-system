"""Graph analysis CLI commands using NetworkX."""

import asyncio
import warnings

# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import click

from src.graph.storage import GraphStorage
from src.graph.networkx_adapter import NetworkXGraphAdapter
from src.graph.types import NodeType


@click.group()
def graph_analysis_cli():
    """Advanced graph analysis using NetworkX"""
    pass


@graph_analysis_cli.command(name="analyze")
def analyze_graph():
    """Analyze graph metrics using NetworkX"""
    storage = GraphStorage()
    graph = storage.load()

    if len(graph.nodes) == 0:
        click.echo("Error: No graph loaded. Run a workflow first.")
        return

    click.echo("Analyzing graph with NetworkX...")
    adapter = NetworkXGraphAdapter(graph)

    metrics = adapter.analyze_graph_metrics()

    click.echo("\n=== Graph Metrics ===")
    click.echo(f"Nodes: {metrics['nodes']}")
    click.echo(f"Edges: {metrics['edges']}")
    click.echo(f"Density: {metrics['density']:.4f}")
    click.echo(f"Average Degree: {metrics['average_degree']:.2f}")
    click.echo(f"Components: {metrics['num_components']}")
    click.echo(f"Largest Component: {metrics['largest_component_size']}")
    click.echo(f"Is DAG: {metrics['is_dag']}")
    click.echo(f"Average Clustering: {metrics['average_clustering']:.4f}")


@graph_analysis_cli.command(name="hubs")
@click.option("--top-n", default=10, help="Number of top hubs to show")
def find_hubs(top_n: int):
    """Find hub nodes (highest degree)"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    hubs = adapter.find_hubs(top_n=top_n)

    click.echo(f"\n=== Top {top_n} Hub Nodes ===")
    for node_id, degree in hubs:
        node = graph.get_node(node_id)
        if node:
            click.echo(f"{node.title[:60]}")
            click.echo(f"  Type: {node.type.value}, Degree: {degree}")


@graph_analysis_cli.command(name="centrality")
@click.option(
    "--metric",
    type=click.Choice(["betweenness", "closeness", "degree", "pagerank"]),
    default="betweenness",
    help="Centrality metric to calculate",
)
def calculate_centrality(metric: str):
    """Calculate node centrality measures"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    centrality = adapter.get_node_centrality(metric=metric)

    # Show top 10
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]

    click.echo(f"\n=== {metric.capitalize()} Centrality (Top 10) ===")
    for node_id, score in top_nodes:
        node = graph.get_node(node_id)
        if node:
            click.echo(f"{score:.4f} - {node.title[:60]}")


@graph_analysis_cli.command(name="path")
@click.option("--from-node", required=True, help="Source node ID")
@click.option("--to-node", required=True, help="Target node ID")
def shortest_path(from_node: str, to_node: str):
    """Find shortest path between two nodes"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    path = adapter.find_shortest_path(from_node, to_node)

    if path:
        click.echo(f"\n=== Shortest Path ({len(path)} hops) ===")
        for i, node_id in enumerate(path):
            node = graph.get_node(node_id)
            if node:
                click.echo(f"{i + 1}. {node.type.value}: {node.title[:60]}")
    else:
        click.echo("No path found between the nodes.")


@graph_analysis_cli.command(name="neighbors")
@click.option("--node-id", required=True, help="Node ID to find neighbors of")
@click.option("--depth", default=1, help="Depth to search")
def get_neighbors(node_id: str, depth: int):
    """Get neighbors of a node within given depth"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    neighbors = adapter.get_neighbors(node_id, depth=depth)

    click.echo(f"\n=== Neighbors (depth={depth}): {len(neighbors)} ===")
    for neighbor_id in list(neighbors)[:20]:  # Show first 20
        node = graph.get_node(neighbor_id)
        if node:
            click.echo(f"- {node.type.value}: {node.title[:60]}")

    if len(neighbors) > 20:
        click.echo(f"... and {len(neighbors) - 20} more")


@graph_analysis_cli.command(name="components")
def connected_components():
    """Find connected components in the graph"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    components = adapter.get_connected_components()

    click.echo(f"\n=== Connected Components: {len(components)} ===")
    for i, component in enumerate(components, 1):
        click.echo(f"\nComponent {i}: {len(component)} nodes")

        # Show a few example nodes
        for node_id in list(component)[:5]:
            node = graph.get_node(node_id)
            if node:
                click.echo(f"  - {node.title[:60]}")

        if len(component) > 5:
            click.echo(f"  ... and {len(component) - 5} more")


@graph_analysis_cli.command(name="cycles")
@click.option("--max-cycles", default=10, help="Maximum cycles to find")
def find_cycles(max_cycles: int):
    """Find cycles in the graph"""
    storage = GraphStorage()
    graph = storage.load()

    adapter = NetworkXGraphAdapter(graph)
    cycles = adapter.find_cycles(max_cycles=max_cycles)

    if cycles:
        click.echo(f"\n=== Found {len(cycles)} Cycles ===")
        for i, cycle in enumerate(cycles, 1):
            click.echo(f"\nCycle {i}: {len(cycle)} nodes")
            for node_id in cycle:
                node = graph.get_node(node_id)
                if node:
                    click.echo(f"  → {node.title[:50]}")
    else:
        click.echo("\nNo cycles found. Graph is acyclic (DAG).")


@graph_analysis_cli.command(name="versions")
def list_versions():
    """List all saved graph versions"""
    storage = GraphStorage()
    versions = storage.list_versions()

    if not versions:
        click.echo("No versions found.")
        return

    click.echo(f"\n=== Graph Versions ({len(versions)}) ===")
    for v in versions:
        click.echo(f"\nVersion: {v['version']}")
        click.echo(f"  File: {v['file']}")
        click.echo(f"  Saved: {v['saved_at']}")
        click.echo(f"  Nodes: {v['nodes']}, Edges: {v['edges']}")


@graph_analysis_cli.command(name="backups")
def list_backups():
    """List all backup files"""
    storage = GraphStorage()
    backups = storage.list_backups()

    if not backups:
        click.echo("No backups found.")
        return

    click.echo(f"\n=== Graph Backups ({len(backups)}) ===")
    for backup in backups:
        click.echo(f"  - {backup.name}")


if __name__ == "__main__":
    graph_analysis_cli()
