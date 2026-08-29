"""
experiments/benchmarks/runner.py – Unified benchmark execution engine and results exporter.

Executes controlled multi-trial benchmark sweeps over standardized VRP instances,
captures multi-metric telemetry, enforces failure isolation, and persists CSV/JSON artifacts.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.vrp.generator import load_vrp_json
from app.vrp.models import VRPProblem

from .adapters import AlgorithmAdapter, BenchmarkTrialResult
from .configurations import BENCHMARK_PRESETS, BenchmarkSize
from .instance_generator import generate_benchmark_instance


@dataclass
class BenchmarkSuiteConfig:
    """
    Complete configuration for a benchmark execution suite.
    """

    instances: list[str] = field(default_factory=lambda: ["small_seed_42"])
    algorithms: list[str] = field(
        default_factory=lambda: ["QPSO", "Classical_PSO", "Genetic_Algorithm", "Simulated_Annealing"]
    )
    n_trials: int = 3
    base_seed: int = 42
    max_iterations: int = 100
    population_size: int = 20
    time_budget_seconds: float | None = None
    output_dir: str = "results/benchmarks"
    instances_dir: str = "data/benchmarks"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkRunner:
    """
    Multi-algorithm, multi-trial benchmark execution engine.
    """

    def __init__(self, config: BenchmarkSuiteConfig | None = None):
        self.config = config or BenchmarkSuiteConfig()
        self.output_path = Path(self.config.output_dir)
        self.instances_path = Path(self.config.instances_dir)

    def load_instance(self, instance_id: str) -> tuple[VRPProblem, str]:
        """
        Load a benchmark instance from JSON or generate on-the-fly from presets.
        """
        json_file = self.instances_path / f"{instance_id}.json"
        if json_file.exists():
            return load_vrp_json(json_file), instance_id

        # Fallback: parse size from instance_id (e.g. "small_seed_42")
        parts = instance_id.split("_")
        size_str = parts[0].lower()
        seed = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 42

        for size_enum in BenchmarkSize:
            if size_enum.value == size_str:
                preset = BENCHMARK_PRESETS[size_enum]
                problem = generate_benchmark_instance(preset, seed=seed)
                return problem, instance_id

        # Default fallback to small preset
        preset = BENCHMARK_PRESETS[BenchmarkSize.SMALL]
        return generate_benchmark_instance(preset, seed=seed), instance_id

    def run(self, verbose: bool = True) -> dict[str, Any]:
        """
        Execute the complete benchmark suite across all configured instances, algorithms, and trials.
        """
        start_suite_time = time.perf_counter()
        self.output_path.mkdir(parents=True, exist_ok=True)

        results: list[BenchmarkTrialResult] = []
        convergence_map: dict[str, dict[int, float]] = {}

        total_trials_planned = len(self.config.instances) * len(self.config.algorithms) * self.config.n_trials
        current_trial_idx = 0

        if verbose:
            print(f"\n=======================================================")
            print(f"  Q-Route M11 Unified Benchmark Runner")
            print(f"=======================================================")
            print(f"  Instances ({len(self.config.instances)}): {', '.join(self.config.instances)}")
            print(f"  Algorithms ({len(self.config.algorithms)}): {', '.join(self.config.algorithms)}")
            print(f"  Trials per configuration: {self.config.n_trials}")
            print(f"  Total planned runs: {total_trials_planned}")
            print(f"=======================================================\n")

        for inst_name in self.config.instances:
            problem, inst_id = self.load_instance(inst_name)
            n_cust = len(problem.customers)

            for algo_name in self.config.algorithms:
                # Guard against running exact solver on large instances
                if algo_name.upper().startswith("EXACT") and n_cust > 8:
                    if verbose:
                        print(f"  [SKIPPED] {algo_name} on {inst_id} (N={n_cust} > 8)")
                    continue

                for trial_idx in range(1, self.config.n_trials + 1):
                    current_trial_idx += 1
                    seed = self.config.base_seed + (trial_idx - 1) * 100

                    if verbose:
                        print(
                            f"  [{current_trial_idx}/{total_trials_planned}] "
                            f"Running {algo_name:<19} on {inst_id:<16} (Trial {trial_idx}, Seed {seed})...",
                            end="",
                            flush=True,
                        )

                    trial_result = AlgorithmAdapter.run_trial(
                        algorithm_name=algo_name,
                        problem=problem,
                        instance_id=inst_id,
                        trial_id=trial_idx,
                        seed=seed,
                        max_iterations=self.config.max_iterations,
                        population_size=self.config.population_size,
                        time_budget_seconds=self.config.time_budget_seconds,
                    )

                    results.append(trial_result)

                    trial_key = f"{inst_id}__{algo_name}__trial_{trial_idx}"
                    convergence_map[trial_key] = trial_result.convergence_history

                    if verbose:
                        if trial_result.status == "SUCCESS":
                            fit_str = f"{trial_result.best_objective:.2f}" if trial_result.best_objective is not None else "N/A"
                            print(f" [OK] Fit: {fit_str:>8} | Time: {trial_result.runtime_seconds:.3f}s")
                        else:
                            print(f" [{trial_result.status}] {trial_result.error_type or 'Violations'}")

        total_suite_elapsed = time.perf_counter() - start_suite_time

        # Export results
        self._export_results(results, convergence_map, total_suite_elapsed)

        summary = {
            "total_runs": len(results),
            "successful_runs": sum(1 for r in results if r.status == "SUCCESS"),
            "infeasible_runs": sum(1 for r in results if r.status == "INFEASIBLE"),
            "error_runs": sum(1 for r in results if r.status == "ERROR"),
            "total_runtime_seconds": round(total_suite_elapsed, 4),
            "output_directory": str(self.output_path),
            "config": self.config.to_dict(),
        }

        if verbose:
            print(f"\n=======================================================")
            print(f"  Benchmark Suite Completed in {total_suite_elapsed:.2f}s")
            print(f"  Total Runs: {summary['total_runs']} | Success: {summary['successful_runs']} | Errors: {summary['error_runs']}")
            print(f"  Exported: {self.output_path / 'benchmark_results.csv'}")
            print(f"            {self.output_path / 'benchmark_results.json'}")
            print(f"            {self.output_path / 'convergence_histories.json'}")
            print(f"=======================================================\n")

        return summary

    def _export_results(
        self,
        results: list[BenchmarkTrialResult],
        convergence_map: dict[str, dict[int, float]],
        total_time: float,
    ) -> None:
        """
        Export tabular CSV, structured JSON, and convergence traces.
        """
        # 1. Export CSV
        csv_file = self.output_path / "benchmark_results.csv"
        csv_rows = [r.to_csv_row() for r in results]
        if csv_rows:
            fieldnames = list(csv_rows[0].keys())
            with open(csv_file, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)

        # 2. Export JSON
        json_file = self.output_path / "benchmark_results.json"
        json_payload = {
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_runtime_seconds": round(total_time, 4),
                "config": self.config.to_dict(),
            },
            "summary": {
                "total_trials": len(results),
                "success_count": sum(1 for r in results if r.status == "SUCCESS"),
                "infeasible_count": sum(1 for r in results if r.status == "INFEASIBLE"),
                "error_count": sum(1 for r in results if r.status == "ERROR"),
            },
            "trials": [r.to_dict() for r in results],
        }
        with open(json_file, "w", encoding="utf-8") as fh:
            json.dump(json_payload, fh, indent=2)

        # 3. Export Convergence Histories
        conv_file = self.output_path / "convergence_histories.json"
        with open(conv_file, "w", encoding="utf-8") as fh:
            json.dump(convergence_map, fh, indent=2)
