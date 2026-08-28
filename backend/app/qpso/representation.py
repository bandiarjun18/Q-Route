"""
app/qpso/representation.py – Priority-key encoding and decoding for QPSO VRP.

Route representation
--------------------
A QPSO particle is a real-valued vector of length N (number of customers):

    keys = [k₀, k₁, …, k_{N-1}]   where kᵢ ∈ ℝ  (typically clamped to [0, 1])

The *relative order* of the values is what matters — absolute values are
irrelevant for the decoder.  This makes the encoding continuous and smooth,
which is exactly what the QPSO quantum update rule expects.

Decoding pipeline
-----------------
1. **Sort customers** by their priority key (ascending).
2. **Assign customers to vehicles** using first-fit, capacity-aware greedy:
   - Scan sorted customers in order.
   - For each customer, try to place it in the first vehicle that still has
     remaining capacity.
   - If no vehicle can accommodate the customer without exceeding capacity,
     place it in the vehicle with the smallest current load (soft violation —
     the feasibility checker will detect the overflow and penalise it).
3. **Build node_sequence** for each vehicle:
   - Start at the vehicle's depot.
   - For each assigned customer in order, run Dijkstra (``shortest_path``)
     from the current tail of the sequence to the customer's location node,
     appending all intermediate hops.
   - Return to depot via Dijkstra.
   - If Dijkstra raises ``NetworkXNoPath`` for any segment, fall back to a
     direct node jump (the feasibility checker flags it as disconnected).
4. Construct and return a ``VRPSolution`` with one ``VehicleRoute`` per vehicle.

Public API
----------
encode_random(n_customers, rng)  → np.ndarray   – random particle in [0,1]
decode(keys, problem)            → VRPSolution  – full decoder
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx
import numpy as np

from app.graph.pathfinding import shortest_path
from app.vrp.models import Customer, Vehicle, VRPProblem, VehicleRoute, VRPSolution


# ---------------------------------------------------------------------------
# Encoding (random initialisation)
# ---------------------------------------------------------------------------

def encode_random(n_customers: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate a random particle: N priority keys uniformly drawn from [0, 1].

    Parameters
    ----------
    n_customers : int                 – dimensionality of the particle
    rng         : np.random.Generator – seeded RNG for reproducibility

    Returns
    -------
    np.ndarray of shape (n_customers,) with values in [0, 1]
    """
    return rng.uniform(0.0, 1.0, size=n_customers)


# ---------------------------------------------------------------------------
# Greedy capacity-aware customer assignment
# ---------------------------------------------------------------------------

def _assign_customers(
    sorted_customers: list[Customer],
    vehicles: list[Vehicle],
) -> list[list[Customer]]:
    """
    Assign customers to vehicles using first-fit capacity-aware greedy.

    Customers are processed in the order given (caller is responsible for
    sorting by priority key first).  Each customer is placed in the first
    vehicle that still has enough remaining capacity.  If no vehicle can
    accommodate the customer without overflowing, it goes to the vehicle
    with the smallest current load (soft constraint violation, penalised
    by the fitness function).

    Parameters
    ----------
    sorted_customers : list[Customer] – customers in priority-key order
    vehicles         : list[Vehicle]  – fleet

    Returns
    -------
    list of lists: one inner list per vehicle, containing the assigned
    Customer objects in the order they were assigned.
    """
    n_vehicles = len(vehicles)
    assignments: list[list[Customer]] = [[] for _ in range(n_vehicles)]
    loads: list[float] = [0.0] * n_vehicles

    for customer in sorted_customers:
        placed = False
        for v_idx, vehicle in enumerate(vehicles):
            if loads[v_idx] + customer.demand <= vehicle.capacity:
                assignments[v_idx].append(customer)
                loads[v_idx] += customer.demand
                placed = True
                break

        if not placed:
            # Soft violation: place on least-loaded vehicle
            min_idx = int(np.argmin(loads))
            assignments[min_idx].append(customer)
            loads[min_idx] += customer.demand

    return assignments


# ---------------------------------------------------------------------------
# Node-sequence builder (Dijkstra chaining)
# ---------------------------------------------------------------------------

def _build_node_sequence(
    depot: Any,
    assigned_customers: list[Customer],
    tg,
) -> list:
    """
    Build the full graph-node sequence for one vehicle's route.

    The sequence starts at ``depot``, threads through each customer's
    location node via Dijkstra shortest-paths, then returns to ``depot``.

    An idle vehicle (no customers) returns ``[depot]`` — a single-element
    sequence that will be flagged by the feasibility checker and penalised,
    which guides the optimizer away from idle-vehicle solutions.

    Parameters
    ----------
    depot              : graph node id
    assigned_customers : list[Customer] – ordered customers to visit
    tg                 : TransportGraph

    Returns
    -------
    list of graph node ids forming the complete route
    """
    if not assigned_customers:
        return [depot]

    seq: list = [depot]

    for customer in assigned_customers:
        target = customer.location_node
        current = seq[-1]
        if current == target:
            # Already there — no movement needed
            continue
        try:
            path, _ = shortest_path(tg, current, target)
            seq.extend(path[1:])          # skip first node (= current)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            seq.append(target)            # direct jump → connectivity violation

    # Return to depot
    current = seq[-1]
    if current != depot:
        try:
            path_back, _ = shortest_path(tg, current, depot)
            seq.extend(path_back[1:])
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            seq.append(depot)             # direct jump → connectivity violation

    return seq


# ---------------------------------------------------------------------------
# Decoder (priority keys → VRPSolution)
# ---------------------------------------------------------------------------

def decode(
    keys: np.ndarray,
    problem: VRPProblem,
) -> VRPSolution:
    """
    Decode a QPSO particle (priority-key vector) into a concrete VRPSolution.

    Steps
    -----
    1. Sort customers by key value (ascending).
    2. Assign sorted customers to vehicles (first-fit, capacity-aware).
    3. Build node_sequence per vehicle using Dijkstra chaining.
    4. Construct VehicleRoute + VRPSolution.

    Note: The returned solution is *not* evaluated yet (``objective_value``
    and ``is_feasible`` remain at their defaults).  Call ``compute_fitness``
    and ``check_feasibility`` to populate those fields.

    Parameters
    ----------
    keys    : np.ndarray of shape (n_customers,) – particle position
    problem : VRPProblem

    Returns
    -------
    VRPSolution with one VehicleRoute per vehicle, routes not yet evaluated.
    """
    customers = problem.customers
    vehicles = problem.vehicles
    n = len(customers)

    if len(keys) != n:
        raise ValueError(
            f"keys length {len(keys)} does not match "
            f"number of customers {n}"
        )

    # 1. Sort customers by priority key
    order = np.argsort(keys)                   # indices that sort ascending
    sorted_customers = [customers[i] for i in order]

    # 2. Greedy capacity assignment
    assignments = _assign_customers(sorted_customers, vehicles)

    # 3. Build VehicleRoute per vehicle
    routes: list[VehicleRoute] = []
    for v_idx, vehicle in enumerate(vehicles):
        assigned = assignments[v_idx]
        visit_order = [c.customer_id for c in assigned]
        node_seq = _build_node_sequence(vehicle.depot_node, assigned, problem.graph)
        routes.append(
            VehicleRoute(
                vehicle_id=vehicle.vehicle_id,
                depot_node=vehicle.depot_node,
                visit_order=visit_order,
                node_sequence=node_seq,
            )
        )

    return VRPSolution(routes=routes)
