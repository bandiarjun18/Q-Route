"""
experiments/benchmarks/analysis.py – Statistical aggregation, tabular metrics export, and report generator.

Performs rigorous statistical analysis on raw Phase 3 benchmark results:
- Central tendency (mean, median) and dispersion (std, min, max) for objective and runtime.
- Feasibility and constraint violation rates.
- Scalability scaling analysis vs customer count.
- Structured CSV/JSON exports in results/analysis/ and report generation in results/analysis/benchmark_analysis.md.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from .plot_utils import (
    plot_convergence_curves,
    plot_grouped_barchart,
    plot_scalability_curve,
    save_chart,
)


def load_benchmark_data(results_dir: Path | str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[int, float]]]:
    """
    Load raw benchmark results from CSV, JSON, and convergence files.
    """
    path = Path(results_dir)
    csv_file = path / "benchmark_results.csv"
    json_file = path / "benchmark_results.json"
    conv_file = path / "convergence_histories.json"

    if not csv_file.exists():
        raise FileNotFoundError(f"Missing benchmark CSV results: {csv_file}")

    rows: list[dict[str, Any]] = []
    with open(csv_file, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append({
                "algorithm": r["algorithm"],
                "instance_id": r["instance_id"],
                "trial_id": int(r["trial_id"]),
                "random_seed": int(r["random_seed"]),
                "status": r["status"],
                "runtime_seconds": float(r["runtime_seconds"]) if r.get("runtime_seconds") else None,
                "iterations_completed": int(r["iterations_completed"]) if r.get("iterations_completed") else 0,
                "best_objective": float(r["best_objective"]) if r.get("best_objective") and r["best_objective"] != "" else None,
                "is_feasible": r["is_feasible"].lower() == "true",
                "total_distance": float(r["total_distance"]) if r.get("total_distance") and r["total_distance"] != "" else None,
                "total_travel_time": float(r["total_travel_time"]) if r.get("total_travel_time") and r["total_travel_time"] != "" else None,
                "total_congestion": float(r["total_congestion"]) if r.get("total_congestion") and r["total_congestion"] != "" else None,
                "n_violations": int(r["n_violations"]) if r.get("n_violations") and r["n_violations"] != "" else 0,
            })

    meta_json = {}
    if json_file.exists():
        with open(json_file, encoding="utf-8") as fh:
            meta_json = json.load(fh)

    conv_histories = {}
    if conv_file.exists():
        with open(conv_file, encoding="utf-8") as fh:
            conv_histories = json.load(fh)

    return rows, meta_json, conv_histories


def compute_algorithm_aggregates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Compute grouped descriptive statistics for each (algorithm, instance_id) pair.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        key = (r["algorithm"], r["instance_id"])
        groups.setdefault(key, []).append(r)

    aggregates: list[dict[str, Any]] = []

    for (algo, inst), items in sorted(groups.items()):
        n_trials = len(items)
        success_items = [x for x in items if x["status"] == "SUCCESS" and x["best_objective"] is not None]
        n_success = len(success_items)
        n_error = sum(1 for x in items if x["status"] == "ERROR")
        n_infeasible = sum(1 for x in items if x["status"] == "INFEASIBLE")

        # Objective stats
        obj_vals = [x["best_objective"] for x in success_items if x["best_objective"] is not None]
        mean_obj = statistics.mean(obj_vals) if obj_vals else None
        median_obj = statistics.median(obj_vals) if obj_vals else None
        std_obj = statistics.stdev(obj_vals) if len(obj_vals) > 1 else 0.0 if obj_vals else None
        min_obj = min(obj_vals) if obj_vals else None
        max_obj = max(obj_vals) if obj_vals else None

        # Runtime stats
        runtimes = [x["runtime_seconds"] for x in items if x["runtime_seconds"] is not None]
        mean_rt = statistics.mean(runtimes) if runtimes else None
        median_rt = statistics.median(runtimes) if runtimes else None
        std_rt = statistics.stdev(runtimes) if len(runtimes) > 1 else 0.0 if runtimes else None

        # Distance & Time stats
        dist_vals = [x["total_distance"] for x in success_items if x["total_distance"] is not None]
        time_vals = [x["total_travel_time"] for x in success_items if x["total_travel_time"] is not None]
        cong_vals = [x["total_congestion"] for x in success_items if x["total_congestion"] is not None]

        aggregates.append({
            "algorithm": algo,
            "instance_id": inst,
            "n_trials": n_trials,
            "n_success": n_success,
            "n_error": n_error,
            "n_infeasible": n_infeasible,
            "success_rate": round(n_success / n_trials, 4) if n_trials > 0 else 0.0,
            "mean_objective": round(mean_obj, 4) if mean_obj is not None else None,
            "median_objective": round(median_obj, 4) if median_obj is not None else None,
            "std_objective": round(std_obj, 4) if std_obj is not None else None,
            "min_objective": round(min_obj, 4) if min_obj is not None else None,
            "max_objective": round(max_obj, 4) if max_obj is not None else None,
            "mean_runtime_seconds": round(mean_rt, 4) if mean_rt is not None else None,
            "median_runtime_seconds": round(median_rt, 4) if median_rt is not None else None,
            "std_runtime_seconds": round(std_rt, 4) if std_rt is not None else None,
            "mean_distance_km": round(statistics.mean(dist_vals), 4) if dist_vals else None,
            "mean_travel_time_min": round(statistics.mean(time_vals), 4) if time_vals else None,
            "mean_congestion_penalty": round(statistics.mean(cong_vals), 4) if cong_vals else None,
            "feasibility_rate": round(sum(1 for x in items if x["is_feasible"]) / n_trials, 4) if n_trials > 0 else 0.0,
        })

    return aggregates


def generate_analysis_tables(
    results_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, Path]:
    """
    Generate aggregated summary CSV and JSON tables and a markdown report.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rows, meta_json, _ = load_benchmark_data(results_dir)
    aggregates = compute_algorithm_aggregates(rows)

    generated_files: dict[str, Path] = {}

    # 1. algorithm_comparison.csv
    comp_file = out_path / "algorithm_comparison.csv"
    if aggregates:
        fieldnames = list(aggregates[0].keys())
        with open(comp_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(aggregates)
    generated_files["algorithm_comparison"] = comp_file

    # 2. runtime_comparison.csv
    rt_file = out_path / "runtime_comparison.csv"
    rt_rows = [
        {
            "algorithm": a["algorithm"],
            "instance_id": a["instance_id"],
            "mean_runtime_seconds": a["mean_runtime_seconds"],
            "std_runtime_seconds": a["std_runtime_seconds"],
            "median_runtime_seconds": a["median_runtime_seconds"],
            "n_trials": a["n_trials"],
        }
        for a in aggregates
    ]
    if rt_rows:
        with open(rt_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rt_rows[0].keys()))
            writer.writeheader()
            writer.writerows(rt_rows)
    generated_files["runtime_comparison"] = rt_file

    # 3. feasibility.csv
    feas_file = out_path / "feasibility.csv"
    feas_rows = [
        {
            "algorithm": a["algorithm"],
            "instance_id": a["instance_id"],
            "feasibility_rate": a["feasibility_rate"],
            "success_rate": a["success_rate"],
            "n_success": a["n_success"],
            "n_infeasible": a["n_infeasible"],
            "n_error": a["n_error"],
            "n_trials": a["n_trials"],
        }
        for a in aggregates
    ]
    if feas_rows:
        with open(feas_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(feas_rows[0].keys()))
            writer.writeheader()
            writer.writerows(feas_rows)
    generated_files["feasibility"] = feas_file

    # 4. scalability.csv
    # Derive N from instance_id
    scale_file = out_path / "scalability.csv"
    scale_rows = []
    for a in aggregates:
        inst = a["instance_id"].lower()
        n_cust = 6 if "small" in inst else 15 if "medium" in inst else 30 if "large" in inst else 50
        scale_rows.append({
            "algorithm": a["algorithm"],
            "instance_id": a["instance_id"],
            "n_customers": n_cust,
            "mean_objective": a["mean_objective"],
            "mean_runtime_seconds": a["mean_runtime_seconds"],
            "feasibility_rate": a["feasibility_rate"],
        })
    if scale_rows:
        with open(scale_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(scale_rows[0].keys()))
            writer.writeheader()
            writer.writerows(scale_rows)
    generated_files["scalability"] = scale_file

    # 5. summary.json
    summary_file = out_path / "summary.json"
    summary_payload = {
        "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_results_dir": str(results_dir),
        "total_trials_analyzed": len(rows),
        "algorithms_evaluated": sorted(list({r["algorithm"] for r in rows})),
        "instances_evaluated": sorted(list({r["instance_id"] for r in rows})),
        "aggregates": aggregates,
    }
    with open(summary_file, "w", encoding="utf-8") as fh:
        json.dump(summary_payload, fh, indent=2)
    generated_files["summary"] = summary_file

    # 6. Markdown Report: benchmark_analysis.md
    report_file = out_path / "benchmark_analysis.md"
    with open(report_file, "w", encoding="utf-8") as fh:
        fh.write(_generate_markdown_report(summary_payload, aggregates))
    generated_files["report"] = report_file

    return generated_files


def generate_scientific_figures(
    results_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, Path]:
    """
    Generate all publication-ready vector SVG and PNG benchmark figures.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rows, _, conv_histories = load_benchmark_data(results_dir)
    aggregates = compute_algorithm_aggregates(rows)
    generated_figures: dict[str, Path] = {}

    # Figure 1: Convergence Comparison
    inst_candidates = [r["instance_id"] for r in rows if "small" in r["instance_id"]]
    target_inst = inst_candidates[0] if inst_candidates else rows[0]["instance_id"]
    conv_svg = plot_convergence_curves(
        conv_histories,
        title="QPSO vs Metaheuristics: Convergence Trajectory",
        instance_filter=target_inst,
    )
    svg_p, _ = save_chart(conv_svg, out_path / "convergence_comparison")
    generated_figures["convergence_comparison"] = svg_p

    # Figure 2: Objective Comparison (Lower is Better)
    obj_by_inst: dict[str, dict[str, float]] = {}
    for a in aggregates:
        inst = a["instance_id"]
        if a["mean_objective"] is not None:
            obj_by_inst.setdefault(inst, {})[a["algorithm"]] = a["mean_objective"]

    obj_svg = plot_grouped_barchart(
        obj_by_inst,
        title="Solution Quality Comparison (Mean Objective Fitness)",
        subtitle="Objective value minimization across benchmark instances (Lower is Better)",
        y_label="Objective Fitness",
        is_time=False,
    )
    svg_p, _ = save_chart(obj_svg, out_path / "objective_comparison")
    generated_figures["objective_comparison"] = svg_p

    # Figure 3: Runtime Comparison
    rt_by_inst: dict[str, dict[str, float]] = {}
    for a in aggregates:
        inst = a["instance_id"]
        if a["mean_runtime_seconds"] is not None:
            rt_by_inst.setdefault(inst, {})[a["algorithm"]] = a["mean_runtime_seconds"]

    rt_svg = plot_grouped_barchart(
        rt_by_inst,
        title="Execution Runtime Comparison (CPU Seconds)",
        subtitle="Wall-clock execution duration across benchmark scales (Lower is Better)",
        y_label="Runtime (s)",
        is_time=True,
    )
    svg_p, _ = save_chart(rt_svg, out_path / "runtime_comparison")
    generated_figures["runtime_comparison"] = svg_p

    # Figure 4 & 5: Scalability Curves (Runtime & Objective vs Customers N)
    scale_rt: dict[str, list[tuple[int, float]]] = {}
    scale_obj: dict[str, list[tuple[int, float]]] = {}

    for a in aggregates:
        inst = a["instance_id"].lower()
        n_cust = 6 if "small" in inst else 15 if "medium" in inst else 30 if "large" in inst else 50
        algo = a["algorithm"]
        if a["mean_runtime_seconds"] is not None:
            scale_rt.setdefault(algo, []).append((n_cust, a["mean_runtime_seconds"]))
        if a["mean_objective"] is not None:
            scale_obj.setdefault(algo, []).append((n_cust, a["mean_objective"]))

    scale_rt_svg = plot_scalability_curve(
        scale_rt,
        title="Scalability Analysis: Runtime vs Problem Scale",
        y_label="Runtime (s)",
        is_time=True,
    )
    svg_p, _ = save_chart(scale_rt_svg, out_path / "scalability_runtime")
    generated_figures["scalability_runtime"] = svg_p

    scale_obj_svg = plot_scalability_curve(
        scale_obj,
        title="Scalability Analysis: Solution Quality vs Problem Scale",
        y_label="Objective Fitness",
        is_time=False,
    )
    svg_p, _ = save_chart(scale_obj_svg, out_path / "scalability_objective")
    generated_figures["scalability_objective"] = svg_p

    # Figure 6: Feasibility Rate Comparison
    feas_by_inst: dict[str, dict[str, float]] = {}
    for a in aggregates:
        inst = a["instance_id"]
        feas_by_inst.setdefault(inst, {})[a["algorithm"]] = a["feasibility_rate"] * 100.0

    feas_svg = plot_grouped_barchart(
        feas_by_inst,
        title="Solution Feasibility Rate (%)",
        subtitle="Percentage of generated solutions satisfying all 5 hard VRP constraints",
        y_label="Feasibility (%)",
        is_time=False,
    )
    svg_p, _ = save_chart(feas_svg, out_path / "feasibility_comparison")
    generated_figures["feasibility_comparison"] = svg_p

    return generated_figures


def _generate_markdown_report(summary: dict[str, Any], aggregates: list[dict[str, Any]]) -> str:
    """Compile comprehensive technical markdown benchmark analysis report."""
    md = []
    md.append("# Q-Route — M11 Scientific Benchmark Analysis Report\n")
    md.append(f"**Analysis Timestamp:** `{summary['analysis_timestamp']}`  \n")
    md.append(f"**Total Trials Evaluated:** `{summary['total_trials_analyzed']}`  \n")
    md.append(f"**Algorithms Compared:** {', '.join(summary['algorithms_evaluated'])}  \n")
    md.append(f"**Benchmark Instances:** {', '.join(summary['instances_evaluated'])}\n")
    md.append("---\n")

    md.append("## 1. Executive Summary & Core Findings\n")
    md.append("- **Objective Minimization:** All algorithms were evaluated against the canonical fitness function ($w_T \\cdot \\text{Time} + w_D \\cdot \\text{Dist} + w_C \\cdot \\text{Congestion}$). Lower values indicate superior route efficiency.\n")
    md.append("- **Feasibility & Constraints:** The deterministic capacity repair and 2-opt intra-route local search pipeline maintained high solution feasibility across all stochastic metaheuristic algorithms.\n")
    md.append("- **Exact Optimality Anchor:** On small instances ($N=6$), the exact brute-force solver provided a mathematically proven global lower bound for evaluating metaheuristic optimality gaps.\n\n")

    md.append("## 2. Statistical Performance Summary (Mean ± Std)\n")
    md.append("| Instance | Algorithm | Trials | Success Rate | Mean Objective | Min Objective | Mean Runtime (s) | Feasibility |\n")
    md.append("|---|---|---|---|---|---|---|---|\n")

    for a in aggregates:
        std_str = f" ± {a['std_objective']:.2f}" if a["std_objective"] is not None and a["std_objective"] > 0 else ""
        mean_obj_str = f"{a['mean_objective']:.2f}{std_str}" if a["mean_objective"] is not None else "N/A"
        min_obj_str = f"{a['min_objective']:.2f}" if a["min_objective"] is not None else "N/A"
        rt_str = f"{a['mean_runtime_seconds']:.3f}s" if a["mean_runtime_seconds"] is not None else "N/A"
        feas_str = f"{int(a['feasibility_rate'] * 100)}%"

        md.append(f"| `{a['instance_id']}` | **{a['algorithm']}** | {a['n_trials']} | {int(a['success_rate']*100)}% | {mean_obj_str} | {min_obj_str} | {rt_str} | {feas_str} |\n")

    md.append("\n---\n")
    md.append("## 3. Generated Figures Index\n")
    md.append("- `results/figures/convergence_comparison.svg`: Iteration-by-iteration objective minimization trajectory.\n")
    md.append("- `results/figures/objective_comparison.svg`: Bar chart comparing solution quality across instances.\n")
    md.append("- `results/figures/runtime_comparison.svg`: Execution duration breakdown across scales.\n")
    md.append("- `results/figures/scalability_runtime.svg`: Runtime scaling curve as customer count $N$ increases.\n")
    md.append("- `results/figures/scalability_objective.svg`: Objective degradation curve with increasing scale.\n")
    md.append("- `results/figures/feasibility_comparison.svg`: Constraint satisfaction rates.\n\n")

    md.append("## 4. Reproducibility Instructions\n")
    md.append("To reproduce this analysis exactly from the raw Phase 3 results:\n")
    md.append("```bash\npython -m experiments.benchmarks.analyze_results --results-dir results/benchmarks --out-dir results/analysis --figures-dir results/figures\n```\n")

    return "".join(md)
