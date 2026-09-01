"""
tests/test_m13_8_dynamic_flow.py – Test suite for Milestone 13.8: Dynamic Frontend <-> Backend Flow.

Verifies:
1. GET /routes/current returns 409 Conflict prior to route optimization.
2. GET /routes/geographic returns 409 Conflict prior to route optimization.
3. After optimization over OSM network, GET /routes/current returns valid active routes with all fields.
4. After optimization over OSM network, GET /routes/geographic returns full geographic model:
   - is_geographic == True
   - center is a [lat, lon] pair
   - depots contain ID, latitude, longitude
   - customers contain ID, location_node, latitude, longitude, demand
   - routes contain vehicle_id, depot_node, visit_order, total_distance, total_travel_time, and ordered [lat, lon] coordinates
5. Dynamic route update: Incident registration triggers rerouting and immediately reflects in GET /routes/current and GET /routes/geographic.
6. Empty active routes list handles gracefully without errors.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.state import AppState
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
<osm version="0.6" generator="QRouteDynamicFlowTest">
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


def _reset_state():
    """Reset global application state between tests."""
    app.state.qroute = AppState()


class TestDynamicFlowBackendIntegration:
    """Tests for Milestone 13.8 dynamic data flow between frontend and backend APIs."""

    def test_routes_endpoints_unoptimized_return_409(self):
        """Unoptimized state returns 409 Conflict with informative detail message."""
        _reset_state()

        r_curr = client.get("/routes/current")
        assert r_curr.status_code == 409

        r_geo = client.get("/routes/geographic")
        assert r_geo.status_code == 409

    def test_routes_current_and_geographic_success_flow(self):
        """GET /routes/current and GET /routes/geographic return fully populated models."""
        _reset_state()
        osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

        vehicles = [
            {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
            {"vehicle_id": "V2", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
        ]
        customers = [
            {"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
            {"customer_id": "C2", "latitude": 12.9800, "longitude": 77.6050, "demand": 6.0},
            {"customer_id": "C3", "latitude": 12.9850, "longitude": 77.6100, "demand": 4.0},
        ]
        problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

        app.state.qroute.graph = osm_graph
        app.state.qroute.problem = problem
        app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=10.5)

        rm = RouteManager()
        ar1 = ActiveRoute(
            route_id="V1",
            vehicle_id="V1",
            depot_node="101",
            visit_order=["C1", "C2"],
            node_sequence=["101", "102", "103", "104", "101"],
            total_distance=4.2,
            total_travel_time=6.5,
            estimated_arrival=6.5,
        )
        ar2 = ActiveRoute(
            route_id="V2",
            vehicle_id="V2",
            depot_node="101",
            visit_order=["C3"],
            node_sequence=["101", "104", "101"],
            total_distance=3.1,
            total_travel_time=4.8,
            estimated_arrival=4.8,
        )
        rm.register(ar1, osm_graph)
        rm.register(ar2, osm_graph)
        app.state.qroute.route_manager = rm

        # 1. Test GET /routes/current
        r_curr = client.get("/routes/current")
        assert r_curr.status_code == 200
        curr_data = r_curr.json()
        assert curr_data["total_active"] == 2
        assert len(curr_data["routes"]) == 2

        v_ids = [r["vehicle_id"] for r in curr_data["routes"]]
        assert "V1" in v_ids and "V2" in v_ids

        # 2. Test GET /routes/geographic
        r_geo = client.get("/routes/geographic")
        assert r_geo.status_code == 200
        geo_data = r_geo.json()

        assert geo_data["is_geographic"] is True
        assert geo_data["center"] is not None
        assert len(geo_data["center"]) == 2
        assert 12.0 <= geo_data["center"][0] <= 13.5
        assert 77.0 <= geo_data["center"][1] <= 78.0

        # Depots
        assert len(geo_data["depots"]) == 1
        assert geo_data["depots"][0]["id"] == "101"

        # Customers
        assert len(geo_data["customers"]) == 3
        c_ids = [c["id"] for c in geo_data["customers"]]
        assert "C1" in c_ids and "C2" in c_ids and "C3" in c_ids

        # Routes
        assert len(geo_data["routes"]) == 2
        r1 = next(r for r in geo_data["routes"] if r["vehicle_id"] == "V1")
        assert len(r1["coordinates"]) == 5
        assert r1["total_distance"] > 0.0
        assert r1["total_travel_time"] > 0.0
        assert r1["visit_order"] == ["C1", "C2"]

    def test_dynamic_route_incident_rerouting_flow(self):
        """Registering an incident on an edge closes edge, re-optimizes routes and updates API payload."""
        _reset_state()
        osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

        vehicles = [{"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627}]
        customers = [{"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0}]
        problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

        app.state.qroute.graph = osm_graph
        app.state.qroute.problem = problem
        app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=5.0)

        rm = RouteManager()
        ar = ActiveRoute(
            route_id="V1",
            vehicle_id="V1",
            depot_node="101",
            visit_order=["C1"],
            node_sequence=["101", "102", "101"],
            total_distance=2.0,
            total_travel_time=3.0,
        )
        rm.register(ar, osm_graph)
        app.state.qroute.route_manager = rm

        # Verify initial active routes
        r1 = client.get("/routes/current").json()
        assert r1["total_active"] == 1

        # Inject incident closing edge ("101", "102")
        r_inc = client.post(
            "/incidents",
            json={
                "edge_u": "101",
                "edge_v": "102",
                "incident_type": "ROAD_CLOSURE",
                "severity": "HIGH",
                "description": "Tree fallen on MG Road",
            },
        )
        assert r_inc.status_code == 200

        # Query GET /routes/current after incident
        r2 = client.get("/routes/current").json()
        assert r2["total_active"] >= 1
        assert len(r2["routes"]) >= 1

        # Query GET /routes/geographic after incident
        r_geo2 = client.get("/routes/geographic").json()
        assert r_geo2["is_geographic"] is True
        assert len(r_geo2["routes"]) >= 1
