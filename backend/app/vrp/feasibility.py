"""
app/vrp/feasibility.py – Hard-constraint feasibility checker for Q-Route VRP.

Public API
----------
check_feasibility(solution, problem) → FeasibilityResult

Constraints enforced
--------------------
1. Vehicle capacity   – sum of assigned demands ≤ vehicle.capacity
2. Customer coverage  – every required customer appears in exactly one route
3. Depot constraint   – every route's node_sequence starts and ends at its
                        vehicle's depot_node
4. Road availability  – no closed edge appears in any route's node_sequence
5. Connectivity       – every consecutive node pair in node_sequence must be a
                        real (existing) edge in the graph

Design notes
------------
- The checker is *pure*: it reads the solution and problem, never mutates them.
- Each violation is recorded as a human-readable string for debugging.
- ``compute_fitness`` in objective.py calls this internally and adds a
  penalty per violation, so QPSO can guide infeasible particles toward the
  feasible region without a hard rejection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.graph.model import TransportGraph
from app.vrp.models import VRPProblem, VRPSolution


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class FeasibilityResult:
    """
    Outcome of ``check_feasibility``.

    Attributes
    ----------
    is_feasible : bool       – True iff all five constraints pass
    violations  : list[str]  – one descriptive string per violation found
                               (empty when is_feasible is True)
    """

    is_feasible: bool
    violations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------

def check_feasibility(
    solution: VRPSolution,
    problem: VRPProblem,
) -> FeasibilityResult:
    """
    Evaluate all five hard constraints on *solution* given *problem*.

    Parameters
    ----------
    solution : VRPSolution  – candidate solution to evaluate
    problem  : VRPProblem   – the VRP instance being solved

    Returns
    -------
    FeasibilityResult with is_feasible=True and an empty violations list when
    all constraints are satisfied, or is_feasible=False with a populated
    violations list describing every detected violation.
    """
    violations: list[str] = []

    # Build a lookup from vehicle_id → Vehicle for fast access
    vehicle_by_id = {v.vehicle_id: v for v in problem.vehicles}
    customer_by_id = problem.customer_by_id
    tg = problem.graph

    # ------------------------------------------------------------------
    # Constraint 2: Customer coverage
    # Every required customer must appear in exactly one route.
    # We check this first so later per-route checks can reference served sets.
    # ------------------------------------------------------------------
    served_customers: list[Any] = []
    for route in solution.routes:
        served_customers.extend(route.visit_order)

    served_set = set(served_customers)
    required_set = problem.customer_ids

    missing = required_set - served_set
    if missing:
        violations.append(
            f"Customer coverage: {len(missing)} customer(s) not served – "
            f"ids: {sorted(missing)}"
        )

    duplicates = [cid for cid in served_customers if served_customers.count(cid) > 1]
    duplicate_set = set(duplicates)
    if duplicate_set:
        violations.append(
            f"Customer coverage: {len(duplicate_set)} customer(s) served more "
            f"than once – ids: {sorted(duplicate_set)}"
        )

    # ------------------------------------------------------------------
    # Per-route checks
    # ------------------------------------------------------------------
    for route in solution.routes:
        vid = route.vehicle_id
        vehicle = vehicle_by_id.get(vid)
        if vehicle is None:
            violations.append(
                f"Route for vehicle {vid!r}: vehicle not found in problem fleet."
            )
            continue

        seq = route.node_sequence

        # ── Constraint 3: Depot constraint ──────────────────────────────
        if len(seq) < 2:
            violations.append(
                f"Vehicle {vid!r}: node_sequence has fewer than 2 nodes "
                f"(must start and end at depot)."
            )
        else:
            if seq[0] != vehicle.depot_node:
                violations.append(
                    f"Vehicle {vid!r}: route does not start at depot "
                    f"{vehicle.depot_node!r} – starts at {seq[0]!r}."
                )
            if seq[-1] != vehicle.depot_node:
                violations.append(
                    f"Vehicle {vid!r}: route does not end at depot "
                    f"{vehicle.depot_node!r} – ends at {seq[-1]!r}."
                )

        # ── Constraint 1: Vehicle capacity ──────────────────────────────
        total_demand = sum(
            customer_by_id[cid].demand
            for cid in route.visit_order
            if cid in customer_by_id
        )
        if total_demand > vehicle.capacity:
            violations.append(
                f"Vehicle {vid!r}: capacity exceeded – demand {total_demand} "
                f"> capacity {vehicle.capacity}."
            )

        # ── Constraints 4 & 5: Road availability + connectivity ─────────
        g = tg.graph
        for i, (u, v) in enumerate(zip(seq[:-1], seq[1:])):
            # Constraint 5: edge must exist
            if not g.has_edge(u, v):
                violations.append(
                    f"Vehicle {vid!r}: no edge from {u!r} to {v!r} "
                    f"at sequence position {i} (disconnected/invalid route)."
                )
                continue  # skip road_status check for non-existent edge

            # Constraint 4: edge must not be closed
            if g[u][v].get("road_status") == TransportGraph.CLOSED:
                violations.append(
                    f"Vehicle {vid!r}: closed road used between "
                    f"{u!r} and {v!r} at sequence position {i}."
                )

    is_feasible = len(violations) == 0
    return FeasibilityResult(is_feasible=is_feasible, violations=violations)
