"""
tests/test_m13_10_e2e_demo.py – End-to-End Real-World Demonstration Test for Milestone 13.10.

Verifies the complete real-world pipeline from clean startup:
1. Real-World OSM Network Loading (POST /network/osm-preset) -> persists NetworkModel, NodeModel, EdgeModel.
2. Geographic Fleet & Customer Setup (POST /fleet/geographic-preset) -> snaps GPS coords, persists FleetVehicleModel, CustomerModel.
3. Multi-Vehicle QPSO Optimization (POST /optimize) -> computes routes, persists OptimizationRunModel, RouteModel.
4. Live Route & Map Geometry Retrieval (GET /routes/current & GET /routes/geographic) -> verifies ordered lat/lon polylines.
5. Live Road Closure Incident (POST /incidents) -> updates EdgeModel to closed, triggers selective dynamic rerouting, persists post-incident OptimizationRunModel & IncidentModel.
6. Post-Incident Route Verification (GET /routes/current & GET /routes/geographic) -> verifies routes avoid closed edge.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.api.state import AppState
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

client = TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Provides a database session for direct model verification and cleanup."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestEndToEndRealWorldDemo:
    """Complete end-to-end real-world pipeline test suite for Milestone 13.10."""

    def test_complete_real_world_e2e_demo_lifecycle(self, db_session: Session):
        """Execute and verify the full real-world lifecycle from a clean application state."""
        # Ensure fresh AppState
        app.state.qroute = AppState()

        net_id = None
        try:
            # ── 1. Load Real-World OSM Network ──────────────────────────────
            r_net = client.post("/network/osm-preset", json={"preset_name": "bangalore_urban"})
            assert r_net.status_code == 200, f"Failed network creation: {r_net.text}"
            net_data = r_net.json()
            assert net_data["n_nodes"] >= 9
            assert net_data["n_edges"] >= 18
            assert len(net_data["nodes"]) == net_data["n_nodes"]
            # Verify nodes have real lat/lon
            assert any(n["lat"] is not None and n["lon"] is not None for n in net_data["nodes"])

            net_id = app.state.qroute.network_db_id
            assert net_id is not None

            # Verify PostgreSQL Network, Nodes, and Edges
            net_model = db_session.execute(
                select(NetworkModel).where(NetworkModel.id == net_id)
            ).scalar_one_or_none()
            assert net_model is not None
            assert net_model.is_active is True

            db_nodes = db_session.execute(
                select(NodeModel).where(NodeModel.network_id == net_id)
            ).scalars().all()
            assert len(db_nodes) == net_data["n_nodes"]

            db_edges = db_session.execute(
                select(EdgeModel).where(EdgeModel.network_id == net_id)
            ).scalars().all()
            assert len(db_edges) == net_data["n_edges"]

            # ── 2. Configure Geographic Fleet & Customers ───────────────────
            r_fleet = client.post("/fleet/geographic-preset")
            assert r_fleet.status_code == 200, f"Failed fleet config: {r_fleet.text}"
            fleet_data = r_fleet.json()
            assert fleet_data["n_vehicles"] == 2
            assert fleet_data["n_customers"] == 6

            # Verify PostgreSQL Fleet Vehicles and Customers
            db_vehs = db_session.execute(
                select(FleetVehicleModel).where(FleetVehicleModel.network_id == net_id)
            ).scalars().all()
            assert len(db_vehs) == 2

            db_custs = db_session.execute(
                select(CustomerModel).where(CustomerModel.network_id == net_id)
            ).scalars().all()
            assert len(db_custs) == 6

            # ── 3. Run QPSO Multi-Vehicle Optimization ─────────────────────
            r_opt = client.post(
                "/optimize",
                json={
                    "n_particles": 20,
                    "max_iterations": 60,
                    "seed": 42,
                    "w_time": 1.0,
                    "w_distance": 0.5,
                    "w_congestion": 0.3,
                },
            )
            assert r_opt.status_code == 200, f"Optimization failed: {r_opt.text}"
            opt_data = r_opt.json()
            assert opt_data["is_feasible"] is True
            assert opt_data["n_routes"] > 0
            assert len(opt_data["routes"]) == opt_data["n_routes"]

            initial_opt_id = app.state.qroute.opt_run_db_id
            assert initial_opt_id is not None

            # Verify PostgreSQL OptimizationRunModel & RouteModel records
            opt_run_db = db_session.execute(
                select(OptimizationRunModel).where(OptimizationRunModel.id == initial_opt_id)
            ).scalar_one_or_none()
            assert opt_run_db is not None
            assert opt_run_db.best_fitness == pytest.approx(opt_data["best_fitness"], rel=1e-3)

            db_routes = db_session.execute(
                select(RouteModel).where(RouteModel.optimization_run_id == initial_opt_id)
            ).scalars().all()
            assert len(db_routes) == opt_data["n_routes"]

            # ── 4. Retrieve Current & Geographic Routes ────────────────────
            r_curr = client.get("/routes/current")
            assert r_curr.status_code == 200
            curr_data = r_curr.json()
            assert curr_data["total_active"] == opt_data["n_routes"]
            for r in curr_data["routes"]:
                assert r["status"] == "ACTIVE"
                assert len(r["node_sequence"]) >= 3
                assert r["total_distance"] > 0
                assert r["total_travel_time"] > 0

            r_geo = client.get("/routes/geographic")
            assert r_geo.status_code == 200
            geo_data = r_geo.json()
            assert geo_data["is_geographic"] is True
            assert len(geo_data["center"]) == 2
            assert len(geo_data["depots"]) >= 1
            assert len(geo_data["customers"]) >= 1
            assert len(geo_data["routes"]) == opt_data["n_routes"]
            for gr in geo_data["routes"]:
                assert len(gr["coordinates"]) > 0
                for pt in gr["coordinates"]:
                    assert len(pt) == 2
                    # Valid Bangalore lat/lon
                    assert 12.9 <= pt[0] <= 13.1
                    assert 77.5 <= pt[1] <= 77.7

            # ── 5. Register Road Closure Incident & Dynamic Rerouting ───────
            # Find an active edge from the first route to simulate closure
            route_0 = curr_data["routes"][0]
            seq = route_0["node_sequence"]
            u_closed = str(seq[0])
            v_closed = str(seq[1])

            r_inc = client.post(
                "/incidents",
                json={
                    "edge_u": u_closed,
                    "edge_v": v_closed,
                    "incident_type": "ROAD_CLOSURE",
                    "severity": "CRITICAL",
                    "description": "Emergency pipeline repair closure",
                },
            )
            assert r_inc.status_code == 200, f"Incident failed: {r_inc.text}"
            inc_data = r_inc.json()
            assert inc_data["is_closure"] is True
            assert inc_data["n_affected"] >= 1
            assert route_0["vehicle_id"] in inc_data["affected_vehicle_ids"]

            # Refresh db session to observe committed changes from API request
            db_session.expire_all()

            # Verify EdgeModel was updated to "closed"
            edge_closed_db = db_session.execute(
                select(EdgeModel).where(
                    EdgeModel.network_id == net_id,
                    EdgeModel.u == u_closed,
                    EdgeModel.v == v_closed,
                )
            ).scalar_one_or_none()
            assert edge_closed_db is not None
            assert edge_closed_db.road_status == "closed"

            # Verify IncidentModel was persisted
            post_opt_id = app.state.qroute.opt_run_db_id
            assert post_opt_id != initial_opt_id

            inc_db = db_session.execute(
                select(IncidentModel).where(
                    IncidentModel.network_id == net_id,
                    IncidentModel.edge_u == u_closed,
                    IncidentModel.edge_v == v_closed,
                )
            ).scalar_one_or_none()
            assert inc_db is not None
            assert inc_db.is_closure is True
            assert inc_db.optimization_run_id == post_opt_id

            # Verify post-incident RouteModel records in PostgreSQL
            post_routes_db = db_session.execute(
                select(RouteModel).where(RouteModel.optimization_run_id == post_opt_id)
            ).scalars().all()
            assert len(post_routes_db) > 0

            # ── 6. Verify Updated Live API State ────────────────────────────
            r_curr_post = client.get("/routes/current")
            assert r_curr_post.status_code == 200
            curr_post = r_curr_post.json()
            # Rerouted vehicle must not use the closed edge
            rerouted_route = next(
                (r for r in curr_post["routes"] if r["vehicle_id"] == route_0["vehicle_id"]),
                None,
            )
            assert rerouted_route is not None
            r_seq = rerouted_route["node_sequence"]
            for i in range(len(r_seq) - 1):
                assert not (str(r_seq[i]) == u_closed and str(r_seq[i + 1]) == v_closed), (
                    f"Rerouted route still traverses closed edge {u_closed} -> {v_closed}"
                )

            r_geo_post = client.get("/routes/geographic")
            assert r_geo_post.status_code == 200
            geo_post = r_geo_post.json()
            assert geo_post["is_geographic"] is True
            assert len(geo_post["routes"]) == len(curr_post["routes"])

        finally:
            # Clean up test database records
            if net_id:
                net = db_session.execute(select(NetworkModel).where(NetworkModel.id == net_id)).scalar_one_or_none()
                if net:
                    db_session.delete(net)
                    db_session.commit()
