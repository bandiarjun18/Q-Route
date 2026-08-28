"""
app/vrp/objective.py – Shared fitness / objective function for Q-Route VRP.

THIS IS THE SINGLE SOURCE OF TRUTH FOR THE FITNESS FORMULA.
All other modules (QPSO, 2-opt, evaluation scripts) must import from here.
Do NOT redefine this formula elsewhere.

Public API
----------
FitnessWeights                           – configurable weight dataclass
route_components(tg, node_sequence)      – (travel_time, distance, congestion)
compute_fitness(solution, problem, weights) → float

Formula
-------
    Fitness = wT * TotalTravelTime
            + wD * TotalDistance
            + wC * TotalCongestion
            + penalty_per_violation * n_violations

where, for each edge (u → v) in a vehicle's node_sequence:
    effective_travel_time  = base_travel_time * congestion_factor
    edge_congestion_penalty = congestion_factor - 1.0
    TotalTravelTime  = Σ effective_travel_time  over all edges in all routes
    TotalDistance    = Σ distance               over all edges in all routes
    TotalCongestion  = Σ edge_congestion_penalty over all edges in all routes

A closed or missing edge contributes math.inf to its respective component so
that infeasible solutions (road-availability / connectivity violations) always
score higher (worse) than any feasible solution — even before the penalty term.

Design notes
------------
- ``compute_fitness`` calls ``check_feasibility`` internally; callers do NOT
  need to run the checker separately before asking for a fitness value.
- The penalty term is additive (soft): infeasible solutions are not outright
  rejected but are scored higher than feasible ones, which guides QPSO
  particles toward the feasible region during optimisation.
- Weights default to the project-standard values (wT=1.0, wD=0.5, wC=0.3)
  matching the per-edge cost formula in app.graph.model.WeightConfig.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.graph.model import TransportGraph
from app.vrp.models import VRPProblem, VRPSolution


# ---------------------------------------------------------------------------
# Weight / penalty configuration
# ---------------------------------------------------------------------------

@dataclass
class FitnessWeights:
    """
    Configurable weights for the VRP fitness function.

    Attributes
    ----------
    wT                   : float – weight for total effective travel time
    wD                   : float – weight for total distance
    wC                   : float – weight for total congestion penalty
    penalty_per_violation: float – added to fitness for each hard-constraint
                                   violation (soft-penalty approach)

    Defaults match the project-standard edge-cost formula in WeightConfig.
    """

    wT: float = 1.0
    wD: float = 0.5
    wC: float = 0.3
    penalty_per_violation: float = 1_000.0

    def __post_init__(self) -> None:
        if self.penalty_per_violation < 0:
            raise ValueError(
                "penalty_per_violation must be >= 0, "
                f"got {self.penalty_per_violation}"
            )


# ---------------------------------------------------------------------------
# Per-route component extraction
# ---------------------------------------------------------------------------

def route_components(
    tg: TransportGraph,
    node_sequence: list,
) -> tuple[float, float, float]:
    """
    Compute the raw (unweighted) cost components for one vehicle's route.

    Parameters
    ----------
    tg            : TransportGraph – the road network
    node_sequence : list           – ordered graph node ids including depot
                                     at start and end

    Returns
    -------
    (travel_time, distance, congestion) : tuple[float, float, float]

    Each value is the sum over all edges in the sequence.
    A closed or missing edge makes the corresponding component ``math.inf``.
    A sequence of length < 2 (degenerate) returns (0.0, 0.0, 0.0).
    """
    if len(node_sequence) < 2:
        return 0.0, 0.0, 0.0

    g = tg.graph
    total_time = 0.0
    total_dist = 0.0
    total_cong = 0.0

    for u, v in zip(node_sequence[:-1], node_sequence[1:]):
        if not g.has_edge(u, v):
            return math.inf, math.inf, math.inf

        data = g[u][v]
        if data.get("road_status") == TransportGraph.CLOSED:
            return math.inf, math.inf, math.inf

        cf = data["congestion_factor"]
        total_time += data["base_travel_time"] * cf
        total_dist += data["distance"]
        total_cong += cf - 1.0

    return total_time, total_dist, total_cong


# ---------------------------------------------------------------------------
# Full solution fitness
# ---------------------------------------------------------------------------

def compute_fitness(
    solution: VRPSolution,
    problem: VRPProblem,
    weights: FitnessWeights | None = None,
) -> float:
    """
    Compute the scalar fitness value for a VRP solution.

    This is the *only* place in Q-Route where the fitness formula is defined.
    QPSO and 2-opt must import and call this function — never reimplement it.

    Formula
    -------
        Fitness = wT * TotalTravelTime
                + wD * TotalDistance
                + wC * TotalCongestion
                + penalty_per_violation * n_violations

    Parameters
    ----------
    solution : VRPSolution
    problem  : VRPProblem
    weights  : FitnessWeights  – defaults to FitnessWeights() if None

    Returns
    -------
    float – lower is better; math.inf when a route contains a missing/closed
            edge (road-availability or connectivity violation).
    """
    # Lazy import to avoid a circular-import between objective ↔ feasibility
    from app.vrp.feasibility import check_feasibility  # noqa: PLC0415

    if weights is None:
        weights = FitnessWeights()

    # ── Route cost components ────────────────────────────────────────────
    agg_time = 0.0
    agg_dist = 0.0
    agg_cong = 0.0

    for route in solution.routes:
        t, d, c = route_components(problem.graph, route.node_sequence)
        # If any component is inf, the whole solution is inf-cost
        if math.isinf(t) or math.isinf(d) or math.isinf(c):
            return math.inf
        agg_time += t
        agg_dist += d
        agg_cong += c

    base_cost = (
        weights.wT * agg_time
        + weights.wD * agg_dist
        + weights.wC * agg_cong
    )

    # ── Feasibility penalty ──────────────────────────────────────────────
    result = check_feasibility(solution, problem)
    n_violations = len(result.violations)
    penalty = weights.penalty_per_violation * n_violations

    return base_cost + penalty
