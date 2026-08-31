"""
tests/test_m13_6_map_visualization.py – Test suite for OSM Map Visualization & Geographic VRP Display (Milestone 13.6).

Verifies:
1. test_route_out_geometry_populated_for_geographic_graph: RouteOut.geometry contains [[lat, lon], ...] for OSM networks.
2. test_route_out_geometry_none_for_synthetic_graph: RouteOut.geometry is None for synthetic Cartesian networks.
3. test_get_routes_geographic_success: GET /routes/geographic returns structured geographic visualization model.
4. test_get_routes_geographic_before_optimization: Guard returns 409 when called before optimization.
5. test_get_routes_geographic_synthetic_fallback: GET /routes/geographic handles synthetic networks gracefully (is_geographic=False).
6. test_node_out_lat_lon_preservation: NodeOut retains explicit lat and lon fields.
7. test_coordinate_ordering_lat_lon: Verified that coordinates are strictly [latitude, longitude].
8. test_multi_vehicle_geographic_routes: Multi-vehicle geographic trajectories are independently generated.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.state import AppState
from app.graph import osm_to_transport_graph
from app.main import app
from app.qpso.optimizer import QPSOResult
from app.routes.manager import RouteManager
from app.routes.model import ActiveRoute
from app.vrp import Customer, Vehicle, VRPProblem, VRPSolution, build_geographic_vrp_problem



SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteM136Test">
  <node id="101" lat="12.9715987" lon="77.5945627">
    <tag k="name" v="MG Road Depot"/>
  </node>
  <node id="102" lat="12.9750000" lon="77.5980000">
    <tag k="name" v="Brigade Road Stop"/>
  </node>
  <node id="103" lat="12.9800000" lon="77.6050000">
    <tag k="name" v="Commercial Street Stop"/>
  </node>
  <way id="201">
    <nd ref="101"/>
    <nd ref="102"/>
    <tag k="highway" v="primary"/>
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
    <nd ref="101"/>
    <tag k="highway" v="primary"/>
    <tag k="oneway" v="no"/>
  </way>
</osm>
"""


client = TestClient(app)


def _reset_state() -> None:
    app.state.qroute = AppState()


def test_get_routes_geographic_before_optimization():
    """1. Verify that GET /routes/geographic returns 409 before optimization."""
    _reset_state()
    r = client.get("/routes/geographic")
    assert r.status_code == 409


def test_get_routes_geographic_success():
    """2. Verify that GET /routes/geographic returns structured geographic data for OSM networks."""
    _reset_state()
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

    vehicles = [
        {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        {"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
        {"customer_id": "C2", "latitude": 12.9800, "longitude": 77.6050, "demand": 6.0},
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

    # Set state
    app.state.qroute.graph = osm_graph
    app.state.qroute.problem = problem
    app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=1.0)

    rm = RouteManager()
    ar = ActiveRoute(
        route_id="V1",
        vehicle_id="V1",
        depot_node="101",
        visit_order=["C1", "C2"],
        node_sequence=["101", "102", "103", "101"],
        total_distance=2.5,
        total_travel_time=3.5,
    )
    rm.register(ar, osm_graph)
    app.state.qroute.route_manager = rm


    # Query GET /routes/geographic
    r = client.get("/routes/geographic")
    assert r.status_code == 200
    data = r.json()

    assert data["is_geographic"] is True
    assert data["center"] is not None
    assert len(data["center"]) == 2
    assert 12.0 <= data["center"][0] <= 13.5
    assert 77.0 <= data["center"][1] <= 78.0

    # Depots
    assert len(data["depots"]) == 1
    assert data["depots"][0]["id"] == "101"
    assert pytest.approx(data["depots"][0]["latitude"], rel=1e-4) == 12.9715987
    assert pytest.approx(data["depots"][0]["longitude"], rel=1e-4) == 77.5945627

    # Customers
    assert len(data["customers"]) == 2
    c_ids = [c["id"] for c in data["customers"]]
    assert "C1" in c_ids and "C2" in c_ids

    # Routes
    assert len(data["routes"]) == 1
    route = data["routes"][0]
    assert route["vehicle_id"] == "V1"
    assert len(route["coordinates"]) == 4
    # Check [lat, lon] sequence: 101 -> 102 -> 103 -> 101
    assert pytest.approx(route["coordinates"][0][0], rel=1e-4) == 12.9715987
    assert pytest.approx(route["coordinates"][1][0], rel=1e-4) == 12.9750000
    assert pytest.approx(route["coordinates"][2][0], rel=1e-4) == 12.9800000
    assert pytest.approx(route["coordinates"][3][0], rel=1e-4) == 12.9715987


def test_route_out_geometry_populated_for_geographic_graph():
    """3. Verify that RouteOut in GET /routes/current contains geometry for geographic graphs."""
    _reset_state()
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

    vehicles = [
        {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        {"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

    app.state.qroute.graph = osm_graph
    app.state.qroute.problem = problem
    app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=1.0)

    rm = RouteManager()
    ar = ActiveRoute(
        route_id="V1",
        vehicle_id="V1",
        depot_node="101",
        visit_order=["C1"],
        node_sequence=["101", "102", "101"],
        total_distance=1.5,
        total_travel_time=2.0,
    )
    rm.register(ar, osm_graph)
    app.state.qroute.route_manager = rm

    r = client.get("/routes/current")
    assert r.status_code == 200
    data = r.json()
    assert len(data["routes"]) == 1
    route = data["routes"][0]
    assert route["geometry"] is not None
    assert len(route["geometry"]) == 3
    assert pytest.approx(route["geometry"][0][0], rel=1e-4) == 12.9715987


def test_route_out_geometry_none_for_synthetic_graph():
    """4. Verify that RouteOut.geometry is None for synthetic Cartesian networks."""
    _reset_state()
    # Create standard synthetic network via API
    r_net = client.post("/network", json={
        "n_nodes": 10, "n_depots": 1, "n_customers": 4,
        "connect_radius_km": 5.0, "grid_size_km": 10.0,
        "closed_fraction": 0.0, "seed": 42,
    })
    assert r_net.status_code == 200
    net = r_net.json()

    depot_node = next(n["id"] for n in net["nodes"] if n["node_type"] == "depot")
    customer_nodes = [n["id"] for n in net["nodes"] if n["node_type"] == "customer"][:2]

    client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 50.0, "depot_node": depot_node}],
        "customers": [{"customer_id": i, "location_node": n, "demand": 5.0} for i, n in enumerate(customer_nodes)],
    })

    r_opt = client.post("/optimize", json={
        "n_particles": 4, "max_iterations": 5, "seed": 42,
        "w_time": 1.0, "w_distance": 0.5, "w_congestion": 0.3,
    })
    assert r_opt.status_code == 200

    r_curr = client.get("/routes/current")
    assert r_curr.status_code == 200
    data = r_curr.json()
    for route in data["routes"]:
        assert route["geometry"] is None


def test_get_routes_geographic_synthetic_fallback():
    """5. Verify that GET /routes/geographic returns is_geographic=False for synthetic networks."""
    _reset_state()
    r_net = client.post("/network", json={
        "n_nodes": 10, "n_depots": 1, "n_customers": 4,
        "connect_radius_km": 5.0, "grid_size_km": 10.0,
        "closed_fraction": 0.0, "seed": 42,
    })
    assert r_net.status_code == 200
    net = r_net.json()

    depot_node = next(n["id"] for n in net["nodes"] if n["node_type"] == "depot")
    customer_nodes = [n["id"] for n in net["nodes"] if n["node_type"] == "customer"][:2]

    client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 50.0, "depot_node": depot_node}],
        "customers": [{"customer_id": i, "location_node": n, "demand": 5.0} for i, n in enumerate(customer_nodes)],
    })
    client.post("/optimize", json={"n_particles": 4, "max_iterations": 5, "seed": 42})

    r_geo = client.get("/routes/geographic")
    assert r_geo.status_code == 200
    data = r_geo.json()
    assert data["is_geographic"] is False
    assert data["center"] is None


def test_node_out_lat_lon_preservation():
    """6. Verify that NodeOut includes lat and lon when available."""
    _reset_state()
    r = client.post("/network", json={
        "n_nodes": 6, "n_depots": 1, "n_customers": 2,
        "connect_radius_km": 5.0, "grid_size_km": 10.0,
        "closed_fraction": 0.0, "seed": 42,
    })
    assert r.status_code == 200
    data = r.json()
    for n in data["nodes"]:
        assert "lat" in n
        assert "lon" in n


def test_coordinate_ordering_lat_lon():
    """7. Verify strict [latitude, longitude] ordering."""
    _reset_state()
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)
    vehicles = [{"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627}]
    customers = [("C1", 12.9750, 77.5980, 5.0)]
    problem = build_geographic_vrp_problem(osm_graph, vehicles, customers)
    app.state.qroute.graph = osm_graph
    app.state.qroute.problem = problem
    app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=1.0)

    rm = RouteManager()
    ar = ActiveRoute(
        route_id="V1", vehicle_id="V1", depot_node="101",
        visit_order=["C1"], node_sequence=["101", "102", "101"],
        total_distance=1.0, total_travel_time=1.0,
    )
    rm.register(ar, osm_graph)
    app.state.qroute.route_manager = rm

    r = client.get("/routes/geographic")
    assert r.status_code == 200
    data = r.json()
    for route in data["routes"]:
        for coord in route["coordinates"]:
            lat, lon = coord
            assert -90.0 <= lat <= 90.0
            assert -180.0 <= lon <= 180.0
            # Lat is ~12.9, lon is ~77.5 for Bangalore OSM fixture
            assert 12.0 <= lat <= 13.5
            assert 77.0 <= lon <= 78.0


def test_multi_vehicle_geographic_routes():
    """8. Verify multi-vehicle geographic routes render independent coordinate trajectories."""
    _reset_state()
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)
    vehicles = [
        {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
        {"vehicle_id": "V2", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        ("C1", 12.9750, 77.5980, 5.0),
        ("C2", 12.9800, 77.6050, 6.0),
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles, customers)
    app.state.qroute.graph = osm_graph
    app.state.qroute.problem = problem
    app.state.qroute.qpso_result = QPSOResult(best_solution=VRPSolution(), best_fitness=1.0)

    rm = RouteManager()
    ar1 = ActiveRoute(
        route_id="V1", vehicle_id="V1", depot_node="101",
        visit_order=["C1"], node_sequence=["101", "102", "101"],
        total_distance=1.0, total_travel_time=1.0,
    )
    ar2 = ActiveRoute(
        route_id="V2", vehicle_id="V2", depot_node="101",
        visit_order=["C2"], node_sequence=["101", "103", "101"],
        total_distance=1.5, total_travel_time=1.5,
    )
    rm.register(ar1, osm_graph)
    rm.register(ar2, osm_graph)
    app.state.qroute.route_manager = rm


    r = client.get("/routes/geographic")
    assert r.status_code == 200
    data = r.json()
    assert len(data["routes"]) == 2
    r1 = next(rt for rt in data["routes"] if rt["vehicle_id"] == "V1")
    r2 = next(rt for rt in data["routes"] if rt["vehicle_id"] == "V2")
    assert r1["coordinates"] != r2["coordinates"]
