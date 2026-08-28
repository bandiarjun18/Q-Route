"""
tests/test_routes.py – Unit tests for the Q-Route Route Management + ETA layer
(Milestone 8).

Coverage (20 test classes / 35 individual tests)
-------------------------------------------------
 1. TestActiveRouteCreation        – defaults, status, estimated_arrival,
                                     from_vehicle_route factory.
 2. TestRouteRegistration          – register() success, metrics stamped,
                                     duplicate route_id rejected.
 3. TestRouteRetrieval             – get() returns correct route; KeyError
                                     on unknown id.
 4. TestRouteUpdate                – allowed fields updated; ValueError for
                                     protected fields; KeyError for unknown id.
 5. TestRouteRemoval               – remove() works; list_active() shrinks;
                                     KeyError on double-remove; deactivate()
                                     retains route in registry.
 6. TestMultipleVehicles           – routes_for_vehicle() filters correctly;
                                     two routes in one manager; no cross-
                                     contamination between managers.
 7. TestValidRouteValidation       – validate_route() passes on valid sequence.
 8. TestInvalidNodeDetection       – ValueError for node absent from graph.
 9. TestInvalidEdgeDetection       – ValueError for missing directed edge.
10. TestClosedEdgeRejection        – validate_route() and register() both
                                     reject closed-edge sequences.
11. TestDistanceCalculation        – route_distance() = 15.0 for [0,1,2,0].
12. TestTravelTimeCalculation      – route_travel_time() = 30.0 at cf=1.0.
13. TestCongestionAwareTravelTime  – 48.0 after HEAVY TrafficLayer apply().
14. TestETACalculation             – compute_eta() with 0, partial, and
                                     over-elapsed values.
15. TestRouteAffectedByIncident    – ROAD_CLOSURE incident flags route as
                                     affected; partial incident also detected.
16. TestRouteUnaffectedByIncident  – incident on an edge not in this route
                                     does not flag the route.
17. TestMultipleRoutesAffectedDetection – only routes overlapping the
                                          incident are returned; mark=True
                                          updates statuses.
18. TestNoGlobalState              – two RouteManager instances are fully
                                     independent.
19. TestEmptyAndMinimalRoutes      – [] and [0] rejected as too short; [0,0]
                                     rejected as missing self-loop edge;
                                     [0,1,0] accepted as minimal valid route.
20. TestRegressionM1toM7          – all M1–M7 public APIs remain importable
                                     and behaviorally unchanged after M8 import.

Run from the backend/ directory:
    python -m pytest tests/test_routes.py -v
"""

from __future__ import annotations

import math

import pytest

from app.graph.model import TransportGraph, WeightConfig
from app.incidents import Incident, IncidentLayer, IncidentSeverity, IncidentType
from app.routes import (
    ActiveRoute,
    RouteManager,
    RouteStatus,
    compute_eta,
    route_distance,
    route_travel_time,
    validate_route,
)
from app.traffic import TrafficLayer, TrafficState
from app.vrp.models import VehicleRoute


# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def simple_graph() -> TransportGraph:
    """
    Three-node graph: depot(0) → A(1) → B(2), plus all reverse edges.
    All edges open, distance=5.0 km, base_travel_time=10.0 min,
    congestion_factor=1.0.

    Derived values used in tests
    ----------------------------
    Route [0,1,2,0] has 3 edges:
      total_distance    = 3 × 5.0  = 15.0 km
      total_travel_time = 3 × 10.0 =  30.0 min  (cf=1.0)
      HEAVY cf=1.6      = 3 × 16.0 =  48.0 min
    """
    tg = TransportGraph()
    tg.add_node(0, node_type="depot",    x=0.0, y=0.0)
    tg.add_node(1, node_type="customer", x=1.0, y=0.0)
    tg.add_node(2, node_type="customer", x=2.0, y=0.0)

    for u, v in [(0, 1), (1, 2), (0, 2), (1, 0), (2, 1), (2, 0)]:
        tg.add_edge(u, v, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)

    return tg


@pytest.fixture()
def route_0_1_2_0() -> ActiveRoute:
    """ActiveRoute visiting nodes 0→1→2→0 with route_id="R1", vehicle_id="V1"."""
    return ActiveRoute(
        route_id="R1",
        vehicle_id="V1",
        depot_node=0,
        visit_order=["C1", "C2"],
        node_sequence=[0, 1, 2, 0],
    )


@pytest.fixture()
def route_manager() -> RouteManager:
    """Fresh, empty RouteManager per test."""
    return RouteManager()


# ═══════════════════════════════════════════════════════════════════════════
# 1. TestActiveRouteCreation
# ═══════════════════════════════════════════════════════════════════════════

class TestActiveRouteCreation:
    """ActiveRoute instantiation and defaults."""

    def test_default_status_is_active(self, route_0_1_2_0: ActiveRoute) -> None:
        assert route_0_1_2_0.status is RouteStatus.ACTIVE

    def test_default_estimated_arrival_is_none(self, route_0_1_2_0: ActiveRoute) -> None:
        assert route_0_1_2_0.estimated_arrival is None

    def test_default_metrics_are_zero(self, route_0_1_2_0: ActiveRoute) -> None:
        assert route_0_1_2_0.total_distance == 0.0
        assert route_0_1_2_0.total_travel_time == 0.0

    def test_route_status_enum_values(self) -> None:
        assert RouteStatus.ACTIVE.value    == "active"
        assert RouteStatus.COMPLETED.value == "completed"
        assert RouteStatus.CANCELLED.value == "cancelled"
        assert RouteStatus.AFFECTED.value  == "affected"

    def test_from_vehicle_route_factory(self) -> None:
        """from_vehicle_route copies all structural fields correctly."""
        vr = VehicleRoute(
            vehicle_id="V7",
            depot_node=42,
            visit_order=["C10", "C11"],
            node_sequence=[42, 10, 11, 42],
        )
        ar = ActiveRoute.from_vehicle_route(vr, route_id="R-factory")
        assert ar.route_id == "R-factory"
        assert ar.vehicle_id == "V7"
        assert ar.depot_node == 42
        assert ar.visit_order == ["C10", "C11"]
        assert ar.node_sequence == [42, 10, 11, 42]
        assert ar.status is RouteStatus.ACTIVE
        assert ar.estimated_arrival is None

    def test_from_vehicle_route_copies_lists(self) -> None:
        """Modifying the copy must not affect the original VehicleRoute."""
        vr = VehicleRoute(
            vehicle_id="V1",
            depot_node=0,
            visit_order=["C1"],
            node_sequence=[0, 1, 0],
        )
        ar = ActiveRoute.from_vehicle_route(vr, route_id="R-copy")
        ar.visit_order.append("extra")
        ar.node_sequence.append(99)
        assert vr.visit_order == ["C1"]
        assert vr.node_sequence == [0, 1, 0]


# ═══════════════════════════════════════════════════════════════════════════
# 2. TestRouteRegistration
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteRegistration:
    """register() success path, metric stamping, duplicate rejection."""

    def test_register_succeeds_and_returns_route(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        result = route_manager.register(route_0_1_2_0, simple_graph)
        assert result is route_0_1_2_0

    def test_register_stamps_distance(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        assert route_0_1_2_0.total_distance == pytest.approx(15.0)

    def test_register_stamps_travel_time(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        assert route_0_1_2_0.total_travel_time == pytest.approx(30.0)

    def test_register_duplicate_route_id_raises(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        duplicate = ActiveRoute(
            route_id="R1",  # same id
            vehicle_id="V2",
            depot_node=0,
            node_sequence=[0, 2, 0],
        )
        with pytest.raises(ValueError, match="R1"):
            route_manager.register(duplicate, simple_graph)

    def test_register_stores_route_in_registry(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        assert len(route_manager) == 1
        assert route_manager.get("R1") is route_0_1_2_0


# ═══════════════════════════════════════════════════════════════════════════
# 3. TestRouteRetrieval
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteRetrieval:
    """get() correct route; KeyError on unknown id."""

    def test_get_returns_correct_route(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        retrieved = route_manager.get("R1")
        assert retrieved is route_0_1_2_0

    def test_get_unknown_id_raises_key_error(
        self, route_manager: RouteManager
    ) -> None:
        with pytest.raises(KeyError):
            route_manager.get("nonexistent")


# ═══════════════════════════════════════════════════════════════════════════
# 4. TestRouteUpdate
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteUpdate:
    """update() allowed fields; ValueError for protected; KeyError for unknown."""

    def test_update_estimated_arrival(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.update("R1", estimated_arrival=12.5)
        assert route_0_1_2_0.estimated_arrival == pytest.approx(12.5)

    def test_update_status(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.update("R1", status=RouteStatus.AFFECTED)
        assert route_0_1_2_0.status is RouteStatus.AFFECTED

    def test_update_protected_route_id_raises(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        with pytest.raises(ValueError, match="protected"):
            route_manager.update("R1", route_id="R999")

    def test_update_protected_node_sequence_raises(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        with pytest.raises(ValueError, match="protected"):
            route_manager.update("R1", node_sequence=[0, 2, 0])

    def test_update_unknown_route_id_raises_key_error(
        self, route_manager: RouteManager
    ) -> None:
        with pytest.raises(KeyError):
            route_manager.update("ghost", estimated_arrival=5.0)


# ═══════════════════════════════════════════════════════════════════════════
# 5. TestRouteRemoval
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteRemoval:
    """remove(); deactivate(); list_active() filtering."""

    def test_remove_deletes_route(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.remove("R1")
        assert len(route_manager) == 0

    def test_remove_makes_get_raise_key_error(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.remove("R1")
        with pytest.raises(KeyError):
            route_manager.get("R1")

    def test_remove_nonexistent_raises_key_error(
        self, route_manager: RouteManager
    ) -> None:
        with pytest.raises(KeyError):
            route_manager.remove("ghost")

    def test_deactivate_keeps_route_in_registry(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.deactivate("R1")
        assert route_manager.get("R1") is route_0_1_2_0  # still retrievable

    def test_deactivate_sets_completed_status(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.deactivate("R1")
        assert route_0_1_2_0.status is RouteStatus.COMPLETED

    def test_deactivate_removes_from_list_active(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        assert len(route_manager.list_active()) == 1
        route_manager.deactivate("R1")
        assert len(route_manager.list_active()) == 0

    def test_deactivate_with_cancelled_status(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        route_manager.deactivate("R1", status=RouteStatus.CANCELLED)
        assert route_0_1_2_0.status is RouteStatus.CANCELLED
        assert route_0_1_2_0 not in route_manager.list_active()


# ═══════════════════════════════════════════════════════════════════════════
# 6. TestMultipleVehicles
# ═══════════════════════════════════════════════════════════════════════════

class TestMultipleVehicles:
    """Multiple routes in one manager; routes_for_vehicle() filtering."""

    def test_routes_for_vehicle_returns_correct_subset(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        r1 = ActiveRoute(
            route_id="V1-R1", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],
        )
        r2 = ActiveRoute(
            route_id="V2-R1", vehicle_id="V2",
            depot_node=0, node_sequence=[0, 2, 0],
        )
        route_manager.register(r1, simple_graph)
        route_manager.register(r2, simple_graph)

        v1_routes = route_manager.routes_for_vehicle("V1")
        v2_routes = route_manager.routes_for_vehicle("V2")

        assert v1_routes == [r1]
        assert v2_routes == [r2]

    def test_routes_for_vehicle_includes_terminal_status(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        r = ActiveRoute(
            route_id="V1-R1", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],
        )
        route_manager.register(r, simple_graph)
        route_manager.deactivate("V1-R1")  # COMPLETED

        # routes_for_vehicle includes all statuses
        assert route_manager.routes_for_vehicle("V1") == [r]

    def test_routes_for_unknown_vehicle_returns_empty(
        self, route_manager: RouteManager
    ) -> None:
        assert route_manager.routes_for_vehicle("phantom") == []


# ═══════════════════════════════════════════════════════════════════════════
# 7. TestValidRouteValidation
# ═══════════════════════════════════════════════════════════════════════════

class TestValidRouteValidation:
    """validate_route() passes on valid sequences."""

    def test_valid_three_node_sequence(self, simple_graph: TransportGraph) -> None:
        validate_route(simple_graph, [0, 1, 2, 0])  # must not raise

    def test_valid_two_node_sequence(self, simple_graph: TransportGraph) -> None:
        validate_route(simple_graph, [0, 1])  # must not raise

    def test_valid_route_returns_none(self, simple_graph: TransportGraph) -> None:
        result = validate_route(simple_graph, [0, 2, 0])
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# 8. TestInvalidNodeDetection
# ═══════════════════════════════════════════════════════════════════════════

class TestInvalidNodeDetection:
    """validate_route() raises ValueError for nodes absent from the graph."""

    def test_unknown_node_raises(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="unknown node"):
            validate_route(simple_graph, [0, 99, 0])

    def test_unknown_start_node_raises(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="unknown node"):
            validate_route(simple_graph, [999, 1, 0])


# ═══════════════════════════════════════════════════════════════════════════
# 9. TestInvalidEdgeDetection
# ═══════════════════════════════════════════════════════════════════════════

class TestInvalidEdgeDetection:
    """validate_route() raises ValueError when a directed edge is missing."""

    def test_missing_directed_edge_raises(self) -> None:
        # Graph with only one directed edge: 0→1, 1→2 (no return edges).
        tg = TransportGraph()
        tg.add_node(0, node_type="depot")
        tg.add_node(1, node_type="customer")
        tg.add_node(2, node_type="customer")
        tg.add_edge(0, 1, distance=5.0, base_travel_time=10.0)
        tg.add_edge(1, 2, distance=5.0, base_travel_time=10.0)
        # There is no edge from 2 back to 0.
        with pytest.raises(ValueError, match="no directed edge"):
            validate_route(tg, [0, 1, 2, 0])

    def test_register_propagates_missing_edge_error(
        self, route_manager: RouteManager
    ) -> None:
        tg = TransportGraph()
        tg.add_node(0, node_type="depot")
        tg.add_node(1, node_type="customer")
        tg.add_edge(0, 1, distance=5.0, base_travel_time=10.0)
        route = ActiveRoute(
            route_id="R-bad",
            vehicle_id="V1",
            depot_node=0,
            node_sequence=[0, 1, 0],  # no edge 1→0
        )
        with pytest.raises(ValueError):
            route_manager.register(route, tg)


# ═══════════════════════════════════════════════════════════════════════════
# 10. TestClosedEdgeRejection
# ═══════════════════════════════════════════════════════════════════════════

class TestClosedEdgeRejection:
    """Closed edges are rejected by validate_route() and register()."""

    def test_closed_edge_rejected_by_validate_route(
        self, simple_graph: TransportGraph
    ) -> None:
        simple_graph.close_edge(1, 2)
        with pytest.raises(ValueError, match="closed edge"):
            validate_route(simple_graph, [0, 1, 2, 0])

    def test_register_rejects_route_with_closed_edge(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        simple_graph.close_edge(0, 1)
        with pytest.raises(ValueError, match="closed"):
            route_manager.register(route_0_1_2_0, simple_graph)

    def test_validate_route_does_not_mutate_graph(
        self, simple_graph: TransportGraph
    ) -> None:
        """validate_route() must not modify road_status or congestion_factor."""
        original_status = simple_graph.graph[0][1]["road_status"]
        original_cf = simple_graph.graph[0][1]["congestion_factor"]
        validate_route(simple_graph, [0, 1, 2, 0])
        assert simple_graph.graph[0][1]["road_status"] == original_status
        assert simple_graph.graph[0][1]["congestion_factor"] == original_cf


# ═══════════════════════════════════════════════════════════════════════════
# 11. TestDistanceCalculation
# ═══════════════════════════════════════════════════════════════════════════

class TestDistanceCalculation:
    """route_distance() returns correct total km."""

    def test_distance_three_edges(self, simple_graph: TransportGraph) -> None:
        # [0,1,2,0] → 3 edges × 5.0 km = 15.0
        assert route_distance(simple_graph, [0, 1, 2, 0]) == pytest.approx(15.0)

    def test_distance_two_edges(self, simple_graph: TransportGraph) -> None:
        # [0,1,0] → 2 edges × 5.0 km = 10.0
        assert route_distance(simple_graph, [0, 1, 0]) == pytest.approx(10.0)

    def test_distance_closed_edge_returns_inf(
        self, simple_graph: TransportGraph
    ) -> None:
        simple_graph.close_edge(0, 1)
        assert math.isinf(route_distance(simple_graph, [0, 1, 2, 0]))


# ═══════════════════════════════════════════════════════════════════════════
# 12. TestTravelTimeCalculation
# ═══════════════════════════════════════════════════════════════════════════

class TestTravelTimeCalculation:
    """route_travel_time() at default congestion (cf=1.0)."""

    def test_travel_time_three_edges_no_congestion(
        self, simple_graph: TransportGraph
    ) -> None:
        # 3 edges × btt=10.0 × cf=1.0 = 30.0
        assert route_travel_time(simple_graph, [0, 1, 2, 0]) == pytest.approx(30.0)

    def test_travel_time_closed_edge_returns_inf(
        self, simple_graph: TransportGraph
    ) -> None:
        simple_graph.close_edge(1, 2)
        assert math.isinf(route_travel_time(simple_graph, [0, 1, 2, 0]))


# ═══════════════════════════════════════════════════════════════════════════
# 13. TestCongestionAwareTravelTime
# ═══════════════════════════════════════════════════════════════════════════

class TestCongestionAwareTravelTime:
    """ETA / travel time reflects congestion_factor from TrafficLayer.apply()."""

    def test_heavy_traffic_increases_travel_time(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = TrafficLayer.uniform(simple_graph, TrafficState.HEAVY)
        layer.apply(simple_graph)
        # 3 edges × btt=10.0 × cf=1.6 = 48.0
        result = route_travel_time(simple_graph, [0, 1, 2, 0])
        assert result == pytest.approx(48.0)

    def test_normal_traffic_unchanged(self, simple_graph: TransportGraph) -> None:
        layer = TrafficLayer.uniform(simple_graph, TrafficState.NORMAL)
        layer.apply(simple_graph)
        assert route_travel_time(simple_graph, [0, 1, 2, 0]) == pytest.approx(30.0)

    def test_route_identity_unchanged_by_traffic(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        """Route path does not change when traffic changes — only cost changes."""
        route_manager.register(route_0_1_2_0, simple_graph)
        original_seq = list(route_0_1_2_0.node_sequence)

        TrafficLayer.uniform(simple_graph, TrafficState.HEAVY).apply(simple_graph)

        assert route_0_1_2_0.node_sequence == original_seq  # path unchanged
        # Re-querying gives updated travel time
        new_tt = route_travel_time(simple_graph, route_0_1_2_0.node_sequence)
        assert new_tt == pytest.approx(48.0)


# ═══════════════════════════════════════════════════════════════════════════
# 14. TestETACalculation
# ═══════════════════════════════════════════════════════════════════════════

class TestETACalculation:
    """compute_eta() with various elapsed_minutes values."""

    def test_eta_no_elapsed(self, simple_graph: TransportGraph) -> None:
        eta = compute_eta(simple_graph, [0, 1, 2, 0], elapsed_minutes=0.0)
        assert eta == pytest.approx(30.0)

    def test_eta_partial_elapsed(self, simple_graph: TransportGraph) -> None:
        eta = compute_eta(simple_graph, [0, 1, 2, 0], elapsed_minutes=10.0)
        assert eta == pytest.approx(20.0)

    def test_eta_fully_elapsed_clamps_to_zero(
        self, simple_graph: TransportGraph
    ) -> None:
        eta = compute_eta(simple_graph, [0, 1, 2, 0], elapsed_minutes=35.0)
        assert eta == pytest.approx(0.0)

    def test_eta_closed_edge_returns_inf(
        self, simple_graph: TransportGraph
    ) -> None:
        simple_graph.close_edge(0, 1)
        eta = compute_eta(simple_graph, [0, 1, 2, 0])
        assert math.isinf(eta)


# ═══════════════════════════════════════════════════════════════════════════
# 15. TestRouteAffectedByIncident
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteAffectedByIncident:
    """affected_by_incident() returns routes that overlap with incidents."""

    def test_road_closure_incident_flags_route(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        inc = Incident(
            u=0, v=1,
            type=IncidentType.ROAD_CLOSURE,
            severity=IncidentSeverity.HIGH,
        )
        layer = IncidentLayer.from_incidents([inc])
        affected = route_manager.affected_by_incident(layer)
        assert route_0_1_2_0 in affected

    def test_partial_incident_flags_route(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        inc = Incident(
            u=1, v=2,
            type=IncidentType.ACCIDENT,
            severity=IncidentSeverity.MEDIUM,
        )
        layer = IncidentLayer.from_incidents([inc])
        affected = route_manager.affected_by_incident(layer)
        assert route_0_1_2_0 in affected


# ═══════════════════════════════════════════════════════════════════════════
# 16. TestRouteUnaffectedByIncident
# ═══════════════════════════════════════════════════════════════════════════

class TestRouteUnaffectedByIncident:
    """Routes with no incident overlap are not returned."""

    def test_incident_on_different_edge_does_not_flag_route(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        # Route [0,1,0] uses edges (0,1) and (1,0).
        route = ActiveRoute(
            route_id="R-small",
            vehicle_id="V1",
            depot_node=0,
            node_sequence=[0, 1, 0],
        )
        route_manager.register(route, simple_graph)

        # Incident is on edge (1,2) which is NOT in this route.
        inc = Incident(
            u=1, v=2,
            type=IncidentType.CONSTRUCTION,
            severity=IncidentSeverity.LOW,
        )
        layer = IncidentLayer.from_incidents([inc])
        affected = route_manager.affected_by_incident(layer)
        assert route not in affected

    def test_empty_incident_layer_returns_no_affected_routes(
        self,
        route_manager: RouteManager,
        route_0_1_2_0: ActiveRoute,
        simple_graph: TransportGraph,
    ) -> None:
        route_manager.register(route_0_1_2_0, simple_graph)
        empty_layer = IncidentLayer()
        affected = route_manager.affected_by_incident(empty_layer)
        assert affected == []


# ═══════════════════════════════════════════════════════════════════════════
# 17. TestMultipleRoutesAffectedDetection
# ═══════════════════════════════════════════════════════════════════════════

class TestMultipleRoutesAffectedDetection:
    """Only routes overlapping the incident are returned; mark=True works."""

    def _build_three_routes(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> tuple[ActiveRoute, ActiveRoute, ActiveRoute]:
        r1 = ActiveRoute(
            route_id="R1", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],  # uses (0,1),(1,0)
        )
        r2 = ActiveRoute(
            route_id="R2", vehicle_id="V2",
            depot_node=0, node_sequence=[0, 2, 0],  # uses (0,2),(2,0)
        )
        r3 = ActiveRoute(
            route_id="R3", vehicle_id="V3",
            depot_node=0, node_sequence=[0, 1, 2, 0],  # uses (0,1),(1,2),(2,0)
        )
        for r in (r1, r2, r3):
            route_manager.register(r, simple_graph)
        return r1, r2, r3

    def test_only_overlapping_routes_returned(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        r1, r2, r3 = self._build_three_routes(route_manager, simple_graph)
        # Incident on edge (1,2): only r3 uses this edge
        inc = Incident(u=1, v=2, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        layer = IncidentLayer.from_incidents([inc])
        affected = route_manager.affected_by_incident(layer)
        assert affected == [r3]
        assert r1 not in affected
        assert r2 not in affected

    def test_mark_true_updates_affected_route_status(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        r1, r2, r3 = self._build_three_routes(route_manager, simple_graph)
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        layer = IncidentLayer.from_incidents([inc])
        # r1 and r3 both use edge (0,1)
        route_manager.affected_by_incident(layer, mark=True)
        assert r1.status is RouteStatus.AFFECTED
        assert r3.status is RouteStatus.AFFECTED
        assert r2.status is RouteStatus.ACTIVE  # unaffected; status unchanged

    def test_completed_routes_excluded_from_affected_check(
        self,
        route_manager: RouteManager,
        simple_graph: TransportGraph,
    ) -> None:
        r1, _r2, _r3 = self._build_three_routes(route_manager, simple_graph)
        route_manager.deactivate("R1")  # COMPLETED

        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        layer = IncidentLayer.from_incidents([inc])
        affected = route_manager.affected_by_incident(layer)
        # r1 is COMPLETED; should not appear even though edge (0,1) is affected
        assert r1 not in affected


# ═══════════════════════════════════════════════════════════════════════════
# 18. TestNoGlobalState
# ═══════════════════════════════════════════════════════════════════════════

class TestNoGlobalState:
    """Two RouteManager instances are completely independent."""

    def test_separate_instances_have_separate_registries(
        self, simple_graph: TransportGraph
    ) -> None:
        rm1 = RouteManager()
        rm2 = RouteManager()

        r = ActiveRoute(
            route_id="R1", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],
        )
        rm1.register(r, simple_graph)

        assert len(rm1) == 1
        assert len(rm2) == 0  # rm2 must be unaffected

    def test_removing_from_one_does_not_affect_other(
        self, simple_graph: TransportGraph
    ) -> None:
        rm1 = RouteManager()
        rm2 = RouteManager()

        r1 = ActiveRoute(
            route_id="RA", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],
        )
        r2 = ActiveRoute(
            route_id="RA", vehicle_id="V1",  # same id is fine in a different manager
            depot_node=0, node_sequence=[0, 2, 0],
        )
        rm1.register(r1, simple_graph)
        rm2.register(r2, simple_graph)

        rm1.remove("RA")
        assert len(rm1) == 0
        assert len(rm2) == 1  # rm2's "RA" is untouched


# ═══════════════════════════════════════════════════════════════════════════
# 19. TestEmptyAndMinimalRoutes
# ═══════════════════════════════════════════════════════════════════════════

class TestEmptyAndMinimalRoutes:
    """Edge cases: sequences that are too short or lack required edges."""

    def test_empty_sequence_rejected(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="too short"):
            validate_route(simple_graph, [])

    def test_single_node_rejected(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="too short"):
            validate_route(simple_graph, [0])

    def test_trivial_depot_depot_no_self_loop_rejected(
        self, simple_graph: TransportGraph
    ) -> None:
        """[depot, depot] is invalid because there is no self-loop edge."""
        with pytest.raises(ValueError, match="no directed edge"):
            validate_route(simple_graph, [0, 0])

    def test_minimal_two_stop_route_accepted(
        self, simple_graph: TransportGraph
    ) -> None:
        """[0, 1, 0] is the smallest meaningful real route — must be valid."""
        validate_route(simple_graph, [0, 1, 0])  # must not raise

    def test_register_minimal_route_stamps_correct_metrics(
        self, simple_graph: TransportGraph
    ) -> None:
        rm = RouteManager()
        r = ActiveRoute(
            route_id="R-min", vehicle_id="V1",
            depot_node=0, node_sequence=[0, 1, 0],
        )
        rm.register(r, simple_graph)
        assert r.total_distance == pytest.approx(10.0)   # 2 × 5.0
        assert r.total_travel_time == pytest.approx(20.0) # 2 × 10.0


# ═══════════════════════════════════════════════════════════════════════════
# 20. TestRegressionM1toM7
# ═══════════════════════════════════════════════════════════════════════════

class TestRegressionM1toM7:
    """Verify that all M1–M7 public APIs remain importable and intact."""

    def test_m1_to_m7_public_apis_importable(self) -> None:
        """Import every M1–M7 public symbol to confirm no import breakage."""
        from app.graph import (  # noqa: F401
            TransportGraph,
            WeightConfig,
            shortest_path,
            path_cost,
            generate_synthetic_network,
            build_transport_graph,
        )
        from app.vrp import (  # noqa: F401
            Vehicle,
            Customer,
            VRPProblem,
            VehicleRoute,
            VRPSolution,
            check_feasibility,
            FeasibilityResult,
            compute_fitness,
            FitnessWeights,
            route_components,
        )
        from app.traffic import (  # noqa: F401
            TrafficState,
            TrafficLayer,
            effective_travel_time,
        )
        from app.incidents import (  # noqa: F401
            IncidentType,
            IncidentSeverity,
            Incident,
            IncidentLayer,
        )

    def test_graph_layer_behavior_unchanged(
        self, simple_graph: TransportGraph
    ) -> None:
        """shortest_path and edge_cost work exactly as before M8."""
        from app.graph import shortest_path, WeightConfig
        wc = WeightConfig()
        path, cost = shortest_path(simple_graph, 0, 2, wc)
        assert 0 in path
        assert 2 in path
        assert cost > 0.0

    def test_traffic_layer_behavior_unchanged(
        self, simple_graph: TransportGraph
    ) -> None:
        """TrafficLayer.apply/reset leaves congestion_factor correct."""
        layer = TrafficLayer.uniform(simple_graph, TrafficState.HEAVY)
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(1.6)
        layer.reset(simple_graph)
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(1.0)

    def test_incident_layer_behavior_unchanged(
        self, simple_graph: TransportGraph
    ) -> None:
        """IncidentLayer.apply sets road_status to closed and reset restores it."""
        inc = Incident(
            u=0, v=1,
            type=IncidentType.ROAD_CLOSURE,
            severity=IncidentSeverity.HIGH,
        )
        layer = IncidentLayer.from_incidents([inc])
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED
        layer.reset(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN

    def test_vrp_route_components_behavior_unchanged(
        self, simple_graph: TransportGraph
    ) -> None:
        """route_components still returns correct (travel_time, distance, cong)."""
        from app.vrp.objective import route_components
        tt, dist, cong = route_components(simple_graph, [0, 1, 2, 0])
        assert tt   == pytest.approx(30.0)
        assert dist == pytest.approx(15.0)
        assert cong == pytest.approx(0.0)   # cf=1.0, so cong = sum(cf-1) = 0
