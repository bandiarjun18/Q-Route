"""
app/routes/validation.py – Route validity checker for Q-Route (Milestone 8).

Public API
----------
validate_route(tg, node_sequence) -> None

Design notes
------------
- Pure function: reads graph state, never mutates it.  Calling it multiple
  times on the same inputs always yields the same result and has no side
  effects.
- Raises ValueError with a descriptive, actionable message on the first
  detected problem.
- Mirrors the road-availability and connectivity checks in
  app.vrp.feasibility.check_feasibility but is route-scoped: it validates
  a single node_sequence with no fleet, capacity, or customer-coverage
  concerns.
- Closed edges are always rejected — they represent impassable road segments
  and are never valid route segments regardless of context (consistent with
  the TransportGraph, pathfinding, and VRP feasibility layers).
- Validation does not call shortest_path or path_cost; it reads the graph
  directly to avoid side-channel coupling with the path-finding layer.
"""

from __future__ import annotations

from typing import Any

from app.graph.model import TransportGraph


def validate_route(tg: TransportGraph, node_sequence: list[Any]) -> None:
    """
    Validate a node sequence against the current state of the road network.

    Checks (in order):

    1. The sequence must contain at least 2 nodes.
    2. Every node id in the sequence must exist in the graph.
    3. Every consecutive pair ``(u, v)`` must be a directed edge in the graph.
    4. No edge in the sequence may have ``road_status == "closed"``.

    Parameters
    ----------
    tg            : TransportGraph – the road network to validate against.
    node_sequence : list           – ordered graph node ids describing the route,
                                     including the depot at position [0] and [-1].

    Returns
    -------
    None – returns silently when the route is valid.

    Raises
    ------
    ValueError
        With a descriptive message if any check fails.  The exception is
        raised on the **first** detected violation (fail-fast).

    Notes
    -----
    This function is **pure**: it reads ``tg`` but never mutates it.
    Route validation does not trigger pathfinding, modify graph attributes,
    or interact with the TrafficLayer or IncidentLayer.
    """
    # ── Check 1: minimum length ──────────────────────────────────────────
    if len(node_sequence) < 2:
        raise ValueError(
            f"Route is too short: node_sequence must have at least 2 nodes, "
            f"got {len(node_sequence)}."
        )

    g = tg.graph

    # ── Check 2: every node must exist ───────────────────────────────────
    for node_id in node_sequence:
        if not g.has_node(node_id):
            raise ValueError(
                f"Route contains unknown node {node_id!r}: "
                f"this node does not exist in the graph."
            )

    # ── Checks 3 & 4: every consecutive edge must exist and be open ──────
    for i, (u, v) in enumerate(zip(node_sequence[:-1], node_sequence[1:])):
        if not g.has_edge(u, v):
            raise ValueError(
                f"Route has no directed edge from {u!r} to {v!r} "
                f"at sequence position {i}."
            )
        if g[u][v].get("road_status") == TransportGraph.CLOSED:
            raise ValueError(
                f"Route uses a closed edge from {u!r} to {v!r} "
                f"at sequence position {i}. "
                f"Closed edges are never valid route segments."
            )
