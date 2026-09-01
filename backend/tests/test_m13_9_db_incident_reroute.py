"""
tests/test_m13_9_db_incident_reroute.py – Tests for Milestone 13.9: Database-Backed Live Incident -> Reroute -> Map Update.

Verifies:
1. Incident Persistence: POST /incidents creates an IncidentModel record in the database.
2. Edge Persistence: Road closure incident updates the corresponding EdgeModel.road_status to "closed".
3. Reroute Persistence: Dynamic selective rerouting persists a new OptimizationRunModel and updated RouteModel records.
4. Incident <-> Optimization Association: IncidentModel.optimization_run_id references the post-incident optimization run.
5. Live API State: GET /routes/current and GET /routes/geographic return the updated live operational state from RouteManager.
6. Non-disruptive Incidents: Incidents that do not affect any routes do not create redundant optimization runs.
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.api.state import AppState
from app.db.models import (
    EdgeModel,
    IncidentModel,
    NetworkModel,
    OptimizationRunModel,
    RouteModel,
)
from app.db.session import SessionLocal, get_db
from app.graph import (
    TransportGraph,
    parse_osm_xml,
    osm_to_transport_graph,
)
from app.qpso import QPSOResult
from app.vrp import VRPSolution, VehicleRoute, build_geographic_vrp_problem
from app.routes.manager import RouteManager
from app.routes.model import ActiveRoute


SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteM139Test">
  <node id="101" lat="12.9715987" lon="77.5945627"/>
  <node id="102" lat="12.9750000" lon="77.5980000"/>
  <node id="103" lat="12.9800000" lon="77.6050000"/>
  <node id="104" lat="12.9850000" lon="77.6100000"/>

  <way id="201">
    <nd ref="101"/>
    <nd ref="102"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="MG Road"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="202">
    <nd ref="102"/>
    <nd ref="103"/>
    <tag k="highway" v="secondary"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="203">
    <nd ref="103"/>
    <nd ref="104"/>
    <tag k="highway" v="tertiary"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="204">
    <nd ref="104"/>
    <nd ref="101"/>
    <tag k="highway" v="residential"/>
    <tag k="oneway" v="no"/>
  </way>
</osm>
"""

client = TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Provides a database session for direct model verification and cleanup."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _setup_osm_state(db: Session) -> tuple[str, str]:
    """Helper to set up an active network, initial optimization run, and routes."""
    app.state.qroute = AppState()
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

    vehicles = [
        {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        {"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
        {"customer_id": "C2", "latitude": 12.9800, "longitude": 77.6050, "demand": 6.0},
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

    net_id = str(uuid.uuid4())
    net_model = NetworkModel(
        id=net_id,
        name="M13.9 OSM Network",
        n_nodes=4,
        n_edges=8,
        n_depots=1,
        n_customers=2,
        n_intersections=1,
        seed=42,
        connect_radius_km=3.5,
        grid_size_km=10.0,
        closed_fraction=0.0,
        is_active=True,
    )
    db.add(net_model)

    # Insert edges
    for u, v, data in osm_graph.graph.edges(data=True):
        e = EdgeModel(
            network_id=net_id,
            u=str(u),
            v=str(v),
            distance=float(data.get("distance", 1.0)),
            base_travel_time=float(data.get("base_travel_time", 2.0)),
            congestion_factor=1.0,
            road_status="open",
        )
        db.add(e)
    db.commit()

    # Initial Route
    rm = RouteManager()
    ar = ActiveRoute(
        route_id="V1",
        vehicle_id="V1",
        depot_node="101",
        visit_order=["C1", "C2"],
        node_sequence=["101", "102", "103", "104", "101"],
        total_distance=4.5,
        total_travel_time=6.0,
        estimated_arrival=6.0,
    )
    rm.register(ar, osm_graph)

    # Initial optimization run
    opt_id = str(uuid.uuid4())
    opt_run = OptimizationRunModel(
        id=opt_id,
        network_id=net_id,
        seed=42,
        n_particles=20,
        max_iterations=100,
        w_time=1.0,
        w_distance=0.5,
        w_congestion=0.3,
        best_fitness=12.5,
        is_feasible=True,
        n_iterations_run=30,
        stopped_early=False,
        convergence_history={"0": 20.0, "30": 12.5},
    )
    db.add(opt_run)
    db.flush()

    route_model = RouteModel(
        optimization_run_id=opt_id,
        route_id="V1",
        vehicle_id="V1",
        depot_node="101",
        visit_order=["C1", "C2"],
        node_sequence=["101", "102", "103", "104", "101"],
        total_distance=4.5,
        total_travel_time=6.0,
        estimated_arrival=6.0,
        status="ACTIVE",
    )
    db.add(route_model)
    db.commit()

    # Populate AppState
    app.state.qroute.graph = osm_graph
    app.state.qroute.network_db_id = net_id
    app.state.qroute.problem = problem
    app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=12.5)
    app.state.qroute.opt_run_db_id = opt_id
    app.state.qroute.route_manager = rm
    app.state.qroute.last_qpso_config = {
        "n_particles": 20,
        "max_iterations": 50,
        "seed": 42,
        "w_time": 1.0,
        "w_distance": 0.5,
        "w_congestion": 0.3,
    }

    return net_id, opt_id


class TestDatabaseIncidentRerouteFlow:
    """Test suite verifying end-to-end database persistence for live incidents and selective rerouting."""

    def test_live_incident_reroute_database_persistence_loop(self, db_session: Session):
        """Verify full loop: Incident -> PostgreSQL -> Edge closure -> Reroute -> DB OptRun -> Live APIs."""
        net_id, initial_opt_id = _setup_osm_state(db_session)

        try:
            # 1. Post a Road Closure incident on edge 101 -> 102 (which lies on V1's route)
            resp = client.post(
                "/incidents",
                json={
                    "edge_u": "101",
                    "edge_v": "102",
                    "incident_type": "ROAD_CLOSURE",
                    "severity": "CRITICAL",
                    "description": "Bridge maintenance closure",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_closure"] is True
            assert "V1" in data["affected_vehicle_ids"]
            assert len(data["updated_routes"]) == 1

            # 2. Verify IncidentModel was persisted in PostgreSQL
            inc_record = db_session.execute(
                select(IncidentModel)
                .where(IncidentModel.network_id == net_id, IncidentModel.edge_u == "101", IncidentModel.edge_v == "102")
            ).scalar_one_or_none()
            assert inc_record is not None
            assert inc_record.incident_type == "ROAD_CLOSURE"
            assert inc_record.is_closure is True

            # 3. Verify EdgeModel.road_status was updated to 'closed'
            edge_record = db_session.execute(
                select(EdgeModel)
                .where(EdgeModel.network_id == net_id, EdgeModel.u == "101", EdgeModel.v == "102")
            ).scalar_one_or_none()
            assert edge_record is not None
            assert edge_record.road_status == "closed"

            # 4. Verify that a new post-incident OptimizationRunModel was persisted
            post_opt_id = app.state.qroute.opt_run_db_id
            assert post_opt_id is not None
            assert post_opt_id != initial_opt_id

            post_opt_run = db_session.execute(
                select(OptimizationRunModel).where(OptimizationRunModel.id == post_opt_id)
            ).scalar_one_or_none()
            assert post_opt_run is not None

            # 5. Verify IncidentModel is associated with the post-incident optimization run
            assert inc_record.optimization_run_id == post_opt_id

            # 6. Verify post-incident routes were persisted in RouteModel
            persisted_routes = db_session.execute(
                select(RouteModel).where(RouteModel.optimization_run_id == post_opt_id)
            ).scalars().all()
            assert len(persisted_routes) == 1
            assert persisted_routes[0].vehicle_id == "V1"
            # Route must not traverse closed edge 101 -> 102
            node_seq = persisted_routes[0].node_sequence
            for i in range(len(node_seq) - 1):
                assert not (node_seq[i] == "101" and node_seq[i + 1] == "102")

            # 7. Verify GET /routes/current reflects the updated operational state
            r_curr = client.get("/routes/current")
            assert r_curr.status_code == 200
            curr_data = r_curr.json()
            assert curr_data["total_active"] == 1
            live_seq = curr_data["routes"][0]["node_sequence"]
            assert live_seq == node_seq
            assert curr_data["routes"][0]["status"] == "ACTIVE"

            # 8. Verify GET /routes/geographic returns updated ordered coordinates
            r_geo = client.get("/routes/geographic")
            assert r_geo.status_code == 200
            geo_data = r_geo.json()
            assert geo_data["is_geographic"] is True
            assert len(geo_data["routes"]) == 1
            assert len(geo_data["routes"][0]["coordinates"]) == len(node_seq)

        finally:
            # Cleanup test network and cascade-deleted entities
            net = db_session.execute(select(NetworkModel).where(NetworkModel.id == net_id)).scalar_one_or_none()
            if net:
                db_session.delete(net)
                db_session.commit()

    def test_non_disruptive_incident_does_not_create_redundant_optrun(self, db_session: Session):
        """Verify that an incident on an unused edge persists the incident without fake route creation."""
        net_id, initial_opt_id = _setup_osm_state(db_session)

        try:
            # Edge 102 -> 101 is not used by V1's route (V1 uses 101->102, 102->103, 103->104, 104->101)
            # Or edge 103 -> 102
            resp = client.post(
                "/incidents",
                json={
                    "edge_u": "103",
                    "edge_v": "102",
                    "incident_type": "CONSTRUCTION",
                    "severity": "LOW",
                    "description": "Minor sidewalk repair",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["affected_vehicle_ids"]) == 0

            # IncidentModel is persisted and associated with initial_opt_id
            inc_record = db_session.execute(
                select(IncidentModel)
                .where(IncidentModel.network_id == net_id, IncidentModel.edge_u == "103", IncidentModel.edge_v == "102")
            ).scalar_one_or_none()
            assert inc_record is not None
            assert inc_record.optimization_run_id == initial_opt_id

            # AppState opt_run_db_id remains initial_opt_id
            assert app.state.qroute.opt_run_db_id == initial_opt_id

        finally:
            net = db_session.execute(select(NetworkModel).where(NetworkModel.id == net_id)).scalar_one_or_none()
            if net:
                db_session.delete(net)
                db_session.commit()
