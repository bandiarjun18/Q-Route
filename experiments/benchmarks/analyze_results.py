#!/usr/bin/env python
"""
experiments/benchmarks/analyze_results.py – CLI entry point for M11 benchmark analysis & visualization.

Usage:
    python -m experiments.benchmarks.analyze_results
    python -m experiments.benchmarks.analyze_results --results-dir results/benchmarks --out-dir results/analysis --figures-dir results/figures
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

from experiments.benchmarks.analysis import (
    generate_analysis_tables,
    generate_scientific_figures,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze M11 benchmark results and generate tables & figures."
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/benchmarks",
        help="Path to directory containing benchmark_results.csv and JSON artifacts.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="results/analysis",
        help="Path to output directory for tabular CSV/JSON summaries and markdown report.",
    )
    parser.add_argument(
        "--figures-dir",
        type=str,
        default="results/figures",
        help="Path to output directory for scientific figures (SVG/PNG).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    figures_dir = Path(args.figures_dir)

    print(f"\n=======================================================")
    print(f"  Q-Route M11 Benchmark Analysis & Visualization")
    print(f"=======================================================")
    print(f"  Source results: {results_dir}")
    print(f"  Analysis tables: {out_dir}")
    print(f"  Scientific figures: {figures_dir}")
    print(f"=======================================================\n")

    # Generate tables and report
    print("  [1/2] Computing statistical aggregates and generating tables...")
    table_files = generate_analysis_tables(results_dir, out_dir)
    for name, p in table_files.items():
        print(f"        [OK] {name:<22} -> {p}")

    # Generate figures
    print("\n  [2/2] Rendering scientific charts and figures...")
    fig_files = generate_scientific_figures(results_dir, figures_dir)
    for name, p in fig_files.items():
        print(f"        [OK] {name:<22} -> {p}")

    print(f"\n=======================================================")
    print(f"  Analysis Completed Successfully.")
    print(f"  Report generated at: {table_files.get('report')}")
    print(f"=======================================================\n")


if __name__ == "__main__":
    main()
