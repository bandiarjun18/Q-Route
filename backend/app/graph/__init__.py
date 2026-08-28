"""
app/graph/__init__.py – Public API for the Q-Route graph engine.

Import from here rather than from sub-modules directly:

    from app.graph import TransportGraph, WeightConfig, shortest_path
    from app.graph import generate_synthetic_network, build_transport_graph
"""

from .model import TransportGraph, WeightConfig
from .generator import (
    generate_synthetic_network,
    save_network_json,
    load_network_json,
    build_transport_graph,
)
from .pathfinding import shortest_path, path_cost

__all__ = [
    # Model
    "TransportGraph",
    "WeightConfig",
    # Generator
    "generate_synthetic_network",
    "save_network_json",
    "load_network_json",
    "build_transport_graph",
    # Pathfinding
    "shortest_path",
    "path_cost",
]
