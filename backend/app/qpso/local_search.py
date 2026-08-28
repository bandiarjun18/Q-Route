"""
app/qpso/local_search.py – 2-opt local search for individual VRP routes.

Public API
----------
two_opt(solution, problem, weights) → VRPSolution

Algorithm
---------
For each vehicle route with ≥ 2 assigned customers, all (i, j) reversal
pairs over ``visit_order`` are enumerated.  A reversal is accepted
immediately (first-improvement strategy) if:

  1. The new route has strictly lower weighted cost, AND
  2. The new node_sequence is fully valid — i.e. ``_route_cost`` returns a
     finite value (no missing/closed edges; Dijkstra found all segments).

After each accepted move the inner loop restarts for that route.  The
route is considered locally optimal when no improving (i, j) pair remains.

Safety guarantees
-----------------
- Never returns a route with higher cost than the input.
- Never returns an infeasible route (measured by edge validity) when the
  input route was already valid:
  * ``_build_node_sequence`` uses Dijkstra, which only traverses open edges.
  * If Dijkstra raises ``NetworkXNoPath`` for any segment, it falls back to
    a direct jump, which ``route_components`` detects as a missing edge and
    returns ``math.inf`` — causing the candidate to be rejected.
- Capacity constraints are unaffected: 2-opt only reorders the visit, not
  the set of assigned customers.
- Customer coverage is unaffected: same customers, different visit order.
- Does not modify base graph data.
- Does not redefine the fitness formula — uses ``route_components`` from
  ``app.vrp.objective`` for per-route cost evaluation.
- Input ``VRPSolution`` is never mutated.

Design notes
------------
2-opt operates on individual routes (not across routes).  Cross-route
exchanges are outside the scope of Milestone 5.

``_build_node_sequence`` is imported from ``representation`` to reuse the
canonical Dijkstra-chaining logic without duplication.
"""

from __future__ import annotations

import math
from typing import Any

from app.vrp.models import VRPProblem, VRPSolution, VehicleRoute
from app.vrp.objective import FitnessWeights, route_components

# Intentional internal-package import: reuse the canonical Dijkstra chainer.
from .representation import _build_node_sequence


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _route_cost(
    node_sequence: list,
    problem: VRPProblem,
    weights: FitnessWeights,
) -> float:
    """
    Compute the weighted scalar cost of a single route's node_sequence.

    Returns ``math.inf`` if any edge is missing or closed, which serves as
    the infeasibility proxy for road-availability and connectivity checks.

    Parameters
    ----------
    node_sequence : list           – ordered graph node ids for the route
    problem       : VRPProblem     – provides the graph
    weights       : FitnessWeights – cost weights

    Returns
    -------
    float – weighted cost; math.inf signals an invalid route.
    """
    t, d, c = route_components(problem.graph, node_sequence)
    if math.isinf(t) or math.isinf(d) or math.isinf(c):
        return math.inf
    return weights.wT * t + weights.wD * d + weights.wC * c


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def two_opt(
    solution: VRPSolution,
    problem: VRPProblem,
    weights: FitnessWeights | None = None,
) -> VRPSolution:
    """
    Apply per-route 2-opt local search to improve a VRP solution.

    Routes with fewer than 2 assigned customers are left unchanged.
    All other routes are optimised independently using first-improvement
    2-opt until no improving reversal exists.

    Parameters
    ----------
    solution : VRPSolution    – solution to refine (not mutated)
    problem  : VRPProblem     – the VRP instance
    weights  : FitnessWeights – cost weights; defaults to FitnessWeights()

    Returns
    -------
    A new VRPSolution with improved (or unchanged) routes.
    """
    if weights is None:
        weights = FitnessWeights()

    vehicle_by_id: dict[Any, Any] = {v.vehicle_id: v for v in problem.vehicles}
    customer_by_id = problem.customer_by_id

    new_routes: list[VehicleRoute] = []

    for route in solution.routes:
        vid = route.vehicle_id
        depot = route.depot_node

        visit_order = list(route.visit_order)
        n = len(visit_order)

        if n < 2:
            # Fewer than 2 customers: no reversal can change anything.
            new_routes.append(
                VehicleRoute(
                    vehicle_id=vid,
                    depot_node=depot,
                    visit_order=visit_order,
                    node_sequence=list(route.node_sequence),
                )
            )
            continue

        # Build node_sequence for the current visit_order and compute cost.
        current_customers = [
            customer_by_id[cid] for cid in visit_order if cid in customer_by_id
        ]
        current_seq = _build_node_sequence(depot, current_customers, problem.graph)
        current_cost = _route_cost(current_seq, problem, weights)

        # ── First-improvement 2-opt inner loop ──────────────────────────
        improved = True
        while improved:
            improved = False
            for i in range(n - 1):
                for j in range(i + 1, n):
                    # Reverse the segment visit_order[i : j+1].
                    candidate_order = (
                        visit_order[:i]
                        + list(reversed(visit_order[i : j + 1]))
                        + visit_order[j + 1 :]
                    )
                    candidate_customers = [
                        customer_by_id[cid]
                        for cid in candidate_order
                        if cid in customer_by_id
                    ]
                    candidate_seq = _build_node_sequence(
                        depot, candidate_customers, problem.graph
                    )
                    candidate_cost = _route_cost(candidate_seq, problem, weights)

                    # Accept only if strictly better and fully valid.
                    if candidate_cost < current_cost - 1e-10:
                        visit_order = candidate_order
                        current_seq = candidate_seq
                        current_cost = candidate_cost
                        improved = True
                        break  # First improvement — restart inner loop.

                if improved:
                    break

        new_routes.append(
            VehicleRoute(
                vehicle_id=vid,
                depot_node=depot,
                visit_order=visit_order,
                node_sequence=current_seq,
            )
        )

    return VRPSolution(routes=new_routes)
