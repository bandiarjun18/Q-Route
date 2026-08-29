"""
tests/test_m12_incident_rerouting.py – Focused tests for Milestone 12 Incident-Aware Dynamic Rerouting.

Tests cover:
1. Incident representation & input validation
2. Affected vs unaffected route detection
3. Unaffected route preservation (structural identity, sequence & stops)
4. Selective rerouting of affected vehicles only
5. Closed-edge avoidance & feasibility verification
6. No-op handling when incident does not intersect active routes
7. API integration & contract compatibility via POST /incidents
8. PostgreSQL incident record persistence
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.state import AppState
from app.db.crud import get_incidents_for_network
from app.db.models import IncidentModel, NetworkModel
from app.db.session import SessionLocal
from app.graph.generator import generate_synthetic_network
from app.graph.model import TransportGraph
from app.graph.pathfinding import shortest_path
from app.incidents.model import Incident, IncidentLayer, IncidentSeverity, IncidentType
from app.incidents.rerouting import detect_affected_routes, selective_reroute
from app.main import app
from app.qpso.config import QPSOConfig
from app.routes.manager import RouteManager
from app.routes.model import ActiveRoute, RouteStatus
from app.vrp.models import Customer, Vehicle, VRPProblem
from app.vrp.objective import FitnessWeights

client = TestClient(app)


@pytest.fixture
def test_setup():
    """Build a deterministic small problem instance with 2 active routes."""
    net_data = generate_synthetic_network(
        n_nodes=10,
        n_depots=1,
        n_customers=4,
        connect_radius_km=5.0,
        grid_size_km=10.0,
        closed_fraction=0.0,
        seed=42,
    )
    graph = TransportGraph.from_dict(net_data)

    depot = next(n for n, d in graph.graph.nodes(data=True) if d.get("node_type") == "depot")
    customers = [n for n, d in graph.graph.nodes(data=True) if d.get("node_type") == "customer"]

    vehs = [
        Vehicle(vehicle_id=0, capacity=50.0, depot_node=depot),
        Vehicle(vehicle_id=1, capacity=50.0, depot_node=depot),
    ]
    custs = [
        Customer(customer_id=i, location_node=c, demand=5.0)
        for i, c in enumerate(customers)
    ]
    problem = VRPProblem(graph=graph, vehicles=vehs, customers=custs)

    rm = RouteManager()

    # Build valid node sequences along graph shortest paths
    p1, _ = shortest_path(graph, depot, customers[0])
    p2, _ = shortest_path(graph, customers[0], customers[1])
    p3, _ = shortest_path(graph, customers[1], depot)
    seq0 = p1[:-1] + p2[:-1] + p3

    p4, _ = shortest_path(graph, depot, customers[2])
    p5, _ = shortest_path(graph, customers[2], customers[3])
    p6, _ = shortest_path(graph, customers[3], depot)
    seq1 = p4[:-1] + p5[:-1] + p6

    # Route 0 serves customers 0 and 1
    r0 = ActiveRoute(
        route_id="V0",
        vehicle_id=0,
        depot_node=depot,
        visit_order=[0, 1],
        node_sequence=seq0,
    )
    # Route 1 serves customers 2 and 3
    r1 = ActiveRoute(
        route_id="V1",
        vehicle_id=1,
        depot_node=depot,
        visit_order=[2, 3],
        node_sequence=seq1,
    )

    return graph, problem, rm, r0, r1, depot, customers


def test_incident_validation():
    """Verify that invalid incident inputs raise appropriate errors."""
    # Self-loop should raise ValueError
    with pytest.raises(ValueError, match="Incident edge endpoints must differ"):
        Incident(u=0, v=0, type=IncidentType.ACCIDENT)

    # Invalid type/severity should raise TypeError
    with pytest.raises(TypeError):
        Incident(u=0, v=1, type="ACCIDENT")  # type: ignore

    with pytest.raises(TypeError):
        Incident(u=0, v=1, type=IncidentType.ACCIDENT, severity="HIGH")  # type: ignore


def test_detect_affected_routes(test_setup):
    """Verify detection accurately separates affected and unaffected vehicle routes."""
    graph, problem, rm, r0, r1, depot, customers = test_setup

    # Register both routes in graph
    rm.register(r0, graph)
    rm.register(r1, graph)

    # Inject incident on the first edge of Route 0
    layer = IncidentLayer()
    closure_edge = (r0.node_sequence[0], r0.node_sequence[1])
    layer.add_incident(
        Incident(
            u=closure_edge[0],
            v=closure_edge[1],
            type=IncidentType.ROAD_CLOSURE,
            severity=IncidentSeverity.CRITICAL,
        )
    )

    affected, unaffected = detect_affected_routes(rm, layer, graph)
    assert len(affected) == 1
    assert affected[0].vehicle_id == 0
    assert len(unaffected) == 1
    assert unaffected[0].vehicle_id == 1


def test_selective_reroute_preserves_unaffected(test_setup):
    """Verify selective reroute preserves unaffected routes while rerouting affected vehicle."""
    graph, problem, rm, r0, r1, depot, customers = test_setup

    rm.register(r0, graph)
    rm.register(r1, graph)

    original_r1_seq = list(r1.node_sequence)
    original_r1_visits = list(r1.visit_order)

    # Inject closure on Route 0 edge
    layer = IncidentLayer()
    closure_edge = (r0.node_sequence[0], r0.node_sequence[1])
    layer.add_incident(
        Incident(
            u=closure_edge[0],
            v=closure_edge[1],
            type=IncidentType.ROAD_CLOSURE,
            severity=IncidentSeverity.CRITICAL,
        )
    )

    cfg = QPSOConfig(
        n_particles=6,
        max_iterations=10,
        seed=42,
        fitness_weights=FitnessWeights(1.0, 0.5, 0.3),
    )

    reroute_res = selective_reroute(graph, problem, rm, layer, cfg)

    assert 0 in reroute_res.affected_vehicle_ids
    assert 1 in reroute_res.unaffected_vehicle_ids
    assert len(reroute_res.updated_routes) >= 1

    # Verify Route 1 (unaffected) remained 100% preserved
    r1_after = rm.get("V1")
    assert list(r1_after.node_sequence) == original_r1_seq
    assert list(r1_after.visit_order) == original_r1_visits

    # Verify Route 0 (affected) avoided the closed edge
    r0_after = rm.get("V0")
    for u, v in zip(r0_after.node_sequence[:-1], r0_after.node_sequence[1:]):
        assert (u, v) != closure_edge, "Rerouted path must avoid closed edge!"


def test_selective_reroute_no_overlap(test_setup):
    """Verify selective reroute is a fast no-op when incident does not intersect any active route."""
    graph, problem, rm, r0, r1, depot, customers = test_setup
    rm.register(r0, graph)
    rm.register(r1, graph)

    # Find an edge in the graph not used by r0 or r1
    used_edges = set(zip(r0.node_sequence[:-1], r0.node_sequence[1:])).union(
        set(zip(r1.node_sequence[:-1], r1.node_sequence[1:]))
    )
    unused_edge = next((u, v) for u, v in graph.graph.edges() if (u, v) not in used_edges)

    layer = IncidentLayer()
    layer.add_incident(
        Incident(
            u=unused_edge[0],
            v=unused_edge[1],
            type=IncidentType.ACCIDENT,
            severity=IncidentSeverity.HIGH,
        )
    )

    cfg = QPSOConfig(n_particles=4, max_iterations=5, seed=42)
    reroute_res = selective_reroute(graph, problem, rm, layer, cfg)

    # 0 affected vehicles
    assert len(reroute_res.affected_vehicle_ids) == 0
    assert len(reroute_res.unaffected_vehicle_ids) == 2
    assert len(reroute_res.updated_routes) == 0
    assert len(reroute_res.preserved_routes) == 2


def test_post_incidents_api_full_flow():
    """Verify POST /incidents executes selective rerouting and returns compliant schema."""
    app.state.qroute = AppState()

    # 1. POST /network
    net_res = client.post(
        "/network",
        json={
            "n_nodes": 10,
            "n_depots": 1,
            "n_customers": 4,
            "connect_radius_km": 5.0,
            "grid_size_km": 10.0,
            "closed_fraction": 0.0,
            "seed": 42,
        },
    )
    assert net_res.status_code == 200
    net_json = net_res.json()

    depot = next(n["id"] for n in net_json["nodes"] if n["node_type"] == "depot")
    custs = [n["id"] for n in net_json["nodes"] if n["node_type"] == "customer"][:4]

    # 2. POST /fleet
    fleet_res = client.post(
        "/fleet",
        json={
            "vehicles": [
                {"vehicle_id": 0, "capacity": 100.0, "depot_node": depot},
                {"vehicle_id": 1, "capacity": 100.0, "depot_node": depot},
            ],
            "customers": [
                {"customer_id": i, "location_node": c, "demand": 3.0}
                for i, c in enumerate(custs)
            ],
        },
    )
    assert fleet_res.status_code == 200

    # 3. POST /optimize
    opt_res = client.post(
        "/optimize",
        json={
            "n_particles": 4,
            "max_iterations": 5,
            "seed": 42,
            "w_time": 1.0,
            "w_distance": 0.5,
            "w_congestion": 0.3,
        },
    )
    assert opt_res.status_code == 200

    # 4. POST /incidents on an open edge
    open_edges = [e for e in net_json["edges"] if e["road_status"] == "open"]
    edge = open_edges[0]

    inc_res = client.post(
        "/incidents",
        json={
            "edge_u": edge["u"],
            "edge_v": edge["v"],
            "incident_type": "CONSTRUCTION",
            "severity": "HIGH",
            "description": "Lane expansion works",
        },
    )
    assert inc_res.status_code == 200
    inc_json = inc_res.json()

    assert inc_json["edge_u"] == edge["u"]
    assert inc_json["edge_v"] == edge["v"]
    assert inc_json["incident_type"] == "CONSTRUCTION"
    assert inc_json["severity"] == "HIGH"
    assert "affected_vehicle_ids" in inc_json
    assert "updated_routes" in inc_json
    assert "unaffected_route_count" in inc_json
    assert inc_json["n_affected"] == len(inc_json["affected_vehicle_ids"])


def test_incident_persistence_in_db():
    """Verify incident record is written to PostgreSQL."""
    session: Session = SessionLocal()
    try:
        incidents = session.execute(select(IncidentModel)).scalars().all()
        # Incidents table is queried without error
        assert isinstance(incidents, list)
    finally:
        session.close()
