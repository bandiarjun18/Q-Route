"""
demo_e2e.py – Standalone End-to-End Real-World Demonstration for Q-Route (Milestone 13.10).

Executes the complete real-world logistics pipeline:
1. Real-World OSM Road Network Loading (Bangalore Central Logistics District)
2. Geographic Fleet & Customer Delivery Configuration
3. Multi-Vehicle QPSO Route Optimization
4. Active Route & Geographic Polyline Geometry Inspection
5. Live Road Closure Incident Injection & Selective Dynamic Rerouting
6. Database Audit & Operational State Verification

Usage:
    python backend/demo_e2e.py
"""

from __future__ import annotations

import sys
import time
from fastapi.testclient import TestClient

from app.main import app
from app.api.state import AppState
from app.db.session import SessionLocal
from app.db.models import (
    NetworkModel,
    NodeModel,
    EdgeModel,
    FleetVehicleModel,
    CustomerModel,
    OptimizationRunModel,
    RouteModel,
    IncidentModel,
)
from sqlalchemy import select


def run_demo() -> bool:
    print("=" * 80)
    print("       Q-ROUTE: REAL-WORLD END-TO-END DEMONSTRATION (MILESTONE 13.10)")
    print("=" * 80)

    client = TestClient(app)
    app.state.qroute = AppState()
    session = SessionLocal()

    net_id = None
    try:
        # ── STEP 1: Load Real-World OSM Network ─────────────────────────────
        print("\n[STEP 1/6] Ingesting Real-World OpenStreetMap Urban Road Network...")
        t0 = time.time()
        r_net = client.post("/network/osm-preset", json={"preset_name": "bangalore_urban"})
        if r_net.status_code != 200:
            print(f"[-] Failed to load network: {r_net.text}")
            return False

        net_data = r_net.json()
        net_id = app.state.qroute.network_db_id
        print(f" [+] Real OSM Network Ingested in {time.time() - t0:.2f}s")
        print(f"     - Network ID: {net_id}")
        print(f"     - Nodes: {net_data['n_nodes']} (with true GPS lat/lon coordinates)")
        print(f"     - Directed Edges: {net_data['n_edges']} (with OSM road segment geometry & speed limits)")

        # ── STEP 2: Configure Geographic Fleet & Customers ──────────────────
        print("\n[STEP 2/6] Configuring Geographic Fleet & Snapping Delivery Locations...")
        t0 = time.time()
        r_fleet = client.post("/fleet/geographic-preset")
        if r_fleet.status_code != 200:
            print(f"[-] Failed to configure fleet: {r_fleet.text}")
            return False

        fleet_data = r_fleet.json()
        print(f" [+] Fleet Configured in {time.time() - t0:.2f}s")
        print(f"     - Vehicles: {fleet_data['n_vehicles']} (Central Logistics Hub @ MG Road)")
        print(f"     - Customer Orders: {fleet_data['n_customers']} (snapped to nearest OSM intersections)")

        # ── STEP 3: Multi-Vehicle QPSO Optimization ─────────────────────────
        print("\n[STEP 3/6] Running Quantum PSO Route Optimization (QPSO + 2-Opt)...")
        t0 = time.time()
        r_opt = client.post(
            "/optimize",
            json={
                "n_particles": 20,
                "max_iterations": 80,
                "seed": 42,
                "w_time": 1.0,
                "w_distance": 0.5,
                "w_congestion": 0.3,
            },
        )
        if r_opt.status_code != 200:
            print(f"[-] Optimization failed: {r_opt.text}")
            return False

        opt_data = r_opt.json()
        initial_opt_id = app.state.qroute.opt_run_db_id
        print(f" [+] Optimization Completed in {time.time() - t0:.2f}s")
        print(f"     - Feasible: {opt_data['is_feasible']}")
        print(f"     - Best Objective Fitness: {opt_data['best_fitness']:.3f}")
        print(f"     - Active Vehicle Routes Produced: {opt_data['n_routes']}")
        print(f"     - Persisted to PostgreSQL (Run ID: {initial_opt_id})")

        # ── STEP 4: Retrieve Geographic Route Geometries ────────────────────
        print("\n[STEP 4/6] Retrieving Live Operational Routes for Leaflet OSM Map...")
        r_geo = client.get("/routes/geographic")
        if r_geo.status_code != 200:
            print(f"[-] Failed to get geographic routes: {r_geo.text}")
            return False

        geo_data = r_geo.json()
        print(f" [+] Geographic Visualization Payload Ready (is_geographic: {geo_data['is_geographic']})")
        print(f"     - Map Center: {geo_data['center']}")
        for gr in geo_data["routes"]:
            print(
                f"     - Route [Veh #{gr['vehicle_id']}]: {len(gr['node_sequence'])} nodes, "
                f"{len(gr['coordinates'])} GPS polyline points, "
                f"{gr['total_distance']:.2f} km, {gr['total_travel_time']:.2f} min"
            )

        # ── STEP 5: Live Road Closure Incident & Dynamic Rerouting ──────────
        r_curr = client.get("/routes/current")
        curr_data = r_curr.json()
        route_0 = curr_data["routes"][0]
        seq = route_0["node_sequence"]
        u_closed = str(seq[0])
        v_closed = str(seq[1])

        print(f"\n[STEP 5/6] Simulating Emergency Road Closure on Active Corridor (N{u_closed} -> N{v_closed})...")
        t0 = time.time()
        r_inc = client.post(
            "/incidents",
            json={
                "edge_u": u_closed,
                "edge_v": v_closed,
                "incident_type": "ROAD_CLOSURE",
                "severity": "CRITICAL",
                "description": "Emergency pipeline burst closure",
            },
        )
        if r_inc.status_code != 200:
            print(f"[-] Incident registration failed: {r_inc.text}")
            return False

        inc_data = r_inc.json()
        post_opt_id = app.state.qroute.opt_run_db_id
        print(f" [+] Selective Dynamic Rerouting Executed in {time.time() - t0:.2f}s")
        print(f"     - Road Closure Applied: Edge N{inc_data['edge_u']} -> N{inc_data['edge_v']}")
        print(f"     - Affected Vehicles Rerouted: {inc_data['affected_vehicle_ids']}")
        print(f"     - Unaffected Routes Preserved: {inc_data['unaffected_route_count']}")
        print(f"     - Post-Incident Optimization Run Persisted: {post_opt_id}")

        # ── STEP 6: Database Audit & Post-Incident Verification ─────────────
        print("\n[STEP 6/6] Verifying PostgreSQL Audit Trail & Operational Synchronization...")
        session.expire_all()

        db_edge = session.execute(
            select(EdgeModel).where(
                EdgeModel.network_id == net_id,
                EdgeModel.u == u_closed,
                EdgeModel.v == v_closed,
            )
        ).scalar_one_or_none()
        assert db_edge is not None
        print(f" [+] PostgreSQL Edge Status: {db_edge.road_status.upper()}")

        db_inc = session.execute(
            select(IncidentModel).where(IncidentModel.network_id == net_id)
        ).scalars().all()
        print(f" [+] PostgreSQL Incidents Recorded: {len(db_inc)} (Linked Run: {db_inc[0].optimization_run_id})")

        db_runs = session.execute(
            select(OptimizationRunModel).where(OptimizationRunModel.network_id == net_id)
        ).scalars().all()
        print(f" [+] PostgreSQL Total Optimization Runs: {len(db_runs)} (Initial + Post-Incident Reroute)")

        r_curr_post = client.get("/routes/current")
        post_curr = r_curr_post.json()
        print("\n[LIVE OPERATIONAL ROUTES AFTER REROUTING]")
        for r in post_curr["routes"]:
            print(
                f" -> Veh #{r['vehicle_id']} [Status: {r['status']}]: "
                f"Path: {' -> '.join(str(n) for n in r['node_sequence'])} | "
                f"Distance: {r['total_distance']:.2f} km | "
                f"ETA: {r['total_travel_time']:.2f} min"
            )

        print("\n" + "=" * 80)
        print(" [SUCCESS] REAL-WORLD END-TO-END DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        return True

    finally:
        # Clean up demo database records
        if net_id:
            net = session.execute(select(NetworkModel).where(NetworkModel.id == net_id)).scalar_one_or_none()
            if net:
                session.delete(net)
                session.commit()
        session.close()


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
