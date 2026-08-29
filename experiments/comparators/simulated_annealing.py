"""
experiments/comparators/simulated_annealing.py – Simulated Annealing baseline for VRP.

Implements standard Simulated Annealing (Kirkpatrick et al., 1983) operating on
priority-key state representations for the Multi-Vehicle VRP.

Neighborhood moves:
- Random priority key perturbation
- Two-customer priority swap
- Subsequence inversion

Acceptance criterion:
- Metropolis condition: if ΔE < 0 accept, else accept with probability exp(-ΔE / T)
- Geometric cooling: T(k+1) = alpha * T(k)
- Evaluates candidates through standard decode -> repair -> 2-opt -> compute_fitness() pipeline.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.vrp.feasibility import check_feasibility
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights

from .common import ComparatorResult, evaluate_particle


@dataclass
class SAConfig:
    """Configuration parameters for Simulated Annealing."""

    initial_temperature: float = 100.0
    min_temperature: float = 1e-4
    cooling_rate: float = 0.96
    steps_per_temperature: int = 5
    max_iterations: int = 500
    perturbation_scale: float = 0.15
    time_budget_seconds: float | None = None
    seed: int = 42
    fitness_weights: FitnessWeights | None = None


class SimulatedAnnealing:
    """Simulated Annealing optimizer for VRP."""

    def __init__(self, problem: VRPProblem, config: SAConfig | None = None):
        self.problem = problem
        self.config = config or SAConfig()
        self.dim = len(problem.customers)

    def _generate_neighbor(
        self,
        current_state: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Generate a neighboring priority-key configuration."""
        d = self.dim
        neighbor = np.copy(current_state)
        move_type = rng.choice(["perturb", "swap", "invert"])

        if move_type == "swap" and d >= 2:
            i, j = rng.choice(d, size=2, replace=False)
            neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
        elif move_type == "invert" and d >= 3:
            i, j = sorted(rng.choice(d, size=2, replace=False))
            neighbor[i : j + 1] = neighbor[i : j + 1][::-1]
        else:
            # Perturb random subset of dimensions
            mask = rng.uniform(0.0, 1.0, size=d) < 0.4
            if not np.any(mask):
                mask[rng.choice(d)] = True
            noise = rng.normal(0.0, self.config.perturbation_scale, size=d)
            neighbor[mask] += noise[mask]

        return np.clip(neighbor, 0.0, 1.0)

    def solve(self, seed: int | None = None) -> ComparatorResult:
        """Run Simulated Annealing optimization."""
        cfg = self.config
        run_seed = seed if seed is not None else cfg.seed
        rng = np.random.default_rng(run_seed)
        weights = cfg.fitness_weights or FitnessWeights()

        start_time = time.perf_counter()

        # 1. Initialize state
        current_state = rng.uniform(0.0, 1.0, size=self.dim)
        current_solution, current_fitness = evaluate_particle(
            current_state, self.problem, weights
        )

        best_state = np.copy(current_state)
        best_fitness = current_fitness
        best_solution = current_solution

        temperature = cfg.initial_temperature
        convergence_history: dict[int, float] = {0: float(best_fitness)}

        iteration = 0
        while iteration < cfg.max_iterations and temperature > cfg.min_temperature:
            if cfg.time_budget_seconds is not None:
                if (time.perf_counter() - start_time) >= cfg.time_budget_seconds:
                    break

            for _ in range(cfg.steps_per_temperature):
                iteration += 1
                if iteration > cfg.max_iterations:
                    break

                # Generate neighbor
                neighbor_state = self._generate_neighbor(current_state, rng)
                neighbor_sol, neighbor_fit = evaluate_particle(
                    neighbor_state, self.problem, weights
                )

                # Metropolis acceptance criterion
                delta = neighbor_fit - current_fitness
                if delta < 0:
                    accept = True
                else:
                    prob = math.exp(-delta / max(temperature, 1e-12))
                    accept = rng.uniform(0.0, 1.0) < prob

                if accept:
                    current_state = neighbor_state
                    current_fitness = neighbor_fit
                    current_solution = neighbor_sol

                    if current_fitness < best_fitness:
                        best_fitness = current_fitness
                        best_state = np.copy(current_state)
                        best_solution = current_solution

                convergence_history[iteration] = float(best_fitness)

            # Cool down
            temperature *= cfg.cooling_rate

        elapsed = time.perf_counter() - start_time

        assert best_solution is not None
        feasibility = check_feasibility(best_solution, self.problem)

        return ComparatorResult(
            algorithm_name="Simulated_Annealing",
            best_solution=best_solution,
            best_fitness=float(best_fitness),
            convergence_history=convergence_history,
            runtime_seconds=elapsed,
            is_feasible=feasibility.is_feasible,
            seed=run_seed,
            iterations_completed=iteration,
            extra_telemetry={
                "initial_temperature": cfg.initial_temperature,
                "final_temperature": temperature,
                "cooling_rate": cfg.cooling_rate,
                "violations": feasibility.violations,
            },
        )
