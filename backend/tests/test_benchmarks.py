"""
tests/test_benchmarks.py – Unit and integration tests for M11 benchmark instance suite.

Verifies:
1. Generation of SMALL (6), MEDIUM (15), LARGE (30), and STRESS (50) instances.
2. Determinism and reproducibility with fixed seeds.
3. Validation checks for structural graph integrity and demand/capacity constraints.
4. Persistence roundtrip with save_vrp_json / load_vrp_json.
5. Batch generation and manifest schema validity.
6. Usability with the existing QPSO optimization pipeline.
"""

from __future__ import annotations

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

from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.vrp.generator import load_vrp_json, save_vrp_json
from experiments.benchmarks import (
    BENCHMARK_PRESETS,
    BENCHMARK_SEEDS,
    BenchmarkInstanceConfig,
    BenchmarkSize,
    generate_and_save_all_benchmarks,
    generate_benchmark_instance,
    validate_benchmark_instance,
)


class TestBenchmarkGeneration:
    """Tests for individual benchmark instance generation across all scales."""

    @pytest.mark.parametrize("size", [BenchmarkSize.SMALL, BenchmarkSize.MEDIUM, BenchmarkSize.LARGE, BenchmarkSize.STRESS])
    def test_generate_standard_sizes(self, size):
        config = BENCHMARK_PRESETS[size]
        problem = generate_benchmark_instance(config, seed=42)

        assert len(problem.customers) == config.n_customers
        assert len(problem.vehicles) == config.n_vehicles
        assert len(problem.graph.graph.nodes) >= config.n_nodes
        assert validate_benchmark_instance(problem, config) is True

    def test_seed_determinism(self):
        config = BENCHMARK_PRESETS[BenchmarkSize.SMALL]
        p1 = generate_benchmark_instance(config, seed=42)
        p2 = generate_benchmark_instance(config, seed=42)

        # Same customer coordinates and demands
        for c1, c2 in zip(p1.customers, p2.customers):
            assert c1.customer_id == c2.customer_id
            assert c1.location_node == c2.location_node
            assert abs(c1.demand - c2.demand) < 1e-9

        # Different seeds produce different demands/locations
        p3 = generate_benchmark_instance(config, seed=999)
        demands1 = [c.demand for c in p1.customers]
        demands3 = [c.demand for c in p3.customers]
        assert demands1 != demands3

    def test_save_and_load_instance(self, tmp_path):
        config = BENCHMARK_PRESETS[BenchmarkSize.SMALL]
        orig_problem = generate_benchmark_instance(config, seed=42)

        save_path = tmp_path / "test_instance.json"
        save_vrp_json(orig_problem, save_path)
        assert save_path.exists()

        loaded_problem = load_vrp_json(save_path)
        assert len(loaded_problem.customers) == len(orig_problem.customers)
        assert len(loaded_problem.vehicles) == len(orig_problem.vehicles)
        assert len(loaded_problem.graph.graph.nodes) == len(orig_problem.graph.graph.nodes)
        assert validate_benchmark_instance(loaded_problem) is True

    def test_pipeline_usability_smoke(self):
        """Smoke test verifying a loaded benchmark runs cleanly in QPSO."""
        config = BENCHMARK_PRESETS[BenchmarkSize.SMALL]
        problem = generate_benchmark_instance(config, seed=42)

        qpso_cfg = QPSOConfig(n_particles=5, max_iterations=5, seed=42)
        result = QPSOOptimizer(problem, qpso_cfg).run()

        assert result.best_fitness > 0
        assert result.best_solution.is_feasible is True
        assert len(result.best_solution.routes) == len(problem.vehicles)


class TestBenchmarkBatchAndManifest:
    """Tests for batch generation and manifest serialization."""

    def test_generate_and_save_all_benchmarks(self, tmp_path):
        test_seeds = [42, 43]
        bench_dir = tmp_path / "benchmarks"

        manifest = generate_and_save_all_benchmarks(bench_dir, seeds=test_seeds)

        assert manifest["manifest_version"] == "1.0"
        assert manifest["total_instances"] == len(BenchmarkSize) * len(test_seeds)

        manifest_file = bench_dir / "manifest.json"
        assert manifest_file.exists()

        with open(manifest_file, encoding="utf-8") as fh:
            loaded_manifest = json.load(fh)
        assert loaded_manifest["total_instances"] == manifest["total_instances"]

        # Check each file exists and is valid
        for entry in loaded_manifest["instances"]:
            inst_path = bench_dir / entry["filename"]
            assert inst_path.exists()
            loaded_p = load_vrp_json(inst_path)
            assert len(loaded_p.customers) == entry["n_customers"]
            assert len(loaded_p.vehicles) == entry["n_vehicles"]
