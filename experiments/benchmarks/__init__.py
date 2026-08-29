"""
experiments/benchmarks – Standardized reproducible benchmark instances and unified execution engine for M11.

Exports:
- BenchmarkSize: Enum of problem scales (SMALL, MEDIUM, LARGE, STRESS)
- BenchmarkInstanceConfig: Dataclass for benchmark specifications
- BENCHMARK_PRESETS: Predefined standard configurations
- BENCHMARK_SEEDS: Fixed deterministic seed array [42, 43, 44, 45, 46]
- generate_benchmark_instance: Single instance generator
- validate_benchmark_instance: Instance validator
- generate_and_save_all_benchmarks: Batch generator and manifest creator
- AlgorithmAdapter: Standardized multi-algorithm trial wrapper
- BenchmarkTrialResult: Dataclass for single-trial telemetry
- BenchmarkSuiteConfig: Dataclass for benchmark run parameters
- BenchmarkRunner: Unified multi-algorithm benchmark executor
"""

import sys
from pathlib import Path

# Ensure backend and repo root are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from .adapters import AlgorithmAdapter, BenchmarkTrialResult
from .configurations import (
    BENCHMARK_PRESETS,
    BENCHMARK_SEEDS,
    BenchmarkInstanceConfig,
    BenchmarkSize,
)
from .instance_generator import (
    generate_and_save_all_benchmarks,
    generate_benchmark_instance,
    validate_benchmark_instance,
)
from .runner import BenchmarkRunner, BenchmarkSuiteConfig

__all__ = [
    "BenchmarkSize",
    "BenchmarkInstanceConfig",
    "BENCHMARK_PRESETS",
    "BENCHMARK_SEEDS",
    "generate_benchmark_instance",
    "validate_benchmark_instance",
    "generate_and_save_all_benchmarks",
    "AlgorithmAdapter",
    "BenchmarkTrialResult",
    "BenchmarkSuiteConfig",
    "BenchmarkRunner",
]
