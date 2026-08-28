"""
tests/test_graph.py – Unit tests for the Q-Route transportation graph engine.

Coverage
--------
1. Graph construction  – node/edge counts, attributes, close/open, round-trip.
2. Closed-edge exclusion – shortest-path correctly avoids closed edges;
   NetworkXNoPath raised when all routes are blocked.
3. Edge-weight changes – congestion edits change path cost and can flip the
   preferred route.
4. Synthetic-network generation – node/edge structure, connectivity,
   reproducibility, JSON round-trip, pathfinding on generated data.

Run from backend/ directory:
    python -m pytest tests/test_graph.py -v
"""

from __future__ import annotations

import json
import math

import networkx as nx
import pytest

from app.graph.model import TransportGraph, WeightConfig
from app.graph.generator import (
    generate_synthetic_network,
    save_network_json,
    load_network_json,
    build_transport_graph,
)
from app.graph.pathfinding import shortest_path, path_cost


# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def diamond_graph() -> TransportGraph:
    """
    Four-node directed graph with two paths from node 0 to node 3.

    Topology (directed edges, both paths open by default)::

        0 ──[short, 1 km, 2 min]──► 2 ──[short, 1 km, 2 min]──► 3
        │                                                          ▲
        └──[long,  5 km, 10 min]──► 1 ──[long, 5 km, 10 min]──────┘

    Short path 0→2→3: total distance 2 km, total base time 4 min.
    Long  path 0→1→3: total distance 10 km, total base time 20 min.
    """
    tg = TransportGraph()
    for nid, ntype in [
        (0, "depot"),
        (1, "intersection"),
        (2, "intersection"),
        (3, "customer"),
    ]:
        tg.add_node(nid, node_type=ntype, x=float(nid), y=0.0)

    # Short path edges
    tg.add_edge(0, 2, distance=1.0, base_travel_time=2.0, congestion_factor=1.0)
    tg.add_edge(2, 3, distance=1.0, base_travel_time=2.0, congestion_factor=1.0)

    # Long path edges
    tg.add_edge(0, 1, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)
    tg.add_edge(1, 3, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)

    return tg


# ═══════════════════════════════════════════════════════════════════════════
# 1. Graph construction
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphConstruction:

    def test_node_count(self, diamond_graph: TransportGraph) -> None:
        assert diamond_graph.node_count() == 4

    def test_edge_count(self, diamond_graph: TransportGraph) -> None:
        assert diamond_graph.edge_count() == 4

    def test_node_types_stored(self, diamond_graph: TransportGraph) -> None:
        g = diamond_graph.graph
        assert g.nodes[0]["node_type"] == "depot"
        assert g.nodes[3]["node_type"] == "customer"
        assert g.nodes[1]["node_type"] == "intersection"

    def test_edge_attributes_stored(self, diamond_graph: TransportGraph) -> None:
        data = diamond_graph.graph[0][2]
        assert data["distance"] == pytest.approx(1.0)
        assert data["base_travel_time"] == pytest.approx(2.0)
        assert data["congestion_factor"] == pytest.approx(1.0)
        assert data["road_status"] == "open"

    def test_default_road_status_is_open(self, diamond_graph: TransportGraph) -> None:
        for u, v, d in diamond_graph.graph.edges(data=True):
            assert d["road_status"] == "open", f"Edge ({u},{v}) should default to 'open'"

    def test_close_edge(self, diamond_graph: TransportGraph) -> None:
        diamond_graph.close_edge(0, 2)
        assert diamond_graph.graph[0][2]["road_status"] == "closed"

    def test_reopen_edge(self, diamond_graph: TransportGraph) -> None:
        diamond_graph.close_edge(0, 2)
        diamond_graph.open_edge(0, 2)
        assert diamond_graph.graph[0][2]["road_status"] == "open"

    def test_set_edge_attribute(self, diamond_graph: TransportGraph) -> None:
        diamond_graph.set_edge_attribute(0, 2, "congestion_factor", 3.5)
        assert diamond_graph.graph[0][2]["congestion_factor"] == pytest.approx(3.5)

    def test_set_attribute_on_missing_edge_raises(self, diamond_graph: TransportGraph) -> None:
        with pytest.raises(KeyError):
            diamond_graph.set_edge_attribute(99, 99, "road_status", "open")

    def test_invalid_node_type_raises(self) -> None:
        tg = TransportGraph()
        with pytest.raises(ValueError, match="node_type"):
            tg.add_node(0, node_type="spaceship")

    def test_invalid_road_status_raises(self) -> None:
        tg = TransportGraph()
        tg.add_node(0)
        tg.add_node(1)
        with pytest.raises(ValueError, match="road_status"):
            tg.add_edge(0, 1, distance=1.0, base_travel_time=1.0, road_status="maybe")

    def test_to_dict_round_trip(self, diamond_graph: TransportGraph) -> None:
        """Serialise → deserialise must reproduce an identical graph."""
        d = diamond_graph.to_dict()
        tg2 = TransportGraph.from_dict(d)
        assert tg2.node_count() == diamond_graph.node_count()
        assert tg2.edge_count() == diamond_graph.edge_count()
        # Spot-check an edge
        assert tg2.graph[0][2]["distance"] == pytest.approx(
            diamond_graph.graph[0][2]["distance"]
        )

    def test_edge_cost_closed_returns_inf(self, diamond_graph: TransportGraph) -> None:
        diamond_graph.close_edge(0, 2)
        cfg = WeightConfig()
        assert diamond_graph.edge_cost(0, 2, cfg) == math.inf

    def test_edge_cost_missing_returns_inf(self, diamond_graph: TransportGraph) -> None:
        cfg = WeightConfig()
        assert diamond_graph.edge_cost(0, 99, cfg) == math.inf

    def test_len_returns_node_count(self, diamond_graph: TransportGraph) -> None:
        assert len(diamond_graph) == diamond_graph.node_count()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Closed-edge exclusion from shortest paths
# ═══════════════════════════════════════════════════════════════════════════

class TestClosedEdgeExclusion:

    def test_open_graph_uses_short_path(self, diamond_graph: TransportGraph) -> None:
        """With all edges open the cheaper (shorter) path must be chosen."""
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        path, _ = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert path == [0, 2, 3], f"Expected [0,2,3], got {path}"

    def test_closing_short_path_forces_detour(self, diamond_graph: TransportGraph) -> None:
        """Close one edge on the short path → algorithm must use long path."""
        diamond_graph.close_edge(0, 2)
        path, _ = shortest_path(diamond_graph, 0, 3)
        assert path == [0, 1, 3], f"Expected detour [0,1,3], got {path}"

    def test_closed_node_not_visited(self, diamond_graph: TransportGraph) -> None:
        """Node 2 must not appear in the path when its only incoming edge is closed."""
        diamond_graph.close_edge(0, 2)
        path, _ = shortest_path(diamond_graph, 0, 3)
        assert 2 not in path

    def test_closing_both_short_edges_forces_detour(self, diamond_graph: TransportGraph) -> None:
        """Close both edges of the short path."""
        diamond_graph.close_edge(0, 2)
        diamond_graph.close_edge(2, 3)
        path, _ = shortest_path(diamond_graph, 0, 3)
        assert path == [0, 1, 3]

    def test_directionality_respected(self) -> None:
        """Closing u→v must not affect v→u."""
        tg = TransportGraph()
        tg.add_node(0, node_type="depot", x=0.0, y=0.0)
        tg.add_node(1, node_type="customer", x=1.0, y=0.0)
        tg.add_edge(0, 1, distance=1.0, base_travel_time=2.0)
        tg.add_edge(1, 0, distance=1.0, base_travel_time=2.0)

        tg.close_edge(0, 1)

        # v→u is still open
        path, _ = shortest_path(tg, 1, 0)
        assert path == [1, 0]

        # u→v is closed → no path
        with pytest.raises(nx.NetworkXNoPath):
            shortest_path(tg, 0, 1)

    def test_all_routes_blocked_raises_no_path(self, diamond_graph: TransportGraph) -> None:
        """If every route to target is blocked, NetworkXNoPath must be raised."""
        diamond_graph.close_edge(2, 3)
        diamond_graph.close_edge(1, 3)
        with pytest.raises(nx.NetworkXNoPath):
            shortest_path(diamond_graph, 0, 3)

    def test_path_cost_of_closed_edge_is_inf(self, diamond_graph: TransportGraph) -> None:
        """path_cost must return inf if the supplied path contains a closed edge."""
        diamond_graph.close_edge(0, 2)
        cost = path_cost(diamond_graph, [0, 2, 3])
        assert cost == math.inf

    def test_path_cost_missing_edge_is_inf(self, diamond_graph: TransportGraph) -> None:
        cost = path_cost(diamond_graph, [0, 99, 3])
        assert cost == math.inf


# ═══════════════════════════════════════════════════════════════════════════
# 3. Edge-weight changes reflected in path cost
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeWeightChanges:

    def test_baseline_cost_time_only(self, diamond_graph: TransportGraph) -> None:
        """
        Short path, w_time=1, no distance/congestion weight.
        Expected = 2 edges × (2.0 min × 1.0 congestion) = 4.0
        """
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        _, cost = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert cost == pytest.approx(4.0)

    def test_manual_cost_calculation(self, diamond_graph: TransportGraph) -> None:
        """
        Full formula: wT=1, wD=1, wC=0.5, congestion=1.0, dist=1.0, time=2.0
        per edge: 1*(2*1) + 1*1 + 0.5*(1-1) = 2+1+0 = 3.0
        two edges → 6.0
        """
        cfg = WeightConfig(w_time=1.0, w_distance=1.0, w_congestion=0.5)
        cost = path_cost(diamond_graph, [0, 2, 3], weight_config=cfg)
        assert cost == pytest.approx(6.0)

    def test_increased_congestion_raises_cost(self, diamond_graph: TransportGraph) -> None:
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        _, cost_before = shortest_path(diamond_graph, 0, 3, weight_config=cfg)

        diamond_graph.set_edge_attribute(0, 2, "congestion_factor", 5.0)
        diamond_graph.set_edge_attribute(2, 3, "congestion_factor", 5.0)

        cost_after = path_cost(diamond_graph, [0, 2, 3], weight_config=cfg)
        assert cost_after > cost_before

    def test_congestion_flips_preferred_route(self, diamond_graph: TransportGraph) -> None:
        """
        Heavy congestion on short path makes long path cheaper.
        Short: base_time=2 min × congestion=100 → 200 min/edge → 400 total
        Long : base_time=10 min × congestion=1  → 10 min/edge  → 20 total
        """
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)

        diamond_graph.set_edge_attribute(0, 2, "congestion_factor", 100.0)
        diamond_graph.set_edge_attribute(2, 3, "congestion_factor", 100.0)

        path, _ = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert path == [0, 1, 3], (
            f"Expected long path [0,1,3] after heavy congestion, got {path}"
        )

    def test_weight_config_distance_only(self, diamond_graph: TransportGraph) -> None:
        """Pure distance objective must also select short path."""
        cfg = WeightConfig(w_time=0.0, w_distance=1.0, w_congestion=0.0)
        path, cost = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert path == [0, 2, 3]
        assert cost == pytest.approx(2.0)  # 1 km + 1 km

    def test_reopening_edge_restores_cost(self, diamond_graph: TransportGraph) -> None:
        """After closing then re-opening an edge the original cost is restored."""
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        _, cost_original = shortest_path(diamond_graph, 0, 3, weight_config=cfg)

        diamond_graph.close_edge(0, 2)
        diamond_graph.open_edge(0, 2)

        _, cost_restored = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert cost_restored == pytest.approx(cost_original)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Synthetic-network generation
# ═══════════════════════════════════════════════════════════════════════════

class TestSyntheticNetworkGeneration:

    def test_node_count(self) -> None:
        data = generate_synthetic_network(n_nodes=15, seed=42)
        assert len(data["nodes"]) == 15

    def test_depot_present(self) -> None:
        data = generate_synthetic_network(n_depots=1, seed=42)
        types = [n["node_type"] for n in data["nodes"]]
        assert "depot" in types

    def test_customer_count(self) -> None:
        data = generate_synthetic_network(n_nodes=20, n_customers=4, seed=42)
        customers = [n for n in data["nodes"] if n["node_type"] == "customer"]
        assert len(customers) == 4

    def test_all_edges_have_required_attributes(self) -> None:
        data = generate_synthetic_network(seed=42)
        required = {"u", "v", "distance", "base_travel_time", "congestion_factor", "road_status"}
        for edge in data["edges"]:
            missing = required - edge.keys()
            assert not missing, f"Edge missing keys: {missing}"

    def test_graph_is_weakly_connected(self) -> None:
        """Every node must be reachable from every other node (ignoring direction)."""
        data = generate_synthetic_network(n_nodes=20, seed=42)
        tg = build_transport_graph(data)
        assert nx.is_weakly_connected(tg.graph)

    def test_edges_are_bidirectional(self) -> None:
        """Every directed edge (u,v) must have a corresponding (v,u)."""
        data = generate_synthetic_network(n_nodes=10, seed=42)
        tg = build_transport_graph(data)
        for u, v in tg.graph.edges():
            assert tg.graph.has_edge(v, u), f"Missing reverse edge ({v},{u})"

    def test_reproducible_same_seed(self) -> None:
        d1 = generate_synthetic_network(seed=99)
        d2 = generate_synthetic_network(seed=99)
        assert d1 == d2

    def test_different_seeds_differ(self) -> None:
        d1 = generate_synthetic_network(seed=1)
        d2 = generate_synthetic_network(seed=2)
        # Different seeds → different node positions
        assert d1["nodes"] != d2["nodes"]

    def test_meta_fields_present(self) -> None:
        data = generate_synthetic_network(n_nodes=12, seed=7)
        meta = data["meta"]
        for key in ("n_nodes", "n_depots", "n_customers", "grid_size_km",
                    "connect_radius_km", "closed_fraction", "seed"):
            assert key in meta, f"Missing meta key: {key}"
        assert meta["n_nodes"] == 12
        assert meta["seed"] == 7

    def test_json_round_trip(self, tmp_path) -> None:
        data = generate_synthetic_network(seed=42)
        out = tmp_path / "net.json"
        save_network_json(data, out)
        loaded = load_network_json(out)
        assert loaded == data

    def test_json_is_valid(self, tmp_path) -> None:
        data = generate_synthetic_network(seed=42)
        out = tmp_path / "net.json"
        save_network_json(data, out)
        raw = out.read_text(encoding="utf-8")
        parsed = json.loads(raw)  # must not raise
        assert "nodes" in parsed and "edges" in parsed

    def test_build_transport_graph_round_trip(self) -> None:
        data = generate_synthetic_network(seed=42)
        tg = build_transport_graph(data)
        assert tg.node_count() == len(data["nodes"])
        assert tg.edge_count() == len(data["edges"])

    def test_shortest_path_depot_to_customer(self) -> None:
        """Depot (node 0) must be able to reach every customer in the default net."""
        data = generate_synthetic_network(n_nodes=20, n_customers=5, seed=42)
        tg = build_transport_graph(data)
        customers = [n["id"] for n in data["nodes"] if n["node_type"] == "customer"]
        for cid in customers:
            path, cost = shortest_path(tg, 0, cid)
            assert len(path) >= 2, f"Path to customer {cid} too short: {path}"
            assert cost > 0.0, f"Path cost to customer {cid} must be positive"

    def test_some_edges_closed(self) -> None:
        """With a non-zero closed_fraction the network must contain closed edges."""
        data = generate_synthetic_network(n_nodes=30, closed_fraction=0.15, seed=42)
        closed = [e for e in data["edges"] if e["road_status"] == "closed"]
        assert len(closed) > 0, "Expected at least one closed edge"
