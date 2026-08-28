"""
app/graph/model.py – Core graph data model for Q-Route.

Defines:
  WeightConfig  – configurable objective-function weights (wT, wD, wC).
  TransportGraph – directed weighted graph wrapping NetworkX DiGraph.

Design notes
------------
- The underlying store is a networkx.DiGraph so future milestones can
  model one-way roads without API changes.
- The edge-cost formula matches the project-wide fitness function:
    cost = wT * (base_travel_time * congestion_factor)
         + wD * distance
         + wC * (congestion_factor - 1.0)
  All components that compute route cost (pathfinding, QPSO fitness,
  2-opt evaluation) must import WeightConfig from here to stay
  apples-to-apples.
- Closed edges are represented as road_status == "closed" and are
  treated as impassable by pathfinding; they are never removed from
  the graph so they can be re-opened on incident resolution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# Weight configuration
# ---------------------------------------------------------------------------

@dataclass
class WeightConfig:
    """
    Weights for the multi-objective edge-cost formula used throughout
    Q-Route.  All defaults are 1.0 / 0.5 / 0.3 — override per scenario.

    Formula (one edge):
        effective_time = base_travel_time * congestion_factor   [minutes]
        cost = w_time      * effective_time
             + w_distance  * distance                           [km]
             + w_congestion * (congestion_factor - 1.0)         [penalty]
    """

    w_time: float = 1.0       # weight for effective travel time
    w_distance: float = 0.5   # weight for distance
    w_congestion: float = 0.3  # weight for congestion penalty

    def edge_cost(
        self,
        distance: float,
        base_travel_time: float,
        congestion_factor: float,
    ) -> float:
        """Scalar cost of traversing one open edge."""
        effective_time = base_travel_time * congestion_factor
        congestion_penalty = congestion_factor - 1.0
        return (
            self.w_time * effective_time
            + self.w_distance * distance
            + self.w_congestion * congestion_penalty
        )


# ---------------------------------------------------------------------------
# Transport graph
# ---------------------------------------------------------------------------

class TransportGraph:
    """
    Weighted directed graph representing a transport network.

    Nodes
    -----
    Attributes stored per node:
      node_type : str  – "intersection" | "depot" | "customer"
      x, y      : float – spatial coordinates (km)
      Any extra keyword arguments are forwarded to NetworkX.

    Edges
    -----
    Required attributes per edge:
      distance         : float – road-segment length (km)
      base_travel_time : float – uncongested travel time (minutes)
      congestion_factor: float – multiplier ≥ 1.0 (1.0 = free flow)
      road_status      : str   – "open" | "closed"

    Closed edges remain in the graph (status can flip back to "open")
    but are excluded from all path computations.
    """

    OPEN: str = "open"
    CLOSED: str = "closed"

    VALID_NODE_TYPES: frozenset[str] = frozenset(
        {"intersection", "depot", "customer"}
    )

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.DiGraph:
        """Read-only access to the underlying NetworkX DiGraph."""
        return self._g

    # ------------------------------------------------------------------
    # Mutation – nodes
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: Any,
        node_type: str = "intersection",
        x: float = 0.0,
        y: float = 0.0,
        **attrs: Any,
    ) -> None:
        """Add or update a node."""
        if node_type not in self.VALID_NODE_TYPES:
            raise ValueError(
                f"node_type must be one of {self.VALID_NODE_TYPES}, got {node_type!r}"
            )
        self._g.add_node(node_id, node_type=node_type, x=x, y=y, **attrs)

    # ------------------------------------------------------------------
    # Mutation – edges
    # ------------------------------------------------------------------

    def add_edge(
        self,
        u: Any,
        v: Any,
        distance: float,
        base_travel_time: float,
        congestion_factor: float = 1.0,
        road_status: str = "open",
        **attrs: Any,
    ) -> None:
        """Add or overwrite a directed edge (u → v)."""
        if road_status not in (self.OPEN, self.CLOSED):
            raise ValueError(
                f"road_status must be 'open' or 'closed', got {road_status!r}"
            )
        self._g.add_edge(
            u, v,
            distance=distance,
            base_travel_time=base_travel_time,
            congestion_factor=congestion_factor,
            road_status=road_status,
            **attrs,
        )

    def set_edge_attribute(self, u: Any, v: Any, attribute: str, value: Any) -> None:
        """Set a single attribute on an existing edge."""
        if not self._g.has_edge(u, v):
            raise KeyError(f"Edge ({u!r}, {v!r}) does not exist in the graph.")
        self._g[u][v][attribute] = value

    def close_edge(self, u: Any, v: Any) -> None:
        """Mark edge (u → v) as closed (impassable)."""
        self.set_edge_attribute(u, v, "road_status", self.CLOSED)

    def open_edge(self, u: Any, v: Any) -> None:
        """Re-open a previously closed edge (u → v)."""
        self.set_edge_attribute(u, v, "road_status", self.OPEN)

    # ------------------------------------------------------------------
    # Cost query
    # ------------------------------------------------------------------

    def edge_cost(
        self,
        u: Any,
        v: Any,
        weight_config: WeightConfig,
    ) -> float:
        """
        Weighted cost of traversing edge (u → v).

        Returns math.inf if the edge is missing or closed.
        """
        if not self._g.has_edge(u, v):
            return math.inf
        data = self._g[u][v]
        if data.get("road_status") == self.CLOSED:
            return math.inf
        return weight_config.edge_cost(
            data["distance"],
            data["base_travel_time"],
            data["congestion_factor"],
        )

    # ------------------------------------------------------------------
    # Size helpers
    # ------------------------------------------------------------------

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def __len__(self) -> int:  # len(tg) → node count
        return self.node_count()

    # ------------------------------------------------------------------
    # Serialisation (JSON-compatible dicts)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Serialise the graph to a plain dict that can be written to JSON.

        Schema::

            {
              "nodes": [{"id": ..., "node_type": ..., "x": ..., "y": ..., ...}],
              "edges": [{"u": ..., "v": ..., "distance": ..., ...}]
            }
        """
        nodes = [{"id": n, **self._g.nodes[n]} for n in self._g.nodes]
        edges = [
            {"u": u, "v": v, **data}
            for u, v, data in self._g.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict) -> "TransportGraph":
        """
        Reconstruct a TransportGraph from a dict produced by ``to_dict()``
        or ``generate_synthetic_network()``.
        """
        tg = cls()
        for node in data["nodes"]:
            node_id = node["id"]
            attrs = {k: v for k, v in node.items() if k != "id"}
            node_type = attrs.pop("node_type", "intersection")
            x = attrs.pop("x", 0.0)
            y = attrs.pop("y", 0.0)
            tg.add_node(node_id, node_type=node_type, x=x, y=y, **attrs)
        for edge in data["edges"]:
            u, v = edge["u"], edge["v"]
            attrs = {k: v for k, v in edge.items() if k not in ("u", "v")}
            tg.add_edge(u, v, **attrs)
        return tg
