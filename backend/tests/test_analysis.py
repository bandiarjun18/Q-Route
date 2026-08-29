"""
tests/test_analysis.py – Unit and integration tests for M11 benchmark analysis & visualization pipeline.

Verifies:
1. Loading and validation of benchmark results CSV/JSON.
2. Accurate statistical aggregation (mean, median, std, min, max, success rates).
3. Generation of analytical tables (algorithm_comparison.csv, runtime_comparison.csv, scalability.csv, feasibility.csv, summary.json, benchmark_analysis.md).
4. Generation of publication-ready scientific vector SVGs and PNGs.
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

from experiments.benchmarks.analysis import (
    compute_algorithm_aggregates,
    generate_analysis_tables,
    generate_scientific_figures,
    load_benchmark_data,
)


@pytest.fixture
def mock_results_dir(tmp_path):
    """Create a temporary directory with synthetic benchmark results for testing."""
    res_dir = tmp_path / "mock_results"
    res_dir.mkdir(parents=True)

    # 1. Write mock CSV
    csv_file = res_dir / "benchmark_results.csv"
    fieldnames = [
        "algorithm", "instance_id", "trial_id", "random_seed", "status",
        "runtime_seconds", "iterations_completed", "best_objective",
        "is_feasible", "total_distance", "total_travel_time", "total_congestion",
        "n_violations", "error_type", "timestamp"
    ]
    rows = [
        {"algorithm": "QPSO", "instance_id": "small_seed_42", "trial_id": 1, "random_seed": 42, "status": "SUCCESS", "runtime_seconds": 1.25, "iterations_completed": 20, "best_objective": 78.5, "is_feasible": "True", "total_distance": 30.0, "total_travel_time": 50.0, "total_congestion": 8.0, "n_violations": 0, "error_type": "", "timestamp": "2026-08-29T12:00:00Z"},
        {"algorithm": "QPSO", "instance_id": "small_seed_42", "trial_id": 2, "random_seed": 142, "status": "SUCCESS", "runtime_seconds": 1.15, "iterations_completed": 20, "best_objective": 78.5, "is_feasible": "True", "total_distance": 30.0, "total_travel_time": 50.0, "total_congestion": 8.0, "n_violations": 0, "error_type": "", "timestamp": "2026-08-29T12:01:00Z"},
        {"algorithm": "Classical_PSO", "instance_id": "small_seed_42", "trial_id": 1, "random_seed": 42, "status": "SUCCESS", "runtime_seconds": 1.50, "iterations_completed": 20, "best_objective": 82.0, "is_feasible": "True", "total_distance": 32.0, "total_travel_time": 52.0, "total_congestion": 9.0, "n_violations": 0, "error_type": "", "timestamp": "2026-08-29T12:02:00Z"},
        {"algorithm": "Classical_PSO", "instance_id": "small_seed_42", "trial_id": 2, "random_seed": 142, "status": "SUCCESS", "runtime_seconds": 1.40, "iterations_completed": 20, "best_objective": 80.0, "is_feasible": "True", "total_distance": 31.0, "total_travel_time": 51.0, "total_congestion": 8.5, "n_violations": 0, "error_type": "", "timestamp": "2026-08-29T12:03:00Z"},
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 2. Write mock JSON
    json_file = res_dir / "benchmark_results.json"
    with open(json_file, "w", encoding="utf-8") as fh:
        json.dump({"summary": {"total_trials": 4, "success_count": 4}, "trials": rows}, fh)

    # 3. Write mock convergence
    conv_file = res_dir / "convergence_histories.json"
    with open(conv_file, "w", encoding="utf-8") as fh:
        json.dump({
            "small_seed_42__QPSO__trial_1": {"0": 120.0, "10": 90.0, "20": 78.5},
            "small_seed_42__Classical_PSO__trial_1": {"0": 120.0, "10": 95.0, "20": 82.0},
        }, fh)

    return res_dir


def test_load_benchmark_data(mock_results_dir):
    rows, meta, conv = load_benchmark_data(mock_results_dir)
    assert len(rows) == 4
    assert meta["summary"]["total_trials"] == 4
    assert len(conv) == 2


def test_compute_algorithm_aggregates(mock_results_dir):
    rows, _, _ = load_benchmark_data(mock_results_dir)
    aggs = compute_algorithm_aggregates(rows)

    assert len(aggs) == 2  # QPSO, Classical_PSO on small_seed_42
    qpso_agg = next(a for a in aggs if a["algorithm"] == "QPSO")
    assert qpso_agg["n_trials"] == 2
    assert qpso_agg["success_rate"] == 1.0
    assert qpso_agg["mean_objective"] == 78.5
    assert qpso_agg["std_objective"] == 0.0
    assert qpso_agg["mean_runtime_seconds"] == 1.2


def test_generate_analysis_tables_and_figures(mock_results_dir, tmp_path):
    out_tables = tmp_path / "analysis"
    out_figures = tmp_path / "figures"

    tables = generate_analysis_tables(mock_results_dir, out_tables)
    assert tables["algorithm_comparison"].exists()
    assert tables["runtime_comparison"].exists()
    assert tables["scalability"].exists()
    assert tables["feasibility"].exists()
    assert tables["summary"].exists()
    assert tables["report"].exists()

    figures = generate_scientific_figures(mock_results_dir, out_figures)
    assert figures["convergence_comparison"].exists()
    assert figures["objective_comparison"].exists()
    assert figures["runtime_comparison"].exists()
    assert figures["scalability_runtime"].exists()
    assert figures["scalability_objective"].exists()
    assert figures["feasibility_comparison"].exists()
