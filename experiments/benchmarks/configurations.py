"""
experiments/benchmarks/configurations.py – Standardized benchmark instance configurations for M11.

Defines reproducible problem specifications across 4 problem scales:
1. SMALL   : N = 6 customers,  2 vehicles,  20 nodes, 1 depot
2. MEDIUM  : N = 15 customers, 4 vehicles,  40 nodes, 2 depots
3. LARGE   : N = 30 customers, 6 vehicles,  80 nodes, 3 depots
4. STRESS  : N = 50 customers, 10 vehicles, 120 nodes, 4 depots

Standard Seeds:
A fixed list of deterministic seeds (42, 43, 44, 45, 46) enables multi-trial stochastic evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class BenchmarkSize(str, Enum):
    """Standardized problem scale tiers."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    STRESS = "stress"


# Standard deterministic seed list for benchmark sweeps
BENCHMARK_SEEDS: list[int] = [42, 43, 44, 45, 46]


@dataclass(frozen=True)
class BenchmarkInstanceConfig:
    """
    Specification for a synthetic VRP benchmark instance.
    """

    size: BenchmarkSize
    n_customers: int
    n_vehicles: int
    n_nodes: int
    n_depots: int
    capacity_factor: float = 1.5
    demand_min: float = 1.0
    demand_max: float = 10.0
    connect_radius_km: float = 3.5
    grid_size_km: float = 10.0
    closed_fraction: float = 0.05
    seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to plain dictionary."""
        data = asdict(self)
        data["size"] = self.size.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkInstanceConfig:
        """Construct from dictionary."""
        d = dict(data)
        if isinstance(d.get("size"), str):
            d["size"] = BenchmarkSize(d["size"])
        return cls(**d)


# Standard predefined specifications
BENCHMARK_PRESETS: dict[BenchmarkSize, BenchmarkInstanceConfig] = {
    BenchmarkSize.SMALL: BenchmarkInstanceConfig(
        size=BenchmarkSize.SMALL,
        n_customers=6,
        n_vehicles=2,
        n_nodes=20,
        n_depots=1,
        capacity_factor=1.5,
        demand_min=1.0,
        demand_max=10.0,
        connect_radius_km=3.5,
        grid_size_km=10.0,
        closed_fraction=0.05,
        seed=42,
    ),
    BenchmarkSize.MEDIUM: BenchmarkInstanceConfig(
        size=BenchmarkSize.MEDIUM,
        n_customers=15,
        n_vehicles=4,
        n_nodes=40,
        n_depots=2,
        capacity_factor=1.5,
        demand_min=1.0,
        demand_max=10.0,
        connect_radius_km=4.0,
        grid_size_km=15.0,
        closed_fraction=0.05,
        seed=42,
    ),
    BenchmarkSize.LARGE: BenchmarkInstanceConfig(
        size=BenchmarkSize.LARGE,
        n_customers=30,
        n_vehicles=6,
        n_nodes=80,
        n_depots=3,
        capacity_factor=1.5,
        demand_min=1.0,
        demand_max=10.0,
        connect_radius_km=4.5,
        grid_size_km=20.0,
        closed_fraction=0.05,
        seed=42,
    ),
    BenchmarkSize.STRESS: BenchmarkInstanceConfig(
        size=BenchmarkSize.STRESS,
        n_customers=50,
        n_vehicles=10,
        n_nodes=120,
        n_depots=4,
        capacity_factor=1.5,
        demand_min=1.0,
        demand_max=10.0,
        connect_radius_km=5.0,
        grid_size_km=25.0,
        closed_fraction=0.05,
        seed=42,
    ),
}
