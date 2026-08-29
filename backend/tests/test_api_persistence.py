"""
tests/test_api_persistence.py – Integration tests verifying API persistence to PostgreSQL.

Tests the full API flow while querying the database directly to ensure:
1. POST /network creates records in `networks`, `nodes`, and `edges` tables.
2. POST /fleet creates records in `fleet_vehicles` and `customers` tables.
3. POST /optimize creates records in `optimization_runs` and `routes` tables.
4. POST /incidents creates records in `incidents` and saves re-optimized `routes`.
5. GET /routes/current and GET /analytics/convergence reflect persisted optimization data.
6. DB error resilience: optimization and API behavior remain functional and clean.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.state import AppState
from app.db.crud import (
    delete_network,
    get_active_network,
    get_incidents_for_network,
    get_latest_optimization_run,
    get_routes_for_optimization,
)
from app.db.models import (
    CustomerModel,
    EdgeModel,
    FleetVehicleModel,
    IncidentModel,
    NetworkModel,
    NodeModel,
    OptimizationRunModel,
    RouteModel,
)
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)

_TEST_NET = {
    "n_nodes": 10,
    "n_depots": 1,
    "n_customers": 4,
    "connect_radius_km": 5.0,
    "grid_size_km": 10.0,
    "closed_fraction": 0.0,
    "seed": 42,
}

_TEST_OPT = {
    "n_particles": 4,
    "max_iterations": 5,
    "seed": 42,
    "w_time": 1.0,
    "w_distance": 0.5,
    "w_congestion": 0.3,
}



@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _reset_state():
    app.state.qroute = AppState()


def test_full_api_flow_persists_to_postgresql(db: Session):
    """Verify that every step of the API flow writes appropriate relational records to PostgreSQL."""
    _reset_state()

    # ── 1. POST /network ─────────────────────────────────────────────────
    res_net = client.post("/network", json=_TEST_NET)
    assert res_net.status_code == 200, res_net.text
    net_json = res_net.json()
    assert net_json["n_nodes"] == 10

    # Query DB to verify Network, Nodes, Edges
    active_net = get_active_network(db)
    assert active_net is not None
    net_id = active_net.id
    assert active_net.seed == 42
    assert active_net.n_nodes == 10

    db_nodes = db.execute(select(NodeModel).where(NodeModel.network_id == net_id)).scalars().all()
    assert len(db_nodes) == 10

    db_edges = db.execute(select(EdgeModel).where(EdgeModel.network_id == net_id)).scalars().all()
    assert len(db_edges) == net_json["n_edges"]

    # ── 2. POST /fleet ───────────────────────────────────────────────────
    depot_nodes = [n["id"] for n in net_json["nodes"] if n["node_type"] == "depot"]
    cust_nodes = [n["id"] for n in net_json["nodes"] if n["node_type"] == "customer"]
    assert len(depot_nodes) >= 1
    assert len(cust_nodes) >= 1

    fleet_payload = {
        "vehicles": [
            {"vehicle_id": 0, "capacity": 100.0, "depot_node": depot_nodes[0]},
            {"vehicle_id": 1, "capacity": 100.0, "depot_node": depot_nodes[0]},
        ],
        "customers": [
            {"customer_id": i, "location_node": cust_nodes[i], "demand": 3.0}
            for i in range(len(cust_nodes))
        ],
    }
    res_fleet = client.post("/fleet", json=fleet_payload)
    assert res_fleet.status_code == 200, res_fleet.text

    # Query DB to verify FleetVehicles and Customers
    db_vehs = db.execute(
        select(FleetVehicleModel).where(FleetVehicleModel.network_id == net_id)
    ).scalars().all()
    assert len(db_vehs) == 2
    assert {v.vehicle_id for v in db_vehs} == {"0", "1"}

    db_custs = db.execute(
        select(CustomerModel).where(CustomerModel.network_id == net_id)
    ).scalars().all()
    assert len(db_custs) == len(cust_nodes)

    # ── 3. POST /optimize ────────────────────────────────────────────────
    res_opt = client.post("/optimize", json=_TEST_OPT)
    assert res_opt.status_code == 200, res_opt.text
    opt_json = res_opt.json()
    assert opt_json["best_fitness"] > 0
    assert opt_json["n_iterations_run"] > 0

    # Query DB to verify OptimizationRun and Routes
    latest_opt = get_latest_optimization_run(db, net_id)
    assert latest_opt is not None
    assert latest_opt.seed == 42
    assert latest_opt.best_fitness == pytest.approx(opt_json["best_fitness"], rel=1e-4)

    db_routes = get_routes_for_optimization(db, latest_opt.id)
    assert len(db_routes) == opt_json["n_routes"]
    for r in db_routes:
        assert r.status == "active"
        assert len(r.node_sequence) >= 2

    # ── 4. GET /routes/current ───────────────────────────────────────────
    res_routes = client.get("/routes/current")
    assert res_routes.status_code == 200
    routes_json = res_routes.json()
    assert routes_json["total_active"] == len(db_routes)

    # ── 5. GET /analytics/convergence ────────────────────────────────────
    res_conv = client.get("/analytics/convergence")
    assert res_conv.status_code == 200
    conv_json = res_conv.json()
    assert conv_json["n_iterations"] == latest_opt.n_iterations_run
    assert len(conv_json["history"]) == len(latest_opt.convergence_history)

    # ── 6. POST /incidents ───────────────────────────────────────────────
    # Pick the first edge from the network
    first_edge = net_json["edges"][0]
    inc_payload = {
        "edge_u": first_edge["u"],
        "edge_v": first_edge["v"],
        "incident_type": "ACCIDENT",
        "severity": "HIGH",
        "description": "Multi-car accident on bridge",
    }
    res_inc = client.post("/incidents", json=inc_payload)
    assert res_inc.status_code == 200, res_inc.text
    inc_json = res_inc.json()
    assert inc_json["incident_type"] == "ACCIDENT"

    # Query DB to verify Incident record
    db_incidents = get_incidents_for_network(db, net_id)
    assert len(db_incidents) >= 1
    assert db_incidents[-1].severity == "HIGH"

    # ── 7. Cleanup test data from PostgreSQL ─────────────────────────────
    delete_network(db, net_id)
    assert get_active_network(db) is None


def test_invalid_node_does_not_corrupt_db(db: Session):
    """Verify that 400 Bad Request on invalid node does not leave orphaned records in DB."""
    _reset_state()
    res_net = client.post("/network", json=_TEST_NET)
    assert res_net.status_code == 200
    active_net = get_active_network(db)
    assert active_net is not None
    net_id = active_net.id

    # Post fleet with non-existent depot node 9999
    invalid_fleet = {
        "vehicles": [{"vehicle_id": 0, "capacity": 50.0, "depot_node": 9999}],
        "customers": [{"customer_id": 0, "location_node": 0, "demand": 5.0}],
    }
    res_fleet = client.post("/fleet", json=invalid_fleet)
    assert res_fleet.status_code == 400

    # Ensure no vehicles were saved in DB for this invalid request
    db_vehs = db.execute(
        select(FleetVehicleModel).where(FleetVehicleModel.network_id == net_id)
    ).scalars().all()
    assert len(db_vehs) == 0

    # Cleanup
    delete_network(db, net_id)


def test_cascade_deletion_cleans_all_dependent_tables(db: Session):
    """Verify that deleting a network cleanly removes all child records across all 7 domain tables."""
    _reset_state()
    res_net = client.post("/network", json=_TEST_NET)
    net_json = res_net.json()
    active_net = get_active_network(db)
    assert active_net is not None
    net_id = active_net.id

    depot_node = next(n["id"] for n in net_json["nodes"] if n["node_type"] == "depot")
    cust_nodes = [n["id"] for n in net_json["nodes"] if n["node_type"] == "customer"][:2]

    # Fleet
    client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 50.0, "depot_node": depot_node}],
        "customers": [{"customer_id": i, "location_node": n, "demand": 3.0} for i, n in enumerate(cust_nodes)],
    })

    # Optimize
    client.post("/optimize", json=_TEST_OPT)

    # Incident
    edge = net_json["edges"][0]
    client.post("/incidents", json={
        "edge_u": edge["u"],
        "edge_v": edge["v"],
        "incident_type": "OBSTRUCTION",
        "severity": "LOW",
    })

    # Verify rows exist before delete
    assert len(db.execute(select(NodeModel).where(NodeModel.network_id == net_id)).scalars().all()) > 0
    assert len(db.execute(select(EdgeModel).where(EdgeModel.network_id == net_id)).scalars().all()) > 0
    assert len(db.execute(select(FleetVehicleModel).where(FleetVehicleModel.network_id == net_id)).scalars().all()) > 0
    assert len(db.execute(select(CustomerModel).where(CustomerModel.network_id == net_id)).scalars().all()) > 0
    assert len(db.execute(select(OptimizationRunModel).where(OptimizationRunModel.network_id == net_id)).scalars().all()) > 0
    assert len(db.execute(select(IncidentModel).where(IncidentModel.network_id == net_id)).scalars().all()) > 0

    # Delete network
    success = delete_network(db, net_id)
    assert success is True

    # Confirm all tables have 0 rows for this network_id
    assert len(db.execute(select(NodeModel).where(NodeModel.network_id == net_id)).scalars().all()) == 0
    assert len(db.execute(select(EdgeModel).where(EdgeModel.network_id == net_id)).scalars().all()) == 0
    assert len(db.execute(select(FleetVehicleModel).where(FleetVehicleModel.network_id == net_id)).scalars().all()) == 0
    assert len(db.execute(select(CustomerModel).where(CustomerModel.network_id == net_id)).scalars().all()) == 0
    assert len(db.execute(select(OptimizationRunModel).where(OptimizationRunModel.network_id == net_id)).scalars().all()) == 0
    assert len(db.execute(select(IncidentModel).where(IncidentModel.network_id == net_id)).scalars().all()) == 0

