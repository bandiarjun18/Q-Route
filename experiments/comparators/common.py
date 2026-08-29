"""
experiments/comparators/common.py – Shared protocols and utilities for M11 comparators.

Every comparator in the M11 suite uses these common utilities to guarantee:
1. Scientific parity: Identical decoding, repair heuristics, and objective evaluation.
2. Canonical fitness: Uses app.vrp.objective.compute_fitness exclusively.
3. Canonical feasibility: Uses app.vrp.feasibility.check_feasibility exclusively.
4. Consistent result structures across all benchmark runs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.qpso.local_search import two_opt
from app.qpso.repair import repair_capacity
from app.qpso.representation import decode, encode_random
from app.vrp.feasibility import check_feasibility
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness


@dataclass
class ComparatorResult:
    """
    Standard output container returned by all M11 comparator solvers.

    Attributes
    ----------
    algorithm_name       : str – Identifier for the algorithm (e.g. 'Classical_PSO', 'GA', 'SA', 'Exact')
    best_solution        : VRPSolution – Best candidate solution found
    best_fitness         : float – Objective value of best_solution
    convergence_history  : dict[int, float] – Map of iteration/step index -> best fitness so far
    runtime_seconds      : float – High-resolution CPU wall-clock execution time
    is_feasible          : bool – True iff best_solution satisfies all 5 hard constraints
    seed                 : int – Random seed used for the run
    iterations_completed : int – Total iterations or generations run
    extra_telemetry      : dict[str, Any] – Optional algorithm-specific metadata
    """

    algorithm_name: str
    best_solution: VRPSolution
    best_fitness: float
    convergence_history: dict[int, float]
    runtime_seconds: float
    is_feasible: bool
    seed: int
    iterations_completed: int
    extra_telemetry: dict[str, Any] = field(default_factory=dict)


def evaluate_particle(
    keys: np.ndarray,
    problem: VRPProblem,
    weights: FitnessWeights | None = None,
    use_repair: bool = True,
    use_2opt: bool = True,
) -> tuple[VRPSolution, float]:
    """
    Standard evaluation pipeline for priority-key candidate representations.

    Pipeline:
        keys -> decode() -> repair_capacity() -> two_opt() -> compute_fitness()

    Parameters
    ----------
    keys       : np.ndarray – Real-valued priority key vector in [0, 1]^N
    problem    : VRPProblem – VRP problem instance
    weights    : FitnessWeights | None – Objective weights (default standard)
    use_repair : bool – Whether to apply deterministic capacity repair
    use_2opt   : bool – Whether to apply 2-opt intra-route improvement

    Returns
    -------
    (solution, fitness) : tuple[VRPSolution, float]
    """
    sol = decode(keys, problem)
    if use_repair:
        sol = repair_capacity(sol, problem)
    if use_2opt:
        sol = two_opt(sol, problem, weights)

    fit = compute_fitness(sol, problem, weights)
    return sol, fit
