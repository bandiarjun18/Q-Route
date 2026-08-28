"""
app/qpso/repair.py – Deterministic capacity-violation repair for Q-Route QPSO.

Public API
----------
repair_capacity(solution, problem) → VRPSolution

Repair strategy
---------------
For each vehicle route whose total assigned demand exceeds the vehicle's
capacity, customers are sorted by demand (largest first) and moved one-by-one
to the first other vehicle that has sufficient remaining capacity.

After each reassignment the receiving (and donating) vehicle's node_sequence
is rebuilt via Dijkstra chaining, exactly as the original decoder does.

Guarantees
----------
- No customer is dropped.
- No customer is duplicated.
- Vehicle depot start/end constraints are preserved (Dijkstra always starts
  and ends at the depot).
- Only capacity violations are targeted; other violation types (connectivity,
  road-availability) are left unchanged for the penalty mechanism in
  ``compute_fitness`` to handle.
- The input ``VRPSolution`` is never mutated.

Design notes
------------
Importing ``_build_node_sequence`` from ``representation`` is intentional:
it is the canonical Dijkstra-chaining implementation and must not be
reimplemented here.  The leading underscore signals it is an internal
helper, but the repair module is considered part of the same package and
may use it directly.
"""

from __future__ import annotations

from typing import Any

from app.vrp.models import VRPProblem, VRPSolution, VehicleRoute

# Intentional internal-package import: reuse the canonical Dijkstra chainer.
from .representation import _build_node_sequence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def repair_capacity(
    solution: VRPSolution,
    problem: VRPProblem,
) -> VRPSolution:
    """
    Attempt to repair vehicle-capacity violations by reassigning customers.

    Parameters
    ----------
    solution : VRPSolution – decoded (possibly infeasible) solution to repair
    problem  : VRPProblem  – the VRP instance being solved

    Returns
    -------
    A new VRPSolution with attempted capacity repairs applied.  Routes that
    could not be fixed (no other vehicle had sufficient slack) are returned
    unchanged so the existing penalty mechanism can score them.
    """
    vehicle_by_id: dict[Any, Any] = {v.vehicle_id: v for v in problem.vehicles}
    customer_by_id = problem.customer_by_id

    # ── Mutable working copies of each vehicle's assignment ──────────────
    # assignments[vid] = ordered list of customer_ids for that vehicle.
    assignments: dict[Any, list[Any]] = {
        route.vehicle_id: list(route.visit_order)
        for route in solution.routes
    }

    # Current load per vehicle (sum of assigned demands).
    loads: dict[Any, float] = {
        vid: sum(
            customer_by_id[cid].demand
            for cid in cids
            if cid in customer_by_id
        )
        for vid, cids in assignments.items()
    }

    # Track which vehicle routes were modified so we only rebuild those.
    changed_vids: set[Any] = set()

    # ── Repair each overloaded vehicle ───────────────────────────────────
    for route in solution.routes:
        vid = route.vehicle_id
        vehicle = vehicle_by_id.get(vid)
        if vehicle is None:
            continue

        # Tolerance of 1e-9 avoids false positives from floating-point noise.
        if loads[vid] <= vehicle.capacity + 1e-9:
            continue  # Within capacity — nothing to do.

        # Sort candidates by demand descending so the largest overflow is
        # addressed first (greedy: minimises the number of moves needed).
        candidates = sorted(
            assignments[vid],
            key=lambda cid: (
                customer_by_id[cid].demand if cid in customer_by_id else 0.0
            ),
            reverse=True,
        )

        for cid in candidates:
            if loads[vid] <= vehicle.capacity + 1e-9:
                break  # This route is now within capacity.

            if cid not in customer_by_id:
                continue
            demand = customer_by_id[cid].demand

            # Find the first other vehicle that can absorb this customer.
            for other_vid in assignments:
                if other_vid == vid:
                    continue
                other_vehicle = vehicle_by_id.get(other_vid)
                if other_vehicle is None:
                    continue
                if loads[other_vid] + demand <= other_vehicle.capacity + 1e-9:
                    # Move the customer to the other vehicle.
                    assignments[vid].remove(cid)
                    loads[vid] -= demand
                    assignments[other_vid].append(cid)
                    loads[other_vid] += demand
                    changed_vids.add(vid)
                    changed_vids.add(other_vid)
                    break
            # If no vehicle had room, leave the customer in place; the
            # feasibility penalty will score the remaining violation.

    # ── Rebuild routes (only for vehicles whose assignment changed) ──────
    new_routes: list[VehicleRoute] = []
    for route in solution.routes:
        vid = route.vehicle_id
        if vid not in changed_vids:
            # Unchanged: shallow copy, preserving the original node_sequence.
            new_routes.append(
                VehicleRoute(
                    vehicle_id=route.vehicle_id,
                    depot_node=route.depot_node,
                    visit_order=list(route.visit_order),
                    node_sequence=list(route.node_sequence),
                )
            )
        else:
            vehicle = vehicle_by_id.get(vid)
            depot = vehicle.depot_node if vehicle else route.depot_node
            new_cid_order = assignments[vid]
            new_customers = [
                customer_by_id[cid]
                for cid in new_cid_order
                if cid in customer_by_id
            ]
            new_seq = _build_node_sequence(depot, new_customers, problem.graph)
            new_routes.append(
                VehicleRoute(
                    vehicle_id=vid,
                    depot_node=depot,
                    visit_order=list(new_cid_order),
                    node_sequence=new_seq,
                )
            )

    return VRPSolution(routes=new_routes)
