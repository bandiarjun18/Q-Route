#!/usr/bin/env python
"""
experiments/benchmarks/run_benchmark.py – CLI entry point for M11 Unified Benchmark Runner.

Usage examples:
    python -m experiments.benchmarks.run_benchmark
    python -m experiments.benchmarks.run_benchmark --instances small_seed_42 --algorithms QPSO,Classical_PSO --trials 2
    python -m experiments.benchmarks.run_benchmark --instances all --trials 5 --iterations 100
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root and backend/ are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from experiments.benchmarks.runner import BenchmarkRunner, BenchmarkSuiteConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Q-Route M11 Unified Multi-Algorithm Benchmark Suite."
    )
    parser.add_argument(
        "--instances",
        type=str,
        default="small_seed_42",
        help="Comma-separated list of instance IDs (e.g. 'small_seed_42,medium_seed_42') or 'all'.",
    )
    parser.add_argument(
        "--algorithms",
        type=str,
        default="QPSO,Classical_PSO,Genetic_Algorithm,Simulated_Annealing",
        help="Comma-separated list of algorithms to evaluate.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="Number of independent random seed trials per algorithm/instance (default: 3).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Maximum iterations or generations per trial (default: 100).",
    )
    parser.add_argument(
        "--particles",
        type=int,
        default=20,
        help="Swarm / population size where applicable (default: 20).",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        help="Optional wall-clock execution budget in seconds per trial.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed (default: 42).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="results/benchmarks",
        help="Output directory for CSV and JSON result artifacts.",
    )
    parser.add_argument(
        "--instances-dir",
        type=str,
        default="data/benchmarks",
        help="Directory containing benchmark instance JSON files.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Parse instances
    if args.instances.lower() == "all":
        # Look up all instance JSON files in instances_dir
        inst_path = Path(args.instances_dir)
        if inst_path.exists():
            inst_files = sorted(inst_path.glob("*.json"))
            instance_list = [f.stem for f in inst_files if f.name != "manifest.json"]
        else:
            instance_list = ["small_seed_42", "medium_seed_42", "large_seed_42", "stress_seed_42"]
    else:
        instance_list = [x.strip() for x in args.instances.split(",") if x.strip()]

    # Parse algorithms
    algo_list = [x.strip() for x in args.algorithms.split(",") if x.strip()]

    config = BenchmarkSuiteConfig(
        instances=instance_list,
        algorithms=algo_list,
        n_trials=args.trials,
        base_seed=args.seed,
        max_iterations=args.iterations,
        population_size=args.particles,
        time_budget_seconds=args.time_budget,
        output_dir=args.out_dir,
        instances_dir=args.instances_dir,
    )

    runner = BenchmarkRunner(config)
    summary = runner.run(verbose=True)

    if summary["error_runs"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
