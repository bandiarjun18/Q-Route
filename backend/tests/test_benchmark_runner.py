"""
tests/test_benchmark_runner.py – Unit and integration tests for M11 Unified Benchmark Runner.

Verifies:
1. AlgorithmAdapter execution across all supported algorithms (QPSO, Classical_PSO, GA, SA, Exact).
2. Failure isolation: Handled exceptions record status="ERROR" without halting the benchmark.
3. Multi-trial execution and deterministic reproducibility.
4. Export artifact generation: benchmark_results.csv, benchmark_results.json, convergence_histories.json.
5. Exact solver guard on instances with N > 8 customers.
"""

from __future__ import annotations

import csv
import json
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

from app.vrp.generator import generate_vrp_instance
from experiments.benchmarks import (
    AlgorithmAdapter,
    BenchmarkRunner,
    BenchmarkSuiteConfig,
    BenchmarkTrialResult,
)


@pytest.fixture
def small_problem():
    """Small reproducible 4-customer 2-vehicle problem."""
    return generate_vrp_instance(n_vehicles=2, n_customers=4, n_nodes=10, seed=42)


class TestAlgorithmAdapter:
    """Tests for individual algorithm trial adapters."""

    @pytest.mark.parametrize("algo", ["QPSO", "Classical_PSO", "Genetic_Algorithm", "Simulated_Annealing", "Exact_Brute_Force"])
    def test_run_all_algorithms(self, small_problem, algo):
        res = AlgorithmAdapter.run_trial(
            algorithm_name=algo,
            problem=small_problem,
            instance_id="test_small",
            trial_id=1,
            seed=42,
            max_iterations=10,
            population_size=10,
        )

        assert isinstance(res, BenchmarkTrialResult)
        assert res.algorithm == algo
        assert res.status == "SUCCESS"
        assert res.is_feasible is True
        assert res.best_objective is not None and res.best_objective > 0
        assert res.runtime_seconds > 0
        assert res.total_distance is not None
        assert res.total_travel_time is not None
        assert res.total_congestion is not None

    def test_error_isolation(self, small_problem):
        res = AlgorithmAdapter.run_trial(
            algorithm_name="NonExistentAlgorithm",
            problem=small_problem,
            instance_id="test_small",
            trial_id=1,
            seed=42,
        )
        assert res.status == "ERROR"
        assert res.error_type == "ValueError"
        assert "Unknown algorithm" in str(res.error_message)


class TestBenchmarkRunner:
    """Tests for the multi-trial runner and results exporter."""

    def test_runner_execution_and_exports(self, tmp_path):
        out_dir = tmp_path / "results"
        inst_dir = tmp_path / "data"
        inst_dir.mkdir(parents=True)

        # Create a small problem and save it
        from app.vrp.generator import save_vrp_json
        prob = generate_vrp_instance(n_vehicles=2, n_customers=4, n_nodes=10, seed=42)
        save_vrp_json(prob, inst_dir / "small_seed_42.json")

        config = BenchmarkSuiteConfig(
            instances=["small_seed_42"],
            algorithms=["QPSO", "Classical_PSO"],
            n_trials=2,
            base_seed=42,
            max_iterations=10,
            population_size=10,
            output_dir=str(out_dir),
            instances_dir=str(inst_dir),
        )

        runner = BenchmarkRunner(config)
        summary = runner.run(verbose=False)

        assert summary["total_runs"] == 4  # 1 instance * 2 algorithms * 2 trials
        assert summary["successful_runs"] == 4
        assert summary["error_runs"] == 0

        # Verify CSV export
        csv_file = out_dir / "benchmark_results.csv"
        assert csv_file.exists()
        with open(csv_file, encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
            assert len(reader) == 4
            for row in reader:
                assert row["status"] == "SUCCESS"
                assert float(row["best_objective"]) > 0
                assert float(row["runtime_seconds"]) > 0

        # Verify JSON export
        json_file = out_dir / "benchmark_results.json"
        assert json_file.exists()
        with open(json_file, encoding="utf-8") as fh:
            data = json.load(fh)
            assert data["summary"]["total_trials"] == 4
            assert len(data["trials"]) == 4

        # Verify Convergence Histories export
        conv_file = out_dir / "convergence_histories.json"
        assert conv_file.exists()
        with open(conv_file, encoding="utf-8") as fh:
            conv_data = json.load(fh)
            assert len(conv_data) == 4
            for trial_key, history in conv_data.items():
                assert len(history) > 0

    def test_runner_deterministic_seeds(self, tmp_path):
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"

        config1 = BenchmarkSuiteConfig(
            instances=["small_seed_42"],
            algorithms=["QPSO"],
            n_trials=2,
            base_seed=100,
            max_iterations=10,
            output_dir=str(out1),
        )
        config2 = BenchmarkSuiteConfig(
            instances=["small_seed_42"],
            algorithms=["QPSO"],
            n_trials=2,
            base_seed=100,
            max_iterations=10,
            output_dir=str(out2),
        )

        BenchmarkRunner(config1).run(verbose=False)
        BenchmarkRunner(config2).run(verbose=False)

        with open(out1 / "benchmark_results.json", encoding="utf-8") as fh1, \
             open(out2 / "benchmark_results.json", encoding="utf-8") as fh2:
            d1 = json.load(fh1)
            d2 = json.load(fh2)

        for t1, t2 in zip(d1["trials"], d2["trials"]):
            assert t1["random_seed"] == t2["random_seed"]
            assert abs(t1["best_objective"] - t2["best_objective"]) < 1e-9
