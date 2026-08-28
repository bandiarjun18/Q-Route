#!/usr/bin/env python
"""
experiments/run_qpso.py – End-to-end QPSO experiment for Q-Route.

Runs a small Multi-Vehicle VRP on a synthetic graph using the QPSO
optimizer (with Milestone 5 repair + 2-opt pipeline) and prints a
detailed report of the best solution found, including before/after
fitness at each stage of the pipeline.

Usage (from the repo root)
--------------------------
    python experiments/run_qpso.py
    python experiments/run_qpso.py --particles 20 --iterations 100
    python experiments/run_qpso.py --vehicles 3 --customers 8 --seed 7

All options
-----------
    --vehicles   INT    number of vehicles          (default 2)
    --customers  INT    number of customers          (default 6)
    --nodes      INT    graph nodes                  (default 20)
    --particles  INT    QPSO swarm size              (default 20)
    --iterations INT    max QPSO iterations          (default no limit)
    --time       FLOAT  wall-clock budget in seconds (default no limit)
    --seed       INT    random seed                  (default 42)
    --wT         FLOAT  travel-time weight           (default 1.0)
    --wD         FLOAT  distance weight              (default 0.5)
    --wC         FLOAT  congestion weight            (default 0.3)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ── Ensure backend/ is on sys.path so `import app.*` works ──────────────────
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.vrp.generator import generate_vrp_instance
from app.vrp.objective import FitnessWeights
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer


# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run QPSO on a synthetic Q-Route VRP instance."
    )
    p.add_argument("--vehicles",   type=int,   default=2,    help="Number of vehicles")
    p.add_argument("--customers",  type=int,   default=6,    help="Number of customers")
    p.add_argument("--nodes",      type=int,   default=20,   help="Graph nodes")
    p.add_argument("--particles",  type=int,   default=20,   help="QPSO swarm size")
    p.add_argument("--iterations", type=int,   default=100,  help="Max QPSO iterations")
    p.add_argument("--time",       type=float, default=None, help="Wall-clock budget (s)")
    p.add_argument("--seed",       type=int,   default=42,   help="Random seed")
    p.add_argument("--wT",         type=float, default=1.0,  help="Travel-time weight")
    p.add_argument("--wD",         type=float, default=0.5,  help="Distance weight")
    p.add_argument("--wC",         type=float, default=0.3,  help="Congestion weight")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _separator(char: str = "-", width: int = 60) -> str:
    return char * width


def _print_section(title: str) -> None:
    print()
    print(_separator("="))
    print(f"  {title}")
    print(_separator("="))


def _convergence_summary(history: dict[int, float]) -> None:
    """Print a compact convergence table (first, every 10th, last iteration)."""
    if not history:
        print("  (no convergence data)")
        return

    iters = sorted(history.keys())
    step = max(1, len(iters) // 10)
    selected = sorted(set(iters[::step]) | {iters[0], iters[-1]})

    print(f"  {'Iteration':>10}  {'Best Fitness':>16}")
    print(f"  {_separator('-', 28)}")
    for it in selected:
        print(f"  {it:>10}  {history[it]:>16.4f}")


def _fmt(value: float | None) -> str:
    """Format an optional fitness value for display."""
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{value:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    # ── 1. Build synthetic VRP problem ───────────────────────────────────
    _print_section("Q-Route QPSO Experiment (Milestone 5)")
    print(f"  Generating synthetic VRP instance …")

    problem = generate_vrp_instance(
        n_vehicles=args.vehicles,
        n_customers=args.customers,
        n_nodes=args.nodes,
        seed=args.seed,
    )

    # ── 2. Configuration ─────────────────────────────────────────────────
    weights = FitnessWeights(wT=args.wT, wD=args.wD, wC=args.wC)
    cfg = QPSOConfig(
        n_particles=args.particles,
        max_iterations=args.iterations,
        time_budget_seconds=args.time,
        seed=args.seed,
        fitness_weights=weights,
    )

    _print_section("Configuration")
    print(f"  Vehicles       : {len(problem.vehicles)}")
    print(f"  Customers      : {len(problem.customers)}")
    print(f"  Graph nodes    : {problem.graph.node_count()}")
    print(f"  Graph edges    : {problem.graph.edge_count()} (directed)")
    print(f"  Particles      : {cfg.n_particles}")
    print(f"  Max iterations : {cfg.max_iterations}")
    print(f"  Time budget    : {cfg.time_budget_seconds or 'unlimited'} s")
    print(f"  Seed           : {cfg.seed}")
    print(f"  Weights        : wT={cfg.fitness_weights.wT}  "
          f"wD={cfg.fitness_weights.wD}  wC={cfg.fitness_weights.wC}")
    print(f"  Penalty/viol.  : {cfg.fitness_weights.penalty_per_violation}")

    print()
    print(f"  Fleet:")
    for v in problem.vehicles:
        print(f"    Vehicle {v.vehicle_id}: depot={v.depot_node}, "
              f"capacity={v.capacity:.2f}")

    print()
    print(f"  Customers:")
    for c in problem.customers:
        print(f"    Customer {c.customer_id}: node={c.location_node}, "
              f"demand={c.demand:.4f}")

    # ── 3. Run QPSO ──────────────────────────────────────────────────────
    _print_section("Running QPSO (decode -> repair -> 2-opt) ...")
    t0 = time.monotonic()
    optimizer = QPSOOptimizer(problem, cfg)
    result = optimizer.run()
    elapsed = time.monotonic() - t0
    print(f"  Done in {elapsed:.2f} s")

    # ── 4. Pipeline fitness stages (best particle) ───────────────────────
    _print_section("Pipeline Fitness Stages (globally best particle)")
    print(f"  Stage 1 – raw decoded (before repair) : "
          f"{_fmt(result.pre_repair_fitness)}")
    print(f"  Stage 2 – after capacity repair        : "
          f"{_fmt(result.post_repair_fitness)}")
    print(f"  Stage 3 – after 2-opt refinement       : "
          f"{_fmt(result.best_fitness)}")

    # Show whether each stage made a measurable difference.
    if (result.pre_repair_fitness is not None
            and result.post_repair_fitness is not None
            and result.pre_repair_fitness > 0):
        repair_delta = result.pre_repair_fitness - result.post_repair_fitness
        opt_delta = result.post_repair_fitness - result.best_fitness
        print()
        print(f"  Repair improved fitness by  : {repair_delta:+.4f}")
        print(f"  2-opt improved fitness by   : {opt_delta:+.4f}")

    # ── 5. Best solution ─────────────────────────────────────────────────
    sol = result.best_solution
    _print_section("Best Solution Found")
    print(f"  Best fitness   : {result.best_fitness:.4f}")
    print(f"  Feasible       : {sol.is_feasible}")
    print(f"  Iterations run : {result.n_iterations_run}")
    print(f"  Stopped early  : {result.stopped_early}")

    if sol.violations:
        print(f"\n  Violations ({len(sol.violations)}):")
        for v in sol.violations:
            print(f"    ✗ {v}")
    else:
        print("  Violations     : none")

    # ── 6. Per-vehicle routes ────────────────────────────────────────────
    print()
    print("  Per-vehicle routes:")
    cust_by_id = problem.customer_by_id
    for route in sol.routes:
        demand = sum(cust_by_id[cid].demand for cid in route.visit_order
                     if cid in cust_by_id)
        veh = next(v for v in problem.vehicles if v.vehicle_id == route.vehicle_id)
        utilisation = demand / veh.capacity * 100 if veh.capacity > 0 else 0
        print(f"    Vehicle {route.vehicle_id}:")
        print(f"      Customers  : {route.visit_order}")
        print(f"      Demand     : {demand:.4f} / {veh.capacity:.2f} "
              f"({utilisation:.1f}%)")
        print(f"      Seq length : {len(route.node_sequence)} nodes")
        print(f"      Sequence   : {route.node_sequence}")

    # ── 7. Fitness breakdown ─────────────────────────────────────────────
    from app.vrp.objective import route_components
    _print_section("Fitness Breakdown")
    total_t = total_d = total_c = 0.0
    for route in sol.routes:
        t_c, d_c, c_c = route_components(problem.graph, route.node_sequence)
        total_t += t_c if not (t_c != t_c) else 0   # guard NaN
        total_d += d_c if not (d_c != d_c) else 0
        total_c += c_c if not (c_c != c_c) else 0
    w = cfg.fitness_weights
    base = w.wT * total_t + w.wD * total_d + w.wC * total_c
    penalty = w.penalty_per_violation * len(sol.violations)
    print(f"  Travel time  (sum eff_time)  : {total_t:.4f} min")
    print(f"  Distance     (sum dist)       : {total_d:.4f} km")
    print(f"  Congestion   (sum cong_pen)   : {total_c:.4f}")
    print(f"  Base cost    (weighted)       : {base:.4f}")
    print(f"  Penalty      ({len(sol.violations)} violations x "
          f"{w.penalty_per_violation})  : {penalty:.4f}")
    print(f"  Total fitness                 : {result.best_fitness:.4f}")

    # ── 8. Convergence ───────────────────────────────────────────────────
    _print_section("Convergence History")
    _convergence_summary(result.convergence_history)

    # Monotonicity check
    iters = sorted(result.convergence_history.keys())
    is_non_increasing = all(
        result.convergence_history[iters[i]] >= result.convergence_history[iters[i + 1]]
        for i in range(len(iters) - 1)
    )
    print()
    print(f"  Non-increasing: {is_non_increasing}")
    print(f"  Initial best  : {result.convergence_history[iters[0]]:.4f}"
          if iters else "  (empty history)")
    print(f"  Final best    : {result.best_fitness:.4f}")
    print()
    print(_separator("="))
    print("  Milestone 5 experiment complete.")
    print(_separator("="))


if __name__ == "__main__":
    main()
