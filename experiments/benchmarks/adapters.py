"""
experiments/benchmarks/adapters.py – Standardized algorithm adapters for the M11 benchmark runner.

Wraps each optimization algorithm (QPSO, Classical PSO, GA, SA, Exact) in a uniform execution
interface that captures metrics, enforces scientific parity, and isolates execution errors.
"""

from __future__ import annotations

import datetime
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.vrp.feasibility import check_feasibility
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness, route_components
from experiments.comparators import (
    ClassicalPSO,
    ClassicalPSOConfig,
    ExactSolver,
    GAConfig,
    GeneticAlgorithm,
    SAConfig,
    SimulatedAnnealing,
)


@dataclass
class BenchmarkTrialResult:
    """
    Standardized result for a single algorithm trial on a benchmark instance.
    """

    algorithm: str
    instance_id: str
    trial_id: int
    random_seed: int
    status: str  # SUCCESS, TIMEOUT, ERROR, INFEASIBLE
    runtime_seconds: float
    iterations_completed: int
    best_objective: float | None
    is_feasible: bool
    total_distance: float | None = None
    total_travel_time: float | None = None
    total_congestion: float | None = None
    constraint_violations: list[str] = field(default_factory=list)
    error_message: str | None = None
    error_type: str | None = None
    convergence_history: dict[int, float] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert trial result to dictionary."""
        return asdict(self)

    def to_csv_row(self) -> dict[str, Any]:
        """Convert trial result to a flat dictionary row for CSV output."""
        return {
            "algorithm": self.algorithm,
            "instance_id": self.instance_id,
            "trial_id": self.trial_id,
            "random_seed": self.random_seed,
            "status": self.status,
            "runtime_seconds": round(self.runtime_seconds, 6),
            "iterations_completed": self.iterations_completed,
            "best_objective": round(self.best_objective, 4) if self.best_objective is not None else None,
            "is_feasible": self.is_feasible,
            "total_distance": round(self.total_distance, 4) if self.total_distance is not None else None,
            "total_travel_time": round(self.total_travel_time, 4) if self.total_travel_time is not None else None,
            "total_congestion": round(self.total_congestion, 4) if self.total_congestion is not None else None,
            "n_violations": len(self.constraint_violations),
            "error_type": self.error_type or "",
            "timestamp": self.timestamp,
        }


def extract_solution_metrics(
    solution: VRPSolution | None,
    problem: VRPProblem,
) -> tuple[float | None, float | None, float | None]:
    """
    Extract unweighted total travel time, distance, and congestion from a solution.
    """
    if solution is None:
        return None, None, None

    agg_time = 0.0
    agg_dist = 0.0
    agg_cong = 0.0

    for route in solution.routes:
        t, d, c = route_components(problem.graph, route.node_sequence)
        if math.isinf(t) or math.isinf(d) or math.isinf(c):
            return math.inf, math.inf, math.inf
        agg_time += t
        agg_dist += d
        agg_cong += c

    return agg_time, agg_dist, agg_cong


class AlgorithmAdapter:
    """
    Base class and registry for benchmark algorithm execution.
    """

    SUPPORTED_ALGORITHMS = ["QPSO", "Classical_PSO", "Genetic_Algorithm", "Simulated_Annealing", "Exact_Brute_Force"]

    @classmethod
    def run_trial(
        cls,
        algorithm_name: str,
        problem: VRPProblem,
        instance_id: str,
        trial_id: int,
        seed: int,
        max_iterations: int = 100,
        population_size: int = 20,
        time_budget_seconds: float | None = None,
        fitness_weights: FitnessWeights | None = None,
    ) -> BenchmarkTrialResult:
        """
        Execute a single algorithm trial under isolated error handling.
        """
        weights = fitness_weights or FitnessWeights()
        start_time = time.perf_counter()

        try:
            algo_key = algorithm_name.upper().replace("-", "_").replace(" ", "_")

            if algo_key in ["QPSO"]:
                cfg = QPSOConfig(
                    n_particles=population_size,
                    max_iterations=max_iterations,
                    time_budget_seconds=time_budget_seconds,
                    seed=seed,
                    fitness_weights=weights,
                )
                qpso_res = QPSOOptimizer(problem, cfg).run()
                elapsed = time.perf_counter() - start_time

                sol = qpso_res.best_solution
                fit = float(qpso_res.best_fitness)
                history = qpso_res.convergence_history
                iters = qpso_res.n_iterations_run
                meta = {"stopped_early": qpso_res.stopped_early}

            elif algo_key in ["CLASSICAL_PSO", "PSO"]:
                pso_cfg = ClassicalPSOConfig(
                    n_particles=population_size,
                    max_iterations=max_iterations,
                    time_budget_seconds=time_budget_seconds,
                    seed=seed,
                    fitness_weights=weights,
                )
                res = ClassicalPSO(problem, pso_cfg).solve(seed=seed)
                elapsed = res.runtime_seconds
                sol = res.best_solution
                fit = res.best_fitness
                history = res.convergence_history
                iters = res.iterations_completed
                meta = res.extra_telemetry

            elif algo_key in ["GENETIC_ALGORITHM", "GA"]:
                ga_cfg = GAConfig(
                    population_size=population_size,
                    generations=max_iterations,
                    time_budget_seconds=time_budget_seconds,
                    seed=seed,
                    fitness_weights=weights,
                )
                res = GeneticAlgorithm(problem, ga_cfg).solve(seed=seed)
                elapsed = res.runtime_seconds
                sol = res.best_solution
                fit = res.best_fitness
                history = res.convergence_history
                iters = res.iterations_completed
                meta = res.extra_telemetry

            elif algo_key in ["SIMULATED_ANNEALING", "SA"]:
                sa_cfg = SAConfig(
                    max_iterations=max_iterations,
                    time_budget_seconds=time_budget_seconds,
                    seed=seed,
                    fitness_weights=weights,
                )
                res = SimulatedAnnealing(problem, sa_cfg).solve(seed=seed)
                elapsed = res.runtime_seconds
                sol = res.best_solution
                fit = res.best_fitness
                history = res.convergence_history
                iters = res.iterations_completed
                meta = res.extra_telemetry

            elif algo_key in ["EXACT", "EXACT_BRUTE_FORCE", "EXACT_SOLVER"]:
                solver = ExactSolver(problem, fitness_weights=weights)
                res = solver.solve(seed=seed)
                elapsed = res.runtime_seconds
                sol = res.best_solution
                fit = res.best_fitness
                history = res.convergence_history
                iters = res.iterations_completed
                meta = res.extra_telemetry

            else:
                raise ValueError(
                    f"Unknown algorithm: {algorithm_name}. Supported: {cls.SUPPORTED_ALGORITHMS}"
                )

            # Check feasibility and extract metrics
            feas = check_feasibility(sol, problem)
            time_comp, dist_comp, cong_comp = extract_solution_metrics(sol, problem)

            status = "SUCCESS" if feas.is_feasible else "INFEASIBLE"

            return BenchmarkTrialResult(
                algorithm=algorithm_name,
                instance_id=instance_id,
                trial_id=trial_id,
                random_seed=seed,
                status=status,
                runtime_seconds=elapsed,
                iterations_completed=iters,
                best_objective=fit,
                is_feasible=feas.is_feasible,
                total_distance=dist_comp,
                total_travel_time=time_comp,
                total_congestion=cong_comp,
                constraint_violations=feas.violations,
                convergence_history=history,
                extra_metadata=meta,
            )

        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start_time
            return BenchmarkTrialResult(
                algorithm=algorithm_name,
                instance_id=instance_id,
                trial_id=trial_id,
                random_seed=seed,
                status="ERROR",
                runtime_seconds=elapsed,
                iterations_completed=0,
                best_objective=None,
                is_feasible=False,
                error_message=str(exc),
                error_type=exc.__class__.__name__,
            )
