"""
tests/test_api.py – Integration tests for the Q-Route REST API (Milestone 9).

Tests use ``fastapi.testclient.TestClient`` to execute requests against the
FastAPI application. State isolation is maintained per test or test flow.

Required Coverage:
 1. POST /network success
 2. POST /fleet success
 3. POST /optimize success
 4. GET /routes/current success
 5. POST /incidents success
 6. Affected-route detection
 7. Unaffected-route preservation
 8. GET /analytics/convergence
 9. Invalid input returns 4xx (422)
10. Unknown node/edge validation returns 400
11. Optimize/fleet/routes/incidents/analytics before required state exists (409)
12. Complete flow:
    network -> fleet -> optimize -> routes/current -> incidents -> routes/current -> analytics/convergence
"""

from __future__ import annotations

import math
import pytest
from fastapi.testclient import TestClient

from app.api.state import AppState
from app.main import app

client = TestClient(app)

# Small, fast network parameters used across all tests
_NET = {
    "n_nodes": 10,
    "n_depots": 1,
    "n_customers": 4,
    "connect_radius_km": 5.0,
    "grid_size_km": 10.0,
    "closed_fraction": 0.0,  # no closed edges so any route is feasible
    "seed": 42,
}

# Fast QPSO parameters
_OPT = {
    "n_particles": 4,
    "max_iterations": 5,
    "seed": 42,
    "w_time": 1.0,
    "w_distance": 0.5,
    "w_congestion": 0.3,
}


def _reset_state() -> None:
    """Reset application state to clean uninitialized state."""
    app.state.qroute = AppState()


def _do_network() -> dict:
    """Create a network and return the response JSON."""
    r = client.post("/network", json=_NET)
    assert r.status_code == 200, r.text
    return r.json()


def _get_depot_and_customers(net: dict) -> tuple[int, list[int]]:
    """Extract depot node and up to 4 customer nodes from a network response."""
    depot_node = next(n["id"] for n in net["nodes"] if n["node_type"] == "depot")
    customer_nodes = [
        n["id"] for n in net["nodes"] if n["node_type"] == "customer"
    ][:4]
    return depot_node, customer_nodes


def _do_fleet(depot_node: int, customer_nodes: list[int]) -> dict:
    """Configure a fleet and return the response JSON."""
    fleet_body = {
        "vehicles": [
            {"vehicle_id": 0, "capacity": 50.0, "depot_node": depot_node},
            {"vehicle_id": 1, "capacity": 50.0, "depot_node": depot_node},
        ],
        "customers": [
            {"customer_id": i, "location_node": n, "demand": 5.0}
            for i, n in enumerate(customer_nodes)
        ],
    }
    r = client.post("/fleet", json=fleet_body)
    assert r.status_code == 200, r.text
    return r.json()


def _do_optimize() -> dict:
    """Run optimization and return the response JSON."""
    r = client.post("/optimize", json=_OPT)
    assert r.status_code == 200, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Health check
# ═══════════════════════════════════════════════════════════════════════════

def test_health_check_unchanged() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


# ═══════════════════════════════════════════════════════════════════════════
# 2. POST /network – success
# ═══════════════════════════════════════════════════════════════════════════

def test_post_network_success() -> None:
    _reset_state()
    r = client.post("/network", json=_NET)
    assert r.status_code == 200
    data = r.json()
    assert data["n_nodes"] == 10
    assert data["n_depots"] == 1
    assert data["n_edges"] > 0
    assert len(data["nodes"]) == 10
    assert len(data["edges"]) == data["n_edges"]
    edge = data["edges"][0]
    assert "u" in edge and "v" in edge
    assert "distance" in edge
    assert "base_travel_time" in edge
    assert "road_status" in edge


# ═══════════════════════════════════════════════════════════════════════════
# 3. Invalid inputs return 422
# ═══════════════════════════════════════════════════════════════════════════

def test_post_network_invalid_n_nodes() -> None:
    r = client.post("/network", json={**_NET, "n_nodes": 2})  # < 4
    assert r.status_code == 422


def test_post_network_invalid_closed_fraction() -> None:
    r = client.post("/network", json={**_NET, "closed_fraction": 1.5})  # > 1
    assert r.status_code == 422


def test_post_fleet_invalid_capacity() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    r = client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": -5.0, "depot_node": depot_node}],
        "customers": [{"customer_id": 0, "location_node": customer_nodes[0], "demand": 1.0}],
    })
    assert r.status_code == 422


def test_post_fleet_invalid_demand() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    r = client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 10.0, "depot_node": depot_node}],
        "customers": [{"customer_id": 0, "location_node": customer_nodes[0], "demand": -1.0}],
    })
    assert r.status_code == 422


def test_post_optimize_invalid_particles() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    r = client.post("/optimize", json={**_OPT, "n_particles": 1})  # < 2
    assert r.status_code == 422


def test_post_incident_invalid_type() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()
    r = client.post("/incidents", json={
        "edge_u": 0, "edge_v": 1,
        "incident_type": "EARTHQUAKE",  # not a valid type
        "severity": "LOW",
    })
    assert r.status_code == 422


def test_post_incident_invalid_severity() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()
    r = client.post("/incidents", json={
        "edge_u": 0, "edge_v": 1,
        "incident_type": "ACCIDENT",
        "severity": "EXTREME",  # not a valid severity
    })
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 4. Unknown node / edge validation returns 400
# ═══════════════════════════════════════════════════════════════════════════

def test_post_fleet_unknown_depot_node() -> None:
    _do_network()
    r = client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 10.0, "depot_node": 99999}],
        "customers": [{"customer_id": 0, "location_node": 1, "demand": 1.0}],
    })
    assert r.status_code == 400
    assert "depot_node" in r.json()["detail"].lower() or "99999" in r.json()["detail"]


def test_post_fleet_unknown_customer_node() -> None:
    net = _do_network()
    depot_node, _ = _get_depot_and_customers(net)
    r = client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 10.0, "depot_node": depot_node}],
        "customers": [{"customer_id": 0, "location_node": 99999, "demand": 1.0}],
    })
    assert r.status_code == 400
    assert "location_node" in r.json()["detail"].lower() or "99999" in r.json()["detail"]


def test_post_incident_unknown_edge() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()
    r = client.post("/incidents", json={
        "edge_u": 99998, "edge_v": 99999,
        "incident_type": "ACCIDENT", "severity": "LOW",
    })
    assert r.status_code == 400
    assert "edge" in r.json()["detail"].lower() or "99998" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Dependency guards / call order errors return 409
# ═══════════════════════════════════════════════════════════════════════════

def test_post_fleet_before_network() -> None:
    _reset_state()
    r = client.post("/fleet", json={
        "vehicles": [{"vehicle_id": 0, "capacity": 10.0, "depot_node": 0}],
        "customers": [{"customer_id": 0, "location_node": 1, "demand": 1.0}],
    })
    assert r.status_code == 409


def test_post_optimize_before_network() -> None:
    _reset_state()
    r = client.post("/optimize", json=_OPT)
    assert r.status_code == 409


def test_post_optimize_before_fleet() -> None:
    _reset_state()
    client.post("/network", json=_NET)
    r = client.post("/optimize", json=_OPT)
    assert r.status_code == 409


def test_get_routes_before_optimize() -> None:
    _reset_state()
    client.post("/network", json=_NET)
    r = client.get("/routes/current")
    assert r.status_code == 409


def test_post_incident_before_optimize() -> None:
    _reset_state()
    client.post("/network", json=_NET)
    r = client.post("/incidents", json={
        "edge_u": 0, "edge_v": 1,
        "incident_type": "ACCIDENT", "severity": "LOW",
    })
    assert r.status_code == 409


def test_get_convergence_before_optimize() -> None:
    _reset_state()
    client.post("/network", json=_NET)
    r = client.get("/analytics/convergence")
    assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# 6. POST /fleet – success
# ═══════════════════════════════════════════════════════════════════════════

def test_post_fleet_success() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    fleet_body = {
        "vehicles": [
            {"vehicle_id": 0, "capacity": 100.0, "depot_node": depot_node},
        ],
        "customers": [
            {"customer_id": i, "location_node": n, "demand": 5.0}
            for i, n in enumerate(customer_nodes[:2])
        ],
    }
    r = client.post("/fleet", json=fleet_body)
    assert r.status_code == 200
    data = r.json()
    assert data["n_vehicles"] == 1
    assert data["n_customers"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 7. POST /optimize – success
# ═══════════════════════════════════════════════════════════════════════════

def test_post_optimize_success() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    r = client.post("/optimize", json=_OPT)
    assert r.status_code == 200
    data = r.json()
    assert "best_fitness" in data
    assert math.isfinite(data["best_fitness"])
    assert "is_feasible" in data
    assert "n_iterations_run" in data
    assert data["n_iterations_run"] >= 1
    assert "routes" in data
    assert isinstance(data["routes"], list)


# ═══════════════════════════════════════════════════════════════════════════
# 8. GET /routes/current – success
# ═══════════════════════════════════════════════════════════════════════════

def test_get_routes_success() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()
    r = client.get("/routes/current")
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data
    assert "total_active" in data
    assert data["total_active"] == len(data["routes"])
    for route in data["routes"]:
        assert "vehicle_id" in route
        assert "node_sequence" in route
        assert "total_distance" in route
        assert "total_travel_time" in route


# ═══════════════════════════════════════════════════════════════════════════
# 9. POST /incidents – success
# ═══════════════════════════════════════════════════════════════════════════

def test_post_incident_success() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()

    open_edges = [e for e in net["edges"] if e["road_status"] == "open"]
    assert len(open_edges) > 0, "Test requires at least one open edge"
    edge = open_edges[0]

    r = client.post("/incidents", json={
        "edge_u": edge["u"],
        "edge_v": edge["v"],
        "incident_type": "ACCIDENT",
        "severity": "LOW",
        "description": "Test accident",
    })
    assert r.status_code == 200
    data = r.json()
    assert "affected_vehicle_ids" in data
    assert isinstance(data["affected_vehicle_ids"], list)
    assert "updated_routes" in data
    assert "unaffected_route_count" in data
    assert data["incident_type"] == "ACCIDENT"
    assert data["severity"] == "LOW"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Affected-route detection
# ═══════════════════════════════════════════════════════════════════════════

def test_affected_route_detection() -> None:
    """Verify that an incident placed directly on a vehicle's route is detected."""
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    opt_data = _do_optimize()

    routes = opt_data["routes"]
    assert len(routes) > 0, "Expected at least one route"
    target_route = routes[0]
    seq = target_route["node_sequence"]
    assert len(seq) >= 2, "Expected node sequence with at least one edge"

    u, v = seq[0], seq[1]
    r = client.post("/incidents", json={
        "edge_u": u,
        "edge_v": v,
        "incident_type": "ACCIDENT",
        "severity": "HIGH",
    })
    assert r.status_code == 200
    inc_data = r.json()
    assert target_route["vehicle_id"] in inc_data["affected_vehicle_ids"]
    assert inc_data["n_affected"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 11. Unaffected-route preservation
# ═══════════════════════════════════════════════════════════════════════════

def test_unaffected_route_preservation() -> None:
    """Verify that vehicles not using an incident edge retain valid routes."""
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    opt_data = _do_optimize()

    routes = opt_data["routes"]
    if len(routes) >= 2:
        r0 = routes[0]
        r1 = routes[1]
        edges0 = set(zip(r0["node_sequence"][:-1], r0["node_sequence"][1:]))
        edges1 = set(zip(r1["node_sequence"][:-1], r1["node_sequence"][1:]))
        unique_to_r0 = edges0 - edges1
        if unique_to_r0:
            u, v = next(iter(unique_to_r0))
            r = client.post("/incidents", json={
                "edge_u": u,
                "edge_v": v,
                "incident_type": "CONSTRUCTION",
                "severity": "LOW",
            })
            assert r.status_code == 200
            inc_data = r.json()
            assert r0["vehicle_id"] in inc_data["affected_vehicle_ids"]
            assert r1["vehicle_id"] not in inc_data["affected_vehicle_ids"]
            assert inc_data["unaffected_route_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 12. GET /analytics/convergence – success
# ═══════════════════════════════════════════════════════════════════════════

def test_get_convergence_success() -> None:
    net = _do_network()
    depot_node, customer_nodes = _get_depot_and_customers(net)
    _do_fleet(depot_node, customer_nodes)
    _do_optimize()

    r = client.get("/analytics/convergence")
    assert r.status_code == 200
    data = r.json()
    assert "n_iterations" in data
    assert "best_fitness" in data
    assert "history" in data
    assert len(data["history"]) > 0
    pt = data["history"][0]
    assert "iteration" in pt
    assert "fitness" in pt
    assert math.isfinite(data["best_fitness"])


# ═══════════════════════════════════════════════════════════════════════════
# 13. Full end-to-end flow
# ═══════════════════════════════════════════════════════════════════════════

def test_full_end_to_end_flow() -> None:
    """
    Complete pipeline: network -> fleet -> optimize -> routes -> incident
    -> routes -> convergence. All steps must return 200.
    """
    _reset_state()
    e2e = TestClient(app)

    # Step 1: Create network
    r = e2e.post("/network", json=_NET)
    assert r.status_code == 200, f"POST /network failed: {r.text}"
    net = r.json()
    depot_node, customer_nodes = _get_depot_and_customers(net)

    # Step 2: Configure fleet
    fleet_body = {
        "vehicles": [
            {"vehicle_id": 0, "capacity": 100.0, "depot_node": depot_node},
            {"vehicle_id": 1, "capacity": 100.0, "depot_node": depot_node},
        ],
        "customers": [
            {"customer_id": i, "location_node": n, "demand": 3.0}
            for i, n in enumerate(customer_nodes)
        ],
    }
    r = e2e.post("/fleet", json=fleet_body)
    assert r.status_code == 200, f"POST /fleet failed: {r.text}"

    # Step 3: Optimize
    r = e2e.post("/optimize", json=_OPT)
    assert r.status_code == 200, f"POST /optimize failed: {r.text}"
    opt = r.json()
    assert math.isfinite(opt["best_fitness"])

    # Step 4: Get routes
    r = e2e.get("/routes/current")
    assert r.status_code == 200, f"GET /routes/current failed: {r.text}"
    routes_before = r.json()
    assert routes_before["total_active"] >= 0

    # Step 5: Register incident on a real open edge
    open_edges = [e for e in net["edges"] if e["road_status"] == "open"]
    assert open_edges, "E2E test needs at least one open edge"
    edge = open_edges[0]
    r = e2e.post("/incidents", json={
        "edge_u": edge["u"],
        "edge_v": edge["v"],
        "incident_type": "CONSTRUCTION",
        "severity": "MEDIUM",
        "description": "E2E test incident",
    })
    assert r.status_code == 200, f"POST /incidents failed: {r.text}"
    inc_data = r.json()
    assert "affected_vehicle_ids" in inc_data

    # Step 6: Get updated routes
    r = e2e.get("/routes/current")
    assert r.status_code == 200, f"GET /routes/current (post-incident) failed: {r.text}"

    # Step 7: Get convergence
    r = e2e.get("/analytics/convergence")
    assert r.status_code == 200, f"GET /analytics/convergence failed: {r.text}"
    conv = r.json()
    assert len(conv["history"]) > 0
