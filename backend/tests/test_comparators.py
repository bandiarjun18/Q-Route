"""
tests/test_comparators.py – Unit and integration tests for M11 comparator algorithms suite.

Verifies:
1. Classical PSO execution, convergence tracking, feasibility, reproducibility.
2. Genetic Algorithm execution, elitism, convergence tracking, feasibility, reproducibility.
3. Simulated Annealing execution, Metropolis cooling, convergence tracking, feasibility, reproducibility.
4. Exact Solver optimality on small instances (N <= 8) and proper exception rejection when N > 8.
5. Scientific parity: All returned solutions pass canonical check_feasibility and compute_fitness.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# Ensure repo root and backend are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.vrp.feasibility import check_feasibility
from app.vrp.generator import generate_vrp_instance
from app.vrp.objective import FitnessWeights, compute_fitness
from experiments.comparators import (
    ClassicalPSO,
    ClassicalPSOConfig,
    ComparatorResult,
    ExactSolver,
    GAConfig,
    GeneticAlgorithm,
    SAConfig,
    SimulatedAnnealing,
)


@pytest.fixture
def small_vrp():
    """Small reproducible 4-customer 2-vehicle VRP instance."""
    return generate_vrp_instance(
        n_vehicles=2,
        n_customers=4,
        n_nodes=10,
        n_depots=1,
        seed=42,
    )


@pytest.fixture
def large_vrp():
    """Instance with N=9 customers to test ExactSolver guard."""
    return generate_vrp_instance(
        n_vehicles=3,
        n_customers=9,
        n_nodes=20,
        n_depots=1,
        seed=42,
    )


class TestClassicalPSO:
    """Tests for Classical PSO comparator."""

    def test_run_classical_pso(self, small_vrp):
        cfg = ClassicalPSOConfig(n_particles=10, max_iterations=20, seed=123)
        solver = ClassicalPSO(small_vrp, cfg)
        result = solver.solve()

        assert isinstance(result, ComparatorResult)
        assert result.algorithm_name == "Classical_PSO"
        assert result.is_feasible is True
        assert not math.isinf(result.best_fitness)
        assert len(result.convergence_history) > 0
        assert result.runtime_seconds > 0
        assert result.iterations_completed == 20

        # Parity check with canonical objective
        direct_fit = compute_fitness(result.best_solution, small_vrp)
        assert abs(direct_fit - result.best_fitness) < 1e-6

        feas = check_feasibility(result.best_solution, small_vrp)
        assert feas.is_feasible is True

    def test_classical_pso_deterministic(self, small_vrp):
        cfg = ClassicalPSOConfig(n_particles=10, max_iterations=15, seed=42)
        r1 = ClassicalPSO(small_vrp, cfg).solve(seed=42)
        r2 = ClassicalPSO(small_vrp, cfg).solve(seed=42)

        assert abs(r1.best_fitness - r2.best_fitness) < 1e-9


class TestGeneticAlgorithm:
    """Tests for Genetic Algorithm comparator."""

    def test_run_ga(self, small_vrp):
        cfg = GAConfig(population_size=12, generations=20, seed=123)
        solver = GeneticAlgorithm(small_vrp, cfg)
        result = solver.solve()

        assert isinstance(result, ComparatorResult)
        assert result.algorithm_name == "Genetic_Algorithm"
        assert result.is_feasible is True
        assert not math.isinf(result.best_fitness)
        assert len(result.convergence_history) > 0
        assert result.runtime_seconds > 0
        assert result.iterations_completed == 20

        direct_fit = compute_fitness(result.best_solution, small_vrp)
        assert abs(direct_fit - result.best_fitness) < 1e-6

        feas = check_feasibility(result.best_solution, small_vrp)
        assert feas.is_feasible is True

    def test_ga_deterministic(self, small_vrp):
        cfg = GAConfig(population_size=10, generations=10, seed=42)
        r1 = GeneticAlgorithm(small_vrp, cfg).solve(seed=42)
        r2 = GeneticAlgorithm(small_vrp, cfg).solve(seed=42)

        assert abs(r1.best_fitness - r2.best_fitness) < 1e-9


class TestSimulatedAnnealing:
    """Tests for Simulated Annealing comparator."""

    def test_run_sa(self, small_vrp):
        cfg = SAConfig(
            initial_temperature=50.0,
            cooling_rate=0.9,
            steps_per_temperature=3,
            max_iterations=50,
            seed=123,
        )
        solver = SimulatedAnnealing(small_vrp, cfg)
        result = solver.solve()

        assert isinstance(result, ComparatorResult)
        assert result.algorithm_name == "Simulated_Annealing"
        assert result.is_feasible is True
        assert not math.isinf(result.best_fitness)
        assert len(result.convergence_history) > 0
        assert result.runtime_seconds > 0

        direct_fit = compute_fitness(result.best_solution, small_vrp)
        assert abs(direct_fit - result.best_fitness) < 1e-6

        feas = check_feasibility(result.best_solution, small_vrp)
        assert feas.is_feasible is True

    def test_sa_deterministic(self, small_vrp):
        cfg = SAConfig(max_iterations=30, seed=42)
        r1 = SimulatedAnnealing(small_vrp, cfg).solve(seed=42)
        r2 = SimulatedAnnealing(small_vrp, cfg).solve(seed=42)

        assert abs(r1.best_fitness - r2.best_fitness) < 1e-9


class TestExactSolver:
    """Tests for Exact / Exhaustive Solver."""

    def test_exact_solver_optimality(self, small_vrp):
        solver = ExactSolver(small_vrp)
        result = solver.solve()

        assert isinstance(result, ComparatorResult)
        assert result.algorithm_name == "Exact_Brute_Force"
        assert result.is_feasible is True
        assert not math.isinf(result.best_fitness)
        assert result.runtime_seconds > 0
        assert result.extra_telemetry["total_candidates_evaluated"] > 0

        feas = check_feasibility(result.best_solution, small_vrp)
        assert feas.is_feasible is True

        # Any heuristic on small_vrp cannot beat the exact solver (exact <= heuristic)
        pso_res = ClassicalPSO(small_vrp, ClassicalPSOConfig(n_particles=10, max_iterations=20, seed=42)).solve()
        assert result.best_fitness <= pso_res.best_fitness + 1e-6

    def test_exact_solver_guard_oversized(self, large_vrp):
        with pytest.raises(ValueError) as exc_info:
            ExactSolver(large_vrp)
        assert "restricted to small instances" in str(exc_info.value)
