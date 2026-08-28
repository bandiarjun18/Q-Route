"""
app/graph/pathfinding.py – Shortest-path computation for Q-Route.

Public API
----------
shortest_path(tg, source, target, weight_config) -> (path, cost)
path_cost(tg, path, weight_config)               -> float

Closed-road exclusion
---------------------
Rather than returning a large sentinel value for closed edges, we build a
``networkx.subgraph_view`` that excludes closed edges entirely before calling
Dijkstra.  This ensures NetworkX never considers a closed edge — even as an
intermediate hop with zero weight — and lets nx.NetworkXNoPath propagate
naturally when no route exists.

The weight function passed to Dijkstra computes:
    cost = wT * (base_travel_time * congestion_factor)
         + wD * distance
         + wC * (congestion_factor - 1.0)
using the shared WeightConfig formula from model.py.
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from .model import TransportGraph, WeightConfig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _open_subgraph(tg: TransportGraph) -> nx.DiGraph:
    """
    Return a read-only view of the graph that contains only open edges.

    Uses networkx.subgraph_view so no data is copied; modifying the
    underlying TransportGraph is immediately reflected in the view.
    """
    g = tg.graph
    return nx.subgraph_view(
        g,
        filter_edge=lambda u, v: g[u][v].get("road_status") != TransportGraph.CLOSED,
    )


def _make_weight_fn(weight_config: WeightConfig):
    """
    Return a NetworkX-compatible weight callable.

    NetworkX passes (u, v, edge_data) to the function and uses the
    return value as the edge weight in Dijkstra.
    """
    def _fn(u: Any, v: Any, data: dict) -> float:
        return weight_config.edge_cost(
            data["distance"],
            data["base_travel_time"],
            data["congestion_factor"],
        )
    return _fn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def shortest_path(
    tg: TransportGraph,
    source: Any,
    target: Any,
    weight_config: WeightConfig | None = None,
) -> tuple[list, float]:
    """
    Find the minimum-cost path from ``source`` to ``target``.

    Closed edges are never used.

    Parameters
    ----------
    tg           : TransportGraph
    source       : node id
    target       : node id
    weight_config: WeightConfig – defaults to WeightConfig() if None

    Returns
    -------
    (path, cost) : list of node ids, total weighted cost

    Raises
    ------
    networkx.NetworkXNoPath   if no path exists (e.g., all routes blocked).
    networkx.NodeNotFound     if source or target is absent from the graph.
    """
    if weight_config is None:
        weight_config = WeightConfig()

    open_g = _open_subgraph(tg)
    path = nx.shortest_path(
        open_g,
        source=source,
        target=target,
        weight=_make_weight_fn(weight_config),
    )
    cost = path_cost(tg, path, weight_config)
    return path, cost


def path_cost(
    tg: TransportGraph,
    path: list,
    weight_config: WeightConfig | None = None,
) -> float:
    """
    Compute the total weighted cost of traversing a pre-computed path.

    Returns ``math.inf`` if any edge on the path is closed or missing —
    this makes infeasible paths distinguishable from valid ones in the
    QPSO fitness function (future milestones).

    Parameters
    ----------
    tg           : TransportGraph
    path         : ordered list of node ids
    weight_config: WeightConfig – defaults to WeightConfig() if None
    """
    if weight_config is None:
        weight_config = WeightConfig()
    if len(path) < 2:
        return 0.0

    g = tg.graph
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        if not g.has_edge(u, v):
            return math.inf
        data = g[u][v]
        if data.get("road_status") == TransportGraph.CLOSED:
            return math.inf
        total += weight_config.edge_cost(
            data["distance"],
            data["base_travel_time"],
            data["congestion_factor"],
        )
    return total
