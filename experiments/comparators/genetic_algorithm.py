"""
experiments/comparators/genetic_algorithm.py – Genetic Algorithm baseline for VRP.

Implements a standard Genetic Algorithm (GA) using priority-key chromosome encoding.

Genetic operators:
- Tournament Selection (size k)
- Arithmetic / Simulated Binary Crossover (SBX)
- Gaussian / Polynomial Mutation
- Elitism (preserves top elite chromosomes directly to the next generation)
- Standard decoding, capacity repair, 2-opt, and canonical compute_fitness()
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
class GAConfig:
    """Configuration parameters for Genetic Algorithm."""

    population_size: int = 30
    generations: int = 100
    tournament_size: int = 3
    crossover_prob: float = 0.85
    mutation_prob: float = 0.15
    mutation_scale: float = 0.1
    elite_count: int = 2
    time_budget_seconds: float | None = None
    seed: int = 42
    fitness_weights: FitnessWeights | None = None


class GeneticAlgorithm:
    """Genetic Algorithm optimizer for VRP."""

    def __init__(self, problem: VRPProblem, config: GAConfig | None = None):
        self.problem = problem
        self.config = config or GAConfig()
        self.dim = len(problem.customers)

    def _tournament_select(
        self,
        population: np.ndarray,
        fitnesses: np.ndarray,
        rng: np.random.Generator,
        k: int,
    ) -> np.ndarray:
        """Select one parent chromosome using tournament selection."""
        candidates = rng.choice(len(population), size=k, replace=False)
        best_idx = candidates[np.argmin(fitnesses[candidates])]
        return np.copy(population[best_idx])

    def solve(self, seed: int | None = None) -> ComparatorResult:
        """Run Genetic Algorithm optimization."""
        cfg = self.config
        run_seed = seed if seed is not None else cfg.seed
        rng = np.random.default_rng(run_seed)
        weights = cfg.fitness_weights or FitnessWeights()

        start_time = time.perf_counter()

        pop_size = cfg.population_size
        d = self.dim
        elite_count = min(cfg.elite_count, pop_size)

        # 1. Initialize population in [0, 1]
        population = rng.uniform(0.0, 1.0, size=(pop_size, d))
        fitnesses = np.full(pop_size, np.inf)
        solutions: list[VRPSolution | None] = [None] * pop_size

        gbest_fitness = np.inf
        gbest_solution: VRPSolution | None = None
        convergence_history: dict[int, float] = {}

        # Evaluate initial population
        for i in range(pop_size):
            sol, fit = evaluate_particle(population[i], self.problem, weights)
            fitnesses[i] = fit
            solutions[i] = sol
            if fit < gbest_fitness:
                gbest_fitness = fit
                gbest_solution = sol

        convergence_history[0] = float(gbest_fitness)

        # 2. Generational Evolution Loop
        completed_generations = 0
        for gen in range(1, cfg.generations + 1):
            if cfg.time_budget_seconds is not None:
                if (time.perf_counter() - start_time) >= cfg.time_budget_seconds:
                    break

            completed_generations = gen

            # Sort population by fitness for elitism
            sorted_indices = np.argsort(fitnesses)
            new_population = np.zeros_like(population)

            # Elitism: copy top individuals
            for e in range(elite_count):
                new_population[e] = np.copy(population[sorted_indices[e]])

            # Fill remaining population with crossover and mutation
            fill_idx = elite_count
            while fill_idx < pop_size:
                p1 = self._tournament_select(population, fitnesses, rng, cfg.tournament_size)
                p2 = self._tournament_select(population, fitnesses, rng, cfg.tournament_size)

                # Crossover
                if rng.uniform(0.0, 1.0) < cfg.crossover_prob:
                    # Simulated Binary Crossover (SBX) or Blend Alpha
                    alpha = rng.uniform(0.0, 1.0, size=d)
                    c1 = alpha * p1 + (1.0 - alpha) * p2
                    c2 = alpha * p2 + (1.0 - alpha) * p1
                else:
                    c1 = np.copy(p1)
                    c2 = np.copy(p2)

                # Mutation
                for child in (c1, c2):
                    if fill_idx < pop_size:
                        if rng.uniform(0.0, 1.0) < cfg.mutation_prob:
                            noise = rng.normal(0.0, cfg.mutation_scale, size=d)
                            child = np.clip(child + noise, 0.0, 1.0)
                        else:
                            child = np.clip(child, 0.0, 1.0)

                        new_population[fill_idx] = child
                        fill_idx += 1

            population = new_population

            # Evaluate new population
            for i in range(pop_size):
                sol, fit = evaluate_particle(population[i], self.problem, weights)
                fitnesses[i] = fit
                solutions[i] = sol
                if fit < gbest_fitness:
                    gbest_fitness = fit
                    gbest_solution = sol

            convergence_history[gen] = float(gbest_fitness)

        elapsed = time.perf_counter() - start_time

        assert gbest_solution is not None
        feasibility = check_feasibility(gbest_solution, self.problem)

        return ComparatorResult(
            algorithm_name="Genetic_Algorithm",
            best_solution=gbest_solution,
            best_fitness=float(gbest_fitness),
            convergence_history=convergence_history,
            runtime_seconds=elapsed,
            is_feasible=feasibility.is_feasible,
            seed=run_seed,
            iterations_completed=completed_generations,
            extra_telemetry={
                "population_size": cfg.population_size,
                "generations": cfg.generations,
                "crossover_prob": cfg.crossover_prob,
                "mutation_prob": cfg.mutation_prob,
                "violations": feasibility.violations,
            },
        )
