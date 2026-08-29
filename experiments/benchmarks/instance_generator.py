"""
experiments/benchmarks/instance_generator.py – Benchmark instance generator, validator, and manifest builder.

Generates reproducible VRP benchmark instances across multiple problem scales,
validates structural graph connectivity, and exports datasets with machine-readable manifests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from app.graph.pathfinding import shortest_path
from app.vrp.generator import generate_vrp_instance, load_vrp_json, save_vrp_json
from app.vrp.models import VRPProblem

from .configurations import (
    BENCHMARK_PRESETS,
    BENCHMARK_SEEDS,
    BenchmarkInstanceConfig,
    BenchmarkSize,
)


def validate_benchmark_instance(
    problem: VRPProblem,
    config: BenchmarkInstanceConfig | None = None,
) -> bool:
    """
    Validate structural integrity and solvability of a generated benchmark instance.

    Checks:
    - Customer and vehicle counts match expectations.
    - Graph is non-empty with existing nodes and edges.
    - All depot and customer location nodes exist in the graph.
    - Fleet capacity is sufficient to satisfy total customer demand.
    - Shortest paths exist from depots to customer locations.

    Parameters
    ----------
    problem : VRPProblem – The instance to validate
    config  : BenchmarkInstanceConfig | None – Optional config to verify expected dimensions

    Returns
    -------
    True if valid. Raises ValueError on any structural inconsistency.
    """
    if not problem.vehicles:
        raise ValueError("Benchmark instance validation failed: No vehicles in fleet.")
    if not problem.customers:
        raise ValueError("Benchmark instance validation failed: No customers in problem.")
    if problem.graph is None or len(problem.graph.graph.nodes) == 0:
        raise ValueError("Benchmark instance validation failed: Graph is missing or empty.")

    g = problem.graph.graph

    if config is not None:
        if len(problem.customers) != config.n_customers:
            raise ValueError(
                f"Customer count mismatch: expected {config.n_customers}, got {len(problem.customers)}"
            )
        if len(problem.vehicles) != config.n_vehicles:
            raise ValueError(
                f"Vehicle count mismatch: expected {config.n_vehicles}, got {len(problem.vehicles)}"
            )

    # Validate customer location nodes
    for cust in problem.customers:
        if cust.location_node not in g:
            raise ValueError(
                f"Customer {cust.customer_id} location node {cust.location_node} not in graph."
            )
        if cust.demand <= 0:
            raise ValueError(f"Customer {cust.customer_id} has non-positive demand: {cust.demand}")

    # Validate vehicles and depots
    total_capacity = 0.0
    for v in problem.vehicles:
        if v.depot_node not in g:
            raise ValueError(f"Vehicle {v.vehicle_id} depot node {v.depot_node} not in graph.")
        if v.capacity <= 0:
            raise ValueError(f"Vehicle {v.vehicle_id} has non-positive capacity: {v.capacity}")
        total_capacity += v.capacity

    total_demand = sum(c.demand for c in problem.customers)
    if total_capacity < total_demand:
        raise ValueError(
            f"Fleet capacity ({total_capacity}) is less than total demand ({total_demand})."
        )

    # Check path connectivity from depots to customers
    depots = {v.depot_node for v in problem.vehicles}
    for d in depots:
        for cust in problem.customers:
            try:
                shortest_path(problem.graph, d, cust.location_node)
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise ValueError(
                    f"No path between depot node {d} and customer location {cust.location_node}."
                ) from exc

    return True


def generate_benchmark_instance(
    config: BenchmarkInstanceConfig,
    seed: int | None = None,
) -> VRPProblem:
    """
    Generate a single reproducible VRP benchmark instance.

    Parameters
    ----------
    config : BenchmarkInstanceConfig – Instance parameters
    seed   : int | None – Explicit seed override (defaults to config.seed)

    Returns
    -------
    VRPProblem instance ready for optimization.
    """
    actual_seed = seed if seed is not None else config.seed

    problem = generate_vrp_instance(
        n_vehicles=config.n_vehicles,
        n_customers=config.n_customers,
        n_nodes=config.n_nodes,
        n_depots=config.n_depots,
        capacity_factor=config.capacity_factor,
        demand_min=config.demand_min,
        demand_max=config.demand_max,
        connect_radius_km=config.connect_radius_km,
        grid_size_km=config.grid_size_km,
        closed_fraction=config.closed_fraction,
        seed=actual_seed,
    )

    validate_benchmark_instance(problem, config)
    return problem


def generate_and_save_all_benchmarks(
    output_dir: Path | str,
    seeds: list[int] | None = None,
) -> dict[str, Any]:
    """
    Generate and save all benchmark instances across all preset scales and seeds.
    Creates data/benchmarks/manifest.json.

    Parameters
    ----------
    output_dir : Path | str – Target directory (e.g. data/benchmarks)
    seeds      : list[int] | None – List of seeds (default BENCHMARK_SEEDS)

    Returns
    -------
    dict representing the benchmark manifest.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    use_seeds = seeds if seeds is not None else BENCHMARK_SEEDS
    manifest_entries: list[dict[str, Any]] = []

    for size_key, base_config in BENCHMARK_PRESETS.items():
        for seed in use_seeds:
            instance_id = f"{size_key.value}_seed_{seed}"
            filename = f"{instance_id}.json"
            file_path = out_path / filename

            # Generate instance
            problem = generate_benchmark_instance(base_config, seed=seed)

            # Persist instance using canonical save_vrp_json
            save_vrp_json(problem, file_path)

            manifest_entries.append(
                {
                    "instance_id": instance_id,
                    "size": size_key.value,
                    "seed": seed,
                    "n_customers": len(problem.customers),
                    "n_vehicles": len(problem.vehicles),
                    "n_nodes": len(problem.graph.graph.nodes),
                    "n_edges": len(problem.graph.graph.edges),
                    "total_demand": round(sum(c.demand for c in problem.customers), 4),
                    "total_capacity": round(sum(v.capacity for v in problem.vehicles), 4),
                    "filename": filename,
                    "relative_path": str(file_path.relative_to(out_path.parent.parent)),
                    "config": base_config.to_dict(),
                }
            )

    manifest = {
        "manifest_version": "1.0",
        "description": "Standardized benchmark instances for Q-Route M11 evaluation suite",
        "total_instances": len(manifest_entries),
        "sizes": [s.value for s in BenchmarkSize],
        "seeds": use_seeds,
        "instances": manifest_entries,
    }

    manifest_file = out_path / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    return manifest
