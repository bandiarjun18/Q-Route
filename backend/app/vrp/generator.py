"""
app/vrp/generator.py – Synthetic fleet + customer/demand generator for Q-Route.

Generates reproducible VRP instances that can be saved to JSON and loaded back,
so experiments always start from identical initial conditions.

Generation strategy
-------------------
1. Generate (or accept) a TransportGraph using the Milestone-2 graph generator.
2. Identify depot nodes in the graph (node_type == "depot").
3. If no depot nodes exist, fall back to node 0.
4. Create Vehicle objects: one per requested vehicle, cycling through depot nodes.
5. Identify customer nodes in the graph (node_type == "customer").
6. If there are fewer graph-customer nodes than requested, supplement with
   intersection nodes so n_customers is always satisfied.
7. Assign random demands within [demand_min, demand_max].
8. Vehicle capacities are set to comfortably cover a fair share of total demand
   (configurable via capacity_factor).

JSON schema (data/synthetic_vrp_*.json)
---------------------------------------
{
  "meta": {
    "n_vehicles": int, "n_customers": int, "seed": int, ...
  },
  "graph": { "nodes": [...], "edges": [...] },       ← TransportGraph.to_dict()
  "vehicles": [
    {"vehicle_id": ..., "capacity": ..., "depot_node": ...},
    ...
  ],
  "customers": [
    {"customer_id": ..., "location_node": ..., "demand": ...},
    ...
  ]
}

CLI usage (from backend/ directory)
-------------------------------------
    python -m app.vrp.generator                              # defaults
    python -m app.vrp.generator --vehicles 3 --customers 8  # custom
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Tuple, Union

import numpy as np

from app.graph.generator import generate_synthetic_network
from app.graph.model import TransportGraph
from app.graph.osm import (
    OSMInvalidDataError,
    nearest_graph_node,
    map_coordinates_to_nodes,
)
from app.vrp.models import Customer, Vehicle, VRPProblem


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_vrp_instance(
    n_vehicles: int = 2,
    n_customers: int = 6,
    n_nodes: int = 20,
    n_depots: int = 1,
    capacity_factor: float = 1.5,
    demand_min: float = 1.0,
    demand_max: float = 10.0,
    connect_radius_km: float = 3.5,
    grid_size_km: float = 10.0,
    closed_fraction: float = 0.05,
    seed: int = 42,
    graph: TransportGraph | None = None,
) -> VRPProblem:
    """
    Generate a reproducible synthetic VRP instance.

    Parameters
    ----------
    n_vehicles       : number of vehicles in the fleet
    n_customers      : number of customer orders to serve
    n_nodes          : total graph nodes (only used when graph=None)
    n_depots         : depot nodes in the graph (only used when graph=None)
    capacity_factor  : vehicle capacity = (total_demand / n_vehicles) * factor
    demand_min       : minimum per-customer demand (inclusive)
    demand_max       : maximum per-customer demand (inclusive)
    connect_radius_km: graph generation parameter (ignored when graph≠None)
    grid_size_km     : graph generation parameter (ignored when graph≠None)
    closed_fraction  : fraction of non-MST edges to close (ignored when graph≠None)
    seed             : NumPy random seed for reproducibility
    graph            : pre-built TransportGraph; if None a new one is generated

    Returns
    -------
    VRPProblem with fleet and customer list ready for solving.
    """
    rng = np.random.default_rng(seed)

    # ── 1. Build or use the transport graph ───────────────────────────────
    if graph is None:
        # Ensure graph has enough customer nodes for the requested count
        net_customers = max(n_customers, 1)
        net_data = generate_synthetic_network(
            n_nodes=n_nodes,
            n_depots=n_depots,
            n_customers=net_customers,
            connect_radius_km=connect_radius_km,
            grid_size_km=grid_size_km,
            closed_fraction=closed_fraction,
            seed=seed,
        )
        tg = TransportGraph.from_dict(net_data)
    else:
        tg = graph

    g = tg.graph

    # ── 2. Identify depot candidates ──────────────────────────────────────
    depot_nodes = [
        n for n, d in g.nodes(data=True) if d.get("node_type") == "depot"
    ]
    if not depot_nodes:
        # Fallback: use node 0 as depot
        depot_nodes = [list(g.nodes())[0]]

    # ── 3. Create vehicles ────────────────────────────────────────────────
    # Capacity is assigned *after* we know total demand (see step 5).
    vehicle_depot_map: list[Any] = [
        depot_nodes[i % len(depot_nodes)] for i in range(n_vehicles)
    ]

    # ── 4. Identify customer node candidates ──────────────────────────────
    customer_nodes = [
        n for n, d in g.nodes(data=True) if d.get("node_type") == "customer"
    ]
    # Supplement with intersection nodes if we need more stops
    intersection_nodes = [
        n for n, d in g.nodes(data=True)
        if d.get("node_type") == "intersection"
    ]
    # Avoid using depot nodes as customer stops
    avoid = set(depot_nodes)
    extra_pool = [n for n in intersection_nodes if n not in avoid]

    # Build final candidate list
    candidate_nodes: list[Any] = list(customer_nodes)
    if len(candidate_nodes) < n_customers:
        needed = n_customers - len(candidate_nodes)
        # Shuffle extras with seeded rng for reproducibility
        rng_extra = np.random.default_rng(seed + 1)
        rng_extra.shuffle(extra_pool)
        candidate_nodes.extend(extra_pool[:needed])

    # Pick exactly n_customers (sample without replacement if enough, else use all)
    actual_n = min(n_customers, len(candidate_nodes))
    if actual_n < n_customers:
        # Edge-case: graph is tiny; use what we have
        selected_nodes = candidate_nodes[:actual_n]
    else:
        # Sample without replacement for variety
        idx = rng.choice(len(candidate_nodes), size=actual_n, replace=False)
        selected_nodes = [candidate_nodes[int(i)] for i in idx]

    # ── 5. Assign demands ─────────────────────────────────────────────────
    demands = [
        round(float(rng.uniform(demand_min, demand_max)), 4)
        for _ in range(actual_n)
    ]
    total_demand = sum(demands)

    # ── 6. Compute vehicle capacities ────────────────────────────────────
    # Each vehicle gets capacity = (total_demand / n_vehicles) * capacity_factor
    # so a single vehicle cannot serve all customers (forces distribution).
    per_vehicle_capacity = round(
        max(demand_max, (total_demand / n_vehicles) * capacity_factor), 4
    )

    vehicles: list[Vehicle] = [
        Vehicle(
            vehicle_id=i,
            capacity=per_vehicle_capacity,
            depot_node=vehicle_depot_map[i],
        )
        for i in range(n_vehicles)
    ]

    customers: list[Customer] = [
        Customer(
            customer_id=j,
            location_node=selected_nodes[j],
            demand=demands[j],
        )
        for j in range(actual_n)
    ]

    return VRPProblem(graph=tg, vehicles=vehicles, customers=customers)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def vrp_problem_to_dict(problem: VRPProblem) -> dict:
    """
    Serialise a VRPProblem to a plain dict suitable for JSON output.

    Schema matches ``load_vrp_json`` expectations.
    """
    return {
        "meta": {
            "n_vehicles": len(problem.vehicles),
            "n_customers": len(problem.customers),
        },
        "graph": problem.graph.to_dict(),
        "vehicles": [
            {
                "vehicle_id": v.vehicle_id,
                "capacity": v.capacity,
                "depot_node": v.depot_node,
            }
            for v in problem.vehicles
        ],
        "customers": [
            {
                "customer_id": c.customer_id,
                "location_node": c.location_node,
                "demand": c.demand,
            }
            for c in problem.customers
        ],
    }


def vrp_problem_from_dict(data: dict) -> VRPProblem:
    """
    Reconstruct a VRPProblem from a dict produced by ``vrp_problem_to_dict``.
    """
    tg = TransportGraph.from_dict(data["graph"])
    vehicles = [
        Vehicle(
            vehicle_id=v["vehicle_id"],
            capacity=v["capacity"],
            depot_node=v["depot_node"],
        )
        for v in data["vehicles"]
    ]
    customers = [
        Customer(
            customer_id=c["customer_id"],
            location_node=c["location_node"],
            demand=c["demand"],
        )
        for c in data["customers"]
    ]
    return VRPProblem(graph=tg, vehicles=vehicles, customers=customers)


def save_vrp_json(problem: VRPProblem, path: str | Path) -> Path:
    """Persist a VRPProblem to a JSON file; creates parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = vrp_problem_to_dict(problem)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


def load_vrp_json(path: str | Path) -> VRPProblem:
    """Load a VRPProblem from a JSON file produced by ``save_vrp_json``."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return vrp_problem_from_dict(data)


# ---------------------------------------------------------------------------
# Geographic Location -> VRP Primitives Mapping (Milestone 13.5)
# ---------------------------------------------------------------------------

def map_customer_location(
    graph: TransportGraph,
    latitude: float,
    longitude: float,
) -> Any:
    """
    Map a customer's geographic coordinate (latitude, longitude) to the nearest
    TransportGraph node ID.
    """
    return nearest_graph_node(graph, latitude=latitude, longitude=longitude)


def map_depot_location(
    graph: TransportGraph,
    latitude: float,
    longitude: float,
) -> Any:
    """
    Map a vehicle depot's geographic coordinate (latitude, longitude) to the nearest
    TransportGraph node ID.
    """
    return nearest_graph_node(graph, latitude=latitude, longitude=longitude)


def map_customer_locations(
    graph: TransportGraph,
    coordinates: Iterable[Tuple[float, float]],
) -> list[Any]:
    """
    Batch map multiple customer coordinates (latitude, longitude) to their respective
    nearest TransportGraph node IDs.
    """
    return map_coordinates_to_nodes(graph, coordinates)


def create_geographic_customer(
    graph: TransportGraph,
    customer_id: Any,
    latitude: float,
    longitude: float,
    demand: float,
) -> Customer:
    """
    Construct a Customer instance by mapping geographic coordinates (latitude, longitude)
    to the nearest TransportGraph node ID.
    """
    location_node = map_customer_location(graph, latitude=latitude, longitude=longitude)
    return Customer(customer_id=customer_id, location_node=location_node, demand=demand)


def create_geographic_vehicle(
    graph: TransportGraph,
    vehicle_id: Any,
    capacity: float,
    depot_latitude: float,
    depot_longitude: float,
) -> Vehicle:
    """
    Construct a Vehicle instance by mapping geographic depot coordinates (latitude, longitude)
    to the nearest TransportGraph node ID.
    """
    depot_node = map_depot_location(graph, latitude=depot_latitude, longitude=depot_longitude)
    return Vehicle(vehicle_id=vehicle_id, capacity=capacity, depot_node=depot_node)


def create_geographic_customers(
    graph: TransportGraph,
    customer_specs: Iterable[Union[dict[str, Any], Tuple[Any, float, float, float]]],
) -> list[Customer]:
    """
    Batch construct Customer instances from geographic specifications.

    Accepts dicts with keys ('customer_id', 'latitude', 'longitude', 'demand') or
    tuples of (customer_id, latitude, longitude, demand).
    """
    customers: list[Customer] = []
    for spec in customer_specs:
        if isinstance(spec, dict):
            cid = spec.get("customer_id")
            lat = spec.get("latitude", spec.get("lat"))
            lon = spec.get("longitude", spec.get("lon"))
            dem = spec.get("demand")
            if cid is None or lat is None or lon is None or dem is None:
                raise OSMInvalidDataError(
                    f"Customer dict spec must contain 'customer_id', 'latitude', 'longitude', and 'demand': {spec!r}"
                )
        elif isinstance(spec, (tuple, list)) and len(spec) == 4:
            cid, lat, lon, dem = spec
        else:
            raise OSMInvalidDataError(
                f"Customer specification must be a dict or 4-tuple (customer_id, lat, lon, demand), got {spec!r}"
            )
        customers.append(
            create_geographic_customer(graph, customer_id=cid, latitude=lat, longitude=lon, demand=dem)
        )
    return customers


def create_geographic_vehicles(
    graph: TransportGraph,
    vehicle_specs: Iterable[Union[dict[str, Any], Tuple[Any, float, float, float]]],
) -> list[Vehicle]:
    """
    Batch construct Vehicle instances from geographic depot specifications.

    Accepts dicts with keys ('vehicle_id', 'capacity', 'depot_latitude', 'depot_longitude')
    or ('vehicle_id', 'capacity', 'lat', 'lon'), or tuples of (vehicle_id, capacity, depot_lat, depot_lon).
    """
    vehicles: list[Vehicle] = []
    for spec in vehicle_specs:
        if isinstance(spec, dict):
            vid = spec.get("vehicle_id")
            cap = spec.get("capacity")
            lat = spec.get("depot_latitude", spec.get("latitude", spec.get("lat")))
            lon = spec.get("depot_longitude", spec.get("longitude", spec.get("lon")))
            if vid is None or cap is None or lat is None or lon is None:
                raise OSMInvalidDataError(
                    f"Vehicle dict spec must contain 'vehicle_id', 'capacity', depot latitude, and depot longitude: {spec!r}"
                )
        elif isinstance(spec, (tuple, list)) and len(spec) == 4:
            vid, cap, lat, lon = spec
        else:
            raise OSMInvalidDataError(
                f"Vehicle specification must be a dict or 4-tuple (vehicle_id, capacity, depot_lat, depot_lon), got {spec!r}"
            )
        vehicles.append(
            create_geographic_vehicle(graph, vehicle_id=vid, capacity=cap, depot_latitude=lat, depot_longitude=lon)
        )
    return vehicles


def build_geographic_vrp_problem(
    graph: TransportGraph,
    vehicles: Union[list[Vehicle], Iterable[Union[dict[str, Any], Tuple[Any, float, float, float]]]],
    customers: Union[list[Customer], Iterable[Union[dict[str, Any], Tuple[Any, float, float, float]]]],
) -> VRPProblem:
    """
    Construct a canonical VRPProblem from a TransportGraph and geographic vehicle/customer specifications.
    """
    processed_vehicles: list[Vehicle] = []
    for v in vehicles:
        if isinstance(v, Vehicle):
            processed_vehicles.append(v)
        else:
            processed_vehicles.extend(create_geographic_vehicles(graph, [v]))

    processed_customers: list[Customer] = []
    for c in customers:
        if isinstance(c, Customer):
            processed_customers.append(c)
        else:
            processed_customers.extend(create_geographic_customers(graph, [c]))

    return VRPProblem(graph=graph, vehicles=processed_vehicles, customers=processed_customers)



# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a synthetic Q-Route VRP instance "
            "(fleet + customers) and save it to JSON."
        )
    )
    parser.add_argument("--vehicles", type=int, default=2, help="Number of vehicles (default 2)")
    parser.add_argument("--customers", type=int, default=6, help="Number of customers (default 6)")
    parser.add_argument("--nodes", type=int, default=20, help="Graph nodes (default 20)")
    parser.add_argument("--depots", type=int, default=1, help="Depot nodes in graph (default 1)")
    parser.add_argument("--radius", type=float, default=3.5, help="Connection radius km (default 3.5)")
    parser.add_argument("--grid", type=float, default=10.0, help="Grid side km (default 10.0)")
    parser.add_argument("--closed", type=float, default=0.05, help="Closed-edge fraction (default 0.05)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument(
        "--out",
        type=str,
        default="../data/synthetic_vrp_default.json",
        help="Output JSON path (default ../data/synthetic_vrp_default.json)",
    )
    args = parser.parse_args()

    problem = generate_vrp_instance(
        n_vehicles=args.vehicles,
        n_customers=args.customers,
        n_nodes=args.nodes,
        n_depots=args.depots,
        connect_radius_km=args.radius,
        grid_size_km=args.grid,
        closed_fraction=args.closed,
        seed=args.seed,
    )

    out_path = save_vrp_json(problem, args.out)

    print("Generated synthetic VRP instance:")
    print(f"  Vehicles  : {len(problem.vehicles)}")
    print(f"  Customers : {len(problem.customers)}")
    print(f"  Graph nodes: {problem.graph.node_count()}")
    print(f"  Graph edges: {problem.graph.edge_count()} directed")
    print(f"  Depots    : {[v.depot_node for v in problem.vehicles]}")
    print(f"  Seed      : {args.seed}")
    print(f"  Saved to  : {out_path.resolve()}")


if __name__ == "__main__":
    _cli()
