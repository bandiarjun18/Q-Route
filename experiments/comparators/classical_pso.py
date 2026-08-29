"""
experiments/comparators/classical_pso.py – Classical Particle Swarm Optimization baseline.

Implements standard velocity-and-position PSO (Eberhart & Kennedy, 1995 / Clerc & Kennedy, 2002)
using priority-key encoding for the discrete Multi-Vehicle VRP.

Unlike QPSO (which uses quantum wave-function collapse and mean-best attractor),
Classical PSO maintains explicit particle velocities, inertia weight, and cognitive/social
acceleration coefficients:

    v_{id}(t+1) = w * v_{id}(t) + c1 * r1 * (pbest_{id} - x_{id}(t)) + c2 * r2 * (gbest_d - x_{id}(t))
    x_{id}(t+1) = x_{id}(t) + v_{id}(t+1)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.vrp.feasibility import check_feasibility
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights

from .common import ComparatorResult, evaluate_particle


@dataclass
class ClassicalPSOConfig:
    """Configuration parameters for Classical PSO."""

    n_particles: int = 20
    max_iterations: int = 100
    w: float = 0.7298          # Clerc constriction inertia weight
    c1: float = 1.49618        # Cognitive acceleration coefficient
    c2: float = 1.49618        # Social acceleration coefficient
    v_max: float = 0.2         # Maximum velocity clamp
    time_budget_seconds: float | None = None
    seed: int = 42
    fitness_weights: FitnessWeights | None = None


class ClassicalPSO:
    """Classical Particle Swarm Optimizer for VRP."""

    def __init__(self, problem: VRPProblem, config: ClassicalPSOConfig | None = None):
        self.problem = problem
        self.config = config or ClassicalPSOConfig()
        self.dim = len(problem.customers)

    def solve(self, seed: int | None = None) -> ComparatorResult:
        """Run Classical PSO optimization."""
        cfg = self.config
        run_seed = seed if seed is not None else cfg.seed
        rng = np.random.default_rng(run_seed)
        weights = cfg.fitness_weights or FitnessWeights()

        start_time = time.perf_counter()

        # 1. Swarm Initialization
        n = cfg.n_particles
        d = self.dim

        # Positions in [0, 1]
        positions = rng.uniform(0.0, 1.0, size=(n, d))
        # Velocities in [-v_max, v_max]
        velocities = rng.uniform(-cfg.v_max, cfg.v_max, size=(n, d))

        pbest_positions = np.copy(positions)
        pbest_fitnesses = np.full(n, np.inf)
        pbest_solutions: list[VRPSolution | None] = [None] * n

        gbest_position = np.copy(positions[0])
        gbest_fitness = np.inf
        gbest_solution: VRPSolution | None = None

        convergence_history: dict[int, float] = {}

        # Evaluate initial swarm
        for i in range(n):
            sol, fit = evaluate_particle(positions[i], self.problem, weights)
            pbest_positions[i] = np.copy(positions[i])
            pbest_fitnesses[i] = fit
            pbest_solutions[i] = sol

            if fit < gbest_fitness:
                gbest_fitness = fit
                gbest_position = np.copy(positions[i])
                gbest_solution = sol

        convergence_history[0] = float(gbest_fitness)

        # 2. Main Iteration Loop
        completed_iterations = 0
        for it in range(1, cfg.max_iterations + 1):
            if cfg.time_budget_seconds is not None:
                if (time.perf_counter() - start_time) >= cfg.time_budget_seconds:
                    break

            completed_iterations = it

            # Update particles
            r1 = rng.uniform(0.0, 1.0, size=(n, d))
            r2 = rng.uniform(0.0, 1.0, size=(n, d))

            velocities = (
                cfg.w * velocities
                + cfg.c1 * r1 * (pbest_positions - positions)
                + cfg.c2 * r2 * (gbest_position - positions)
            )

            # Clamp velocities
            velocities = np.clip(velocities, -cfg.v_max, cfg.v_max)

            # Update positions and clamp to [0, 1]
            positions = np.clip(positions + velocities, 0.0, 1.0)

            # Evaluate updated positions
            for i in range(n):
                sol, fit = evaluate_particle(positions[i], self.problem, weights)
                if fit < pbest_fitnesses[i]:
                    pbest_fitnesses[i] = fit
                    pbest_positions[i] = np.copy(positions[i])
                    pbest_solutions[i] = sol

                    if fit < gbest_fitness:
                        gbest_fitness = fit
                        gbest_position = np.copy(positions[i])
                        gbest_solution = sol

            convergence_history[it] = float(gbest_fitness)

        elapsed = time.perf_counter() - start_time

        assert gbest_solution is not None
        feasibility = check_feasibility(gbest_solution, self.problem)

        return ComparatorResult(
            algorithm_name="Classical_PSO",
            best_solution=gbest_solution,
            best_fitness=float(gbest_fitness),
            convergence_history=convergence_history,
            runtime_seconds=elapsed,
            is_feasible=feasibility.is_feasible,
            seed=run_seed,
            iterations_completed=completed_iterations,
            extra_telemetry={
                "n_particles": cfg.n_particles,
                "w": cfg.w,
                "c1": cfg.c1,
                "c2": cfg.c2,
                "violations": feasibility.violations,
            },
        )
