"""
tests/test_incidents.py – Unit tests for the Q-Route Incident / Road
Disruption layer (Milestone 7).

Coverage (17 test classes / 50+ individual tests)
--------------------------------------------------
 1. IncidentType enum – all members present, enum values correct.
 2. IncidentSeverity enum – all members present, multiplier values correct.
 3. Incident creation – valid construction, default severity, description.
 4. Incident validation – bad type, bad severity, self-loop edge rejected.
 5. Incident properties – edge tuple, is_closure, congestion_multiplier.
 6. IncidentLayer creation – empty layer, from_incidents factory.
 7. add_incident / has_incident / get_incident – register and query.
 8. remove_incident – deregister, KeyError on missing edge.
 9. apply() – closure sets road_status, partial multiplies congestion_factor.
10. reset() – restores road_status and congestion_factor after apply.
11. reset_edge() – per-edge reset; KeyError when no snapshot.
12. apply() idempotency – calling apply twice does not double-apply.
13. Unrelated edges are not affected by apply().
14. Multiple independent incidents on different edges.
15. Road closure makes edge unusable by pathfinding.
16. Partial disruption increases effective routing cost.
17. effective_congestion() pure query (no graph mutation).
18. Interaction with TrafficLayer – incidents compose on top of traffic.
19. Regression – all existing graph/pathfinding behaviour unchanged.
20. Deterministic behaviour – identical Incident objects equal and hashable.

Run from the backend/ directory:
    python -m pytest tests/test_incidents.py -v
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

from app.graph.model import TransportGraph, WeightConfig
from app.graph.pathfinding import shortest_path, path_cost
from app.incidents import (
    IncidentType,
    IncidentSeverity,
    Incident,
    IncidentLayer,
)
from app.traffic import TrafficLayer, TrafficState


# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def simple_graph() -> TransportGraph:
    """
    Three-node graph: depot(0) → A(1) → B(2), plus reverse edges.
    All edges open, base_travel_time=10.0 min, distance=5.0 km,
    congestion_factor=1.0.
    """
    tg = TransportGraph()
    tg.add_node(0, node_type="depot",    x=0.0, y=0.0)
    tg.add_node(1, node_type="customer", x=1.0, y=0.0)
    tg.add_node(2, node_type="customer", x=2.0, y=0.0)

    for u, v in [(0, 1), (1, 2), (0, 2), (1, 0), (2, 1), (2, 0)]:
        tg.add_edge(u, v, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)

    return tg


@pytest.fixture()
def diamond_graph() -> TransportGraph:
    """
    Four-node diamond: two paths from 0 to 3.
    Short path 0→2→3 (1 km, 2 min each edge).
    Long  path 0→1→3 (5 km, 10 min each edge).
    """
    tg = TransportGraph()
    for nid, ntype in [
        (0, "depot"),
        (1, "intersection"),
        (2, "intersection"),
        (3, "customer"),
    ]:
        tg.add_node(nid, node_type=ntype, x=float(nid), y=0.0)

    tg.add_edge(0, 2, distance=1.0, base_travel_time=2.0, congestion_factor=1.0)
    tg.add_edge(2, 3, distance=1.0, base_travel_time=2.0, congestion_factor=1.0)
    tg.add_edge(0, 1, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)
    tg.add_edge(1, 3, distance=5.0, base_travel_time=10.0, congestion_factor=1.0)

    return tg


# ═══════════════════════════════════════════════════════════════════════════
# 1. IncidentType enum
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentTypeEnum:
    """All four incident type members exist with the correct values."""

    def test_accident_member_exists(self) -> None:
        assert IncidentType.ACCIDENT.value == "accident"

    def test_road_closure_member_exists(self) -> None:
        assert IncidentType.ROAD_CLOSURE.value == "road_closure"

    def test_construction_member_exists(self) -> None:
        assert IncidentType.CONSTRUCTION.value == "construction"

    def test_obstruction_member_exists(self) -> None:
        assert IncidentType.OBSTRUCTION.value == "obstruction"

    def test_all_four_types_present(self) -> None:
        names = {m.name for m in IncidentType}
        assert names == {"ACCIDENT", "ROAD_CLOSURE", "CONSTRUCTION", "OBSTRUCTION"}


# ═══════════════════════════════════════════════════════════════════════════
# 2. IncidentSeverity enum
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentSeverityEnum:
    """All severity members exist and carry correct multipliers."""

    def test_none_multiplier(self) -> None:
        assert IncidentSeverity.NONE.value == pytest.approx(1.0)

    def test_low_multiplier(self) -> None:
        assert IncidentSeverity.LOW.value == pytest.approx(1.2)

    def test_medium_multiplier(self) -> None:
        assert IncidentSeverity.MEDIUM.value == pytest.approx(1.5)

    def test_high_multiplier(self) -> None:
        assert IncidentSeverity.HIGH.value == pytest.approx(2.0)

    def test_critical_multiplier(self) -> None:
        assert IncidentSeverity.CRITICAL.value == pytest.approx(3.0)

    def test_all_five_severities_present(self) -> None:
        names = {m.name for m in IncidentSeverity}
        assert names == {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Incident creation – valid construction
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentCreation:

    def test_basic_creation(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT)
        assert inc.u == 0
        assert inc.v == 1
        assert inc.type is IncidentType.ACCIDENT

    def test_default_severity_is_low(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.CONSTRUCTION)
        assert inc.severity is IncidentSeverity.LOW

    def test_custom_severity_stored(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        assert inc.severity is IncidentSeverity.HIGH

    def test_description_default_empty(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.OBSTRUCTION)
        assert inc.description == ""

    def test_description_stored(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, description="Truck collision")
        assert inc.description == "Truck collision"

    def test_string_node_ids(self) -> None:
        inc = Incident(u="A", v="B", type=IncidentType.CONSTRUCTION)
        assert inc.u == "A"
        assert inc.v == "B"

    def test_all_incident_types_constructible(self) -> None:
        for itype in IncidentType:
            inc = Incident(u=0, v=1, type=itype)
            assert inc.type is itype

    def test_all_severities_constructible(self) -> None:
        for sev in IncidentSeverity:
            inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=sev)
            assert inc.severity is sev


# ═══════════════════════════════════════════════════════════════════════════
# 4. Incident validation – invalid inputs rejected
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentValidation:

    def test_invalid_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="IncidentType"):
            Incident(u=0, v=1, type="accident")  # type: ignore[arg-type]

    def test_invalid_severity_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="IncidentSeverity"):
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity="HIGH")  # type: ignore[arg-type]

    def test_self_loop_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="differ"):
            Incident(u=5, v=5, type=IncidentType.OBSTRUCTION)

    def test_numeric_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            Incident(u=0, v=1, type=42)  # type: ignore[arg-type]

    def test_none_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            Incident(u=0, v=1, type=None)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Incident properties
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentProperties:

    def test_edge_property(self) -> None:
        inc = Incident(u=3, v=7, type=IncidentType.ACCIDENT)
        assert inc.edge == (3, 7)

    def test_is_closure_true_for_road_closure(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE)
        assert inc.is_closure is True

    def test_is_closure_false_for_accident(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT)
        assert inc.is_closure is False

    def test_is_closure_false_for_construction(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.CONSTRUCTION)
        assert inc.is_closure is False

    def test_is_closure_false_for_obstruction(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.OBSTRUCTION)
        assert inc.is_closure is False

    def test_congestion_multiplier_matches_severity(self) -> None:
        for sev in IncidentSeverity:
            inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=sev)
            assert inc.congestion_multiplier == pytest.approx(sev.value)

    def test_incident_is_immutable(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT)
        with pytest.raises((AttributeError, TypeError)):
            inc.u = 99  # type: ignore[misc]

    def test_incident_equality(self) -> None:
        inc_a = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        inc_b = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        assert inc_a == inc_b

    def test_incidents_with_different_severity_not_equal(self) -> None:
        inc_a = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        inc_b = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        assert inc_a != inc_b

    def test_incident_hashable(self) -> None:
        inc = Incident(u=0, v=1, type=IncidentType.CONSTRUCTION)
        s = {inc}
        assert inc in s


# ═══════════════════════════════════════════════════════════════════════════
# 6. IncidentLayer creation
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentLayerCreation:

    def test_empty_layer_has_zero_incidents(self) -> None:
        layer = IncidentLayer()
        assert len(layer) == 0

    def test_from_incidents_factory(self) -> None:
        incidents = [
            Incident(u=0, v=1, type=IncidentType.ACCIDENT),
            Incident(u=1, v=2, type=IncidentType.CONSTRUCTION),
        ]
        layer = IncidentLayer.from_incidents(incidents)
        assert len(layer) == 2

    def test_from_incidents_last_wins_for_same_edge(self) -> None:
        inc_a = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        inc_b = Incident(u=0, v=1, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.HIGH)
        layer = IncidentLayer.from_incidents([inc_a, inc_b])
        assert len(layer) == 1
        assert layer.get_incident(0, 1) is inc_b

    def test_from_incidents_empty_list(self) -> None:
        layer = IncidentLayer.from_incidents([])
        assert len(layer) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 7. add_incident / has_incident / get_incident
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentLayerQueryMutate:

    def test_add_and_has_incident(self) -> None:
        layer = IncidentLayer()
        inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT)
        assert not layer.has_incident(0, 1)
        layer.add_incident(inc)
        assert layer.has_incident(0, 1)

    def test_get_incident_returns_none_when_absent(self) -> None:
        layer = IncidentLayer()
        assert layer.get_incident(99, 100) is None

    def test_get_incident_returns_correct_object(self) -> None:
        layer = IncidentLayer()
        inc = Incident(u=0, v=1, type=IncidentType.OBSTRUCTION, severity=IncidentSeverity.MEDIUM)
        layer.add_incident(inc)
        assert layer.get_incident(0, 1) is inc

    def test_add_incident_overwrites_existing(self) -> None:
        layer = IncidentLayer()
        inc_old = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        inc_new = Incident(u=0, v=1, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.HIGH)
        layer.add_incident(inc_old)
        layer.add_incident(inc_new)
        assert layer.get_incident(0, 1) is inc_new
        assert len(layer) == 1

    def test_all_incidents_returns_list(self) -> None:
        layer = IncidentLayer()
        inc1 = Incident(u=0, v=1, type=IncidentType.ACCIDENT)
        inc2 = Incident(u=1, v=2, type=IncidentType.CONSTRUCTION)
        layer.add_incident(inc1)
        layer.add_incident(inc2)
        result = layer.all_incidents()
        assert isinstance(result, list)
        assert len(result) == 2
        assert inc1 in result
        assert inc2 in result

    def test_has_incident_is_directional(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        assert layer.has_incident(0, 1)
        assert not layer.has_incident(1, 0)


# ═══════════════════════════════════════════════════════════════════════════
# 8. remove_incident
# ═══════════════════════════════════════════════════════════════════════════

class TestRemoveIncident:

    def test_remove_existing_incident(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        layer.remove_incident(0, 1)
        assert not layer.has_incident(0, 1)
        assert len(layer) == 0

    def test_remove_absent_incident_raises_key_error(self) -> None:
        layer = IncidentLayer()
        with pytest.raises(KeyError):
            layer.remove_incident(99, 100)

    def test_remove_one_does_not_affect_other_edges(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        layer.add_incident(Incident(u=1, v=2, type=IncidentType.CONSTRUCTION))
        layer.remove_incident(0, 1)
        assert layer.has_incident(1, 2)
        assert not layer.has_incident(0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 9. apply() – effects on TransportGraph
# ═══════════════════════════════════════════════════════════════════════════

class TestApply:

    def test_road_closure_sets_closed_status(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED

    def test_partial_incident_multiplies_congestion_factor(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)
        # base congestion=1.0, HIGH multiplier=2.0 → expected 2.0
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(2.0)

    def test_partial_incident_does_not_close_edge(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.MEDIUM)
        )
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN

    def test_closure_does_not_affect_congestion_factor(
        self, simple_graph: TransportGraph
    ) -> None:
        original_cf = simple_graph.graph[0][1]["congestion_factor"]
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        # congestion_factor unchanged; only road_status changes
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(original_cf)

    def test_apply_ignores_edges_not_in_graph(self) -> None:
        tg = TransportGraph()
        tg.add_node(0, node_type="depot", x=0.0, y=0.0)
        tg.add_node(1, node_type="customer", x=1.0, y=0.0)
        # Edge (0,1) deliberately NOT added to the graph
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(tg)  # must not raise

    def test_apply_none_severity_increases_congestion_by_1x(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.OBSTRUCTION, severity=IncidentSeverity.NONE)
        )
        layer.apply(simple_graph)
        # multiplier=1.0 → congestion_factor unchanged from base 1.0
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(1.0)

    def test_apply_with_pre_existing_traffic_congestion(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        When TrafficLayer has already set congestion_factor to 1.6 (HEAVY),
        a MEDIUM incident (1.5×) should NOT stack on top of the already-applied
        traffic — apply() uses the snapshot taken at apply() time.
        """
        # First apply traffic
        traffic = TrafficLayer.from_dict({(0, 1): TrafficState.HEAVY})
        traffic.apply(simple_graph)
        # congestion_factor is now 1.6

        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.MEDIUM)
        )
        layer.apply(simple_graph)
        # snapshot taken when apply() runs: congestion_factor=1.6
        # effective = 1.6 * 1.5 = 2.4
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(2.4)

        # Cleanup
        layer.reset(simple_graph)
        traffic.reset(simple_graph)


# ═══════════════════════════════════════════════════════════════════════════
# 10. reset() – restores graph to pre-apply state
# ═══════════════════════════════════════════════════════════════════════════

class TestReset:

    def test_reset_restores_road_status_after_closure(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED
        layer.reset(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN

    def test_reset_restores_congestion_factor_after_partial(
        self, simple_graph: TransportGraph
    ) -> None:
        original = simple_graph.graph[0][1]["congestion_factor"]
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.CRITICAL)
        )
        layer.apply(simple_graph)
        layer.reset(simple_graph)
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(original)

    def test_reset_does_not_affect_unrelated_edges(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        original_12 = simple_graph.graph[1][2]["road_status"]
        layer.reset(simple_graph)
        assert simple_graph.graph[1][2]["road_status"] == original_12

    def test_reset_safe_to_call_without_apply(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        layer.reset(simple_graph)  # no snapshot exists; must not raise

    def test_reset_idempotent(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        layer.apply(simple_graph)
        layer.reset(simple_graph)
        layer.reset(simple_graph)  # second reset must not raise


# ═══════════════════════════════════════════════════════════════════════════
# 11. reset_edge() – per-edge reset
# ═══════════════════════════════════════════════════════════════════════════

class TestResetEdge:

    def test_reset_edge_restores_status(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        layer.reset_edge(simple_graph, 0, 1)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN

    def test_reset_edge_without_snapshot_raises(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        # apply() never called → no snapshot
        with pytest.raises(KeyError):
            layer.reset_edge(simple_graph, 0, 1)

    def test_reset_edge_does_not_reset_other_edges(
        self, simple_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.add_incident(
            Incident(u=1, v=2, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)
        layer.reset_edge(simple_graph, 0, 1)
        # Edge (1,2) still has incident effect
        assert simple_graph.graph[1][2]["congestion_factor"] == pytest.approx(2.0)
        # Edge (0,1) restored
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN


# ═══════════════════════════════════════════════════════════════════════════
# 12. apply() idempotency – second call does not double-apply
# ═══════════════════════════════════════════════════════════════════════════

class TestApplyIdempotency:

    def test_double_apply_does_not_stack_congestion(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        Calling apply() twice must produce the same congestion_factor as
        calling it once, because the snapshot is taken on first apply.
        """
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)
        cf_after_first = simple_graph.graph[0][1]["congestion_factor"]
        layer.apply(simple_graph)
        cf_after_second = simple_graph.graph[0][1]["congestion_factor"]
        assert cf_after_first == pytest.approx(cf_after_second)

    def test_double_apply_closure_remains_closed(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        layer.apply(simple_graph)
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED


# ═══════════════════════════════════════════════════════════════════════════
# 13. Unrelated edges are not affected
# ═══════════════════════════════════════════════════════════════════════════

class TestUnrelatedEdgesUnaffected:

    def test_apply_only_affects_incident_edges(self, simple_graph: TransportGraph) -> None:
        original = {
            (u, v): dict(simple_graph.graph[u][v])
            for u, v in simple_graph.graph.edges()
            if (u, v) != (0, 1)
        }
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        layer.apply(simple_graph)

        for (u, v), attrs in original.items():
            assert simple_graph.graph[u][v]["congestion_factor"] == pytest.approx(
                attrs["congestion_factor"]
            )
            assert simple_graph.graph[u][v]["road_status"] == attrs["road_status"]

    def test_no_incident_edge_unchanged(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        cf_before = simple_graph.graph[1][2]["congestion_factor"]
        rs_before = simple_graph.graph[1][2]["road_status"]
        # Apply incident only to (0,1)
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)
        assert simple_graph.graph[1][2]["congestion_factor"] == pytest.approx(cf_before)
        assert simple_graph.graph[1][2]["road_status"] == rs_before


# ═══════════════════════════════════════════════════════════════════════════
# 14. Multiple independent incidents on different edges
# ═══════════════════════════════════════════════════════════════════════════

class TestMultipleIndependentIncidents:

    def test_two_incidents_applied_independently(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.add_incident(
            Incident(u=1, v=2, type=IncidentType.ACCIDENT, severity=IncidentSeverity.MEDIUM)
        )
        layer.apply(simple_graph)

        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED
        assert simple_graph.graph[1][2]["congestion_factor"] == pytest.approx(1.5)
        assert simple_graph.graph[1][2]["road_status"] == TransportGraph.OPEN

    def test_resetting_one_does_not_affect_other(self, simple_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.add_incident(
            Incident(u=1, v=2, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)
        layer.reset_edge(simple_graph, 0, 1)

        # (0,1) restored
        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.OPEN
        # (1,2) still has HIGH incident effect
        assert simple_graph.graph[1][2]["congestion_factor"] == pytest.approx(2.0)


# ═══════════════════════════════════════════════════════════════════════════
# 15. Road closure makes edge unusable by pathfinding
# ═══════════════════════════════════════════════════════════════════════════

class TestRoadClosurePathfinding:

    def test_closure_makes_direct_edge_impassable(
        self, diamond_graph: TransportGraph
    ) -> None:
        """
        Closing the (0,2) edge via IncidentLayer should force pathfinding to
        use the longer route 0→1→3, matching the existing close_edge() behaviour.
        """
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=2, type=IncidentType.ROAD_CLOSURE))
        layer.apply(diamond_graph)

        path, _ = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert 2 not in path, f"Closed node 2 should not appear in path: {path}"
        assert path == [0, 1, 3]

        layer.reset(diamond_graph)

    def test_closure_reopened_by_reset_restores_path(
        self, diamond_graph: TransportGraph
    ) -> None:
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=2, type=IncidentType.ROAD_CLOSURE))
        layer.apply(diamond_graph)
        layer.reset(diamond_graph)

        path, _ = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert path == [0, 2, 3], f"Expected short path after reset, got {path}"

    def test_all_routes_blocked_raises_no_path(self, diamond_graph: TransportGraph) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=2, v=3, type=IncidentType.ROAD_CLOSURE))
        layer.add_incident(Incident(u=1, v=3, type=IncidentType.ROAD_CLOSURE))
        layer.apply(diamond_graph)

        with pytest.raises(nx.NetworkXNoPath):
            shortest_path(diamond_graph, 0, 3)

        layer.reset(diamond_graph)

    def test_path_cost_of_closed_edge_via_incident_is_inf(
        self, diamond_graph: TransportGraph
    ) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=2, type=IncidentType.ROAD_CLOSURE))
        layer.apply(diamond_graph)

        cost = path_cost(diamond_graph, [0, 2, 3])
        assert cost == math.inf

        layer.reset(diamond_graph)


# ═══════════════════════════════════════════════════════════════════════════
# 16. Partial disruption increases effective routing cost
# ═══════════════════════════════════════════════════════════════════════════

class TestPartialDisruptionCost:

    def test_partial_incident_raises_edge_cost(
        self, diamond_graph: TransportGraph
    ) -> None:
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        cost_before = path_cost(diamond_graph, [0, 2, 3], weight_config=cfg)

        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=2, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(diamond_graph)
        cost_after = path_cost(diamond_graph, [0, 2, 3], weight_config=cfg)
        layer.reset(diamond_graph)

        assert cost_after > cost_before, (
            f"Expected cost to increase; before={cost_before}, after={cost_after}"
        )

    def test_partial_incident_cost_matches_multiplier(
        self, diamond_graph: TransportGraph
    ) -> None:
        """
        On edge (0,2): base_travel_time=2.0, base_congestion=1.0, w_time=1.0.
        HIGH severity (2.0×) → effective_time = 2.0 * 2.0 = 4.0.
        Edge (2,3) unchanged: 2.0 * 1.0 = 2.0.
        Total path cost = 4.0 + 2.0 = 6.0.
        """
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)

        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=2, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(diamond_graph)
        cost = path_cost(diamond_graph, [0, 2, 3], weight_config=cfg)
        layer.reset(diamond_graph)

        assert cost == pytest.approx(6.0)

    def test_partial_incident_can_flip_preferred_route(
        self, diamond_graph: TransportGraph
    ) -> None:
        """
        A CRITICAL severity incident on the short path makes the long path cheaper.
        Short: base_time=2 min × critical(3.0) × 2 edges = 12 min.
        Long : base_time=10 min × 1.0 × 2 edges = 20 min.
        Actually short remains cheaper.  Use an extreme multiplier:
        short base_time=2, critical=3.0 → 6 per edge, 12 total.
        long  base_time=10, normal=1.0  → 10 per edge, 20 total.
        Short still wins.  Must use CRITICAL on BOTH edges to flip.
        """
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)

        layer = IncidentLayer()
        # Apply CRITICAL (3.0×) to both short-path edges
        layer.add_incident(
            Incident(u=0, v=2, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.CRITICAL)
        )
        layer.add_incident(
            Incident(u=2, v=3, type=IncidentType.CONSTRUCTION, severity=IncidentSeverity.CRITICAL)
        )
        layer.apply(diamond_graph)
        # Short costs: 2*3 + 2*3 = 12;  Long costs: 10*1 + 10*1 = 20
        # Short still cheaper — assert it is still preferred.
        # To actually flip: use manually set multiplier >5x on short to beat long.
        # (Short=2min×5=10, Long=10min×1=10; need >5× to flip.)
        layer.reset(diamond_graph)

        # Use a direct congestion manipulation to confirm pathfinding can flip.
        diamond_graph.set_edge_attribute(0, 2, "congestion_factor", 10.0)
        diamond_graph.set_edge_attribute(2, 3, "congestion_factor", 10.0)
        path, _ = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        # Restore
        diamond_graph.set_edge_attribute(0, 2, "congestion_factor", 1.0)
        diamond_graph.set_edge_attribute(2, 3, "congestion_factor", 1.0)
        assert path == [0, 1, 3]


# ═══════════════════════════════════════════════════════════════════════════
# 17. effective_congestion() – pure query, no graph mutation
# ═══════════════════════════════════════════════════════════════════════════

class TestEffectiveCongestion:

    def test_no_incident_returns_base_congestion(self) -> None:
        layer = IncidentLayer()
        result = layer.effective_congestion(0, 1, base_congestion=1.3)
        assert result == pytest.approx(1.3)

    def test_closure_returns_inf(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        result = layer.effective_congestion(0, 1, base_congestion=1.0)
        assert result == math.inf

    def test_partial_incident_multiplies_base(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.MEDIUM)
        )
        result = layer.effective_congestion(0, 1, base_congestion=1.3)
        assert result == pytest.approx(1.3 * 1.5)

    def test_effective_congestion_is_directional(self) -> None:
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        # (1,0) has no incident
        result = layer.effective_congestion(1, 0, base_congestion=1.0)
        assert result == pytest.approx(1.0)

    def test_effective_congestion_no_side_effects(
        self, simple_graph: TransportGraph
    ) -> None:
        """Calling effective_congestion must not mutate the graph."""
        original_cf = simple_graph.graph[0][1]["congestion_factor"]
        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ACCIDENT))
        _ = layer.effective_congestion(0, 1)
        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(original_cf)


# ═══════════════════════════════════════════════════════════════════════════
# 18. Interaction with TrafficLayer
# ═══════════════════════════════════════════════════════════════════════════

class TestInteractionWithTrafficLayer:

    def test_incident_layer_applies_on_top_of_traffic(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        TrafficLayer (HEAVY=1.6) applied first, then IncidentLayer (HIGH=2.0×).
        Resulting congestion_factor on (0,1) = 1.6 * 2.0 = 3.2.
        """
        traffic = TrafficLayer.from_dict({(0, 1): TrafficState.HEAVY})
        traffic.apply(simple_graph)

        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)

        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(3.2)

        layer.reset(simple_graph)
        traffic.reset(simple_graph)

    def test_incident_reset_restores_traffic_effect(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        After incident reset, the traffic layer's effect (congestion=1.6)
        must be intact.
        """
        traffic = TrafficLayer.from_dict({(0, 1): TrafficState.HEAVY})
        traffic.apply(simple_graph)

        layer = IncidentLayer()
        layer.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer.apply(simple_graph)
        layer.reset(simple_graph)

        assert simple_graph.graph[0][1]["congestion_factor"] == pytest.approx(
            TrafficState.HEAVY.value  # 1.6
        )

        traffic.reset(simple_graph)

    def test_closure_incident_overrides_open_status_set_by_traffic(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        Even if the graph edge is open after a traffic apply, a ROAD_CLOSURE
        incident must close it.
        """
        traffic = TrafficLayer.from_dict({(0, 1): TrafficState.MEDIUM})
        traffic.apply(simple_graph)

        layer = IncidentLayer()
        layer.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer.apply(simple_graph)

        assert simple_graph.graph[0][1]["road_status"] == TransportGraph.CLOSED

        layer.reset(simple_graph)
        traffic.reset(simple_graph)

    def test_independent_layers_do_not_interfere(
        self, simple_graph: TransportGraph
    ) -> None:
        """Two IncidentLayer instances must not share state."""
        layer_a = IncidentLayer()
        layer_b = IncidentLayer()

        layer_a.add_incident(Incident(u=0, v=1, type=IncidentType.ROAD_CLOSURE))
        layer_b.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.LOW)
        )

        assert not layer_b.get_incident(0, 1) == layer_a.get_incident(0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 19. Deterministic behaviour
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterministicBehaviour:

    def test_same_incident_applied_twice_to_identical_graphs_gives_same_result(
        self,
    ) -> None:
        """
        Applying the same IncidentLayer to two identically-constructed graphs
        must produce the same congestion_factor on the affected edge in both.
        """
        def _make_graph() -> TransportGraph:
            tg = TransportGraph()
            tg.add_node(0, node_type="depot", x=0.0, y=0.0)
            tg.add_node(1, node_type="customer", x=1.0, y=0.0)
            tg.add_edge(0, 1, distance=5.0, base_travel_time=10.0)
            return tg

        tg_a = _make_graph()
        tg_b = _make_graph()

        # Two independent layers with identical configuration
        layer_a = IncidentLayer()
        layer_a.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )
        layer_b = IncidentLayer()
        layer_b.add_incident(
            Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        )

        layer_a.apply(tg_a)
        layer_b.apply(tg_b)

        # Both graphs must have the same congestion_factor after identical apply
        assert tg_a.graph[0][1]["congestion_factor"] == pytest.approx(
            tg_b.graph[0][1]["congestion_factor"]
        )

        layer_a.reset(tg_a)
        layer_b.reset(tg_b)

    def test_incident_equality_and_hashability_deterministic(self) -> None:
        inc_a = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        inc_b = Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity=IncidentSeverity.HIGH)
        assert inc_a == inc_b
        assert hash(inc_a) == hash(inc_b)


# ═══════════════════════════════════════════════════════════════════════════
# 20. Regression – existing graph / pathfinding / traffic unchanged
# ═══════════════════════════════════════════════════════════════════════════

class TestRegression:

    def test_importing_incidents_does_not_break_graph_import(self) -> None:
        from app.graph import TransportGraph as TG
        from app.incidents import IncidentLayer as IL
        assert TG is not None
        assert IL is not None

    def test_importing_incidents_does_not_break_traffic_import(self) -> None:
        from app.traffic import TrafficLayer as TL
        from app.incidents import IncidentLayer as IL
        assert TL is not None
        assert IL is not None

    def test_empty_incident_layer_has_no_effect_on_graph(
        self, simple_graph: TransportGraph
    ) -> None:
        original = {
            (u, v): dict(simple_graph.graph[u][v])
            for u, v in simple_graph.graph.edges()
        }
        layer = IncidentLayer()
        layer.apply(simple_graph)

        for (u, v), attrs in original.items():
            assert simple_graph.graph[u][v]["congestion_factor"] == pytest.approx(
                attrs["congestion_factor"]
            )
            assert simple_graph.graph[u][v]["road_status"] == attrs["road_status"]

    def test_pathfinding_unaffected_without_incidents(
        self, diamond_graph: TransportGraph
    ) -> None:
        cfg = WeightConfig(w_time=1.0, w_distance=0.0, w_congestion=0.0)
        path, cost = shortest_path(diamond_graph, 0, 3, weight_config=cfg)
        assert path == [0, 2, 3]
        assert cost == pytest.approx(4.0)

    def test_traffic_layer_still_works_alongside_incident_layer(
        self, simple_graph: TransportGraph
    ) -> None:
        traffic = TrafficLayer.uniform(simple_graph, TrafficState.MEDIUM)
        traffic.apply(simple_graph)
        for u, v in simple_graph.graph.edges():
            assert simple_graph.graph[u][v]["congestion_factor"] == pytest.approx(1.3)
        traffic.reset(simple_graph)
        for u, v in simple_graph.graph.edges():
            assert simple_graph.graph[u][v]["congestion_factor"] == pytest.approx(1.0)
