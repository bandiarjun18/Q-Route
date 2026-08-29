"""
experiments/comparators – Reusable comparator algorithm suite for M11 benchmarking.

Algorithms:
- ClassicalPSO: Standard continuous/random-key Particle Swarm Optimization
- GeneticAlgorithm: Generational GA with tournament selection, SBX crossover, elitism
- SimulatedAnnealing: SA with Metropolis acceptance and geometric cooling
- ExactSolver: Combinatorial exhaustive solver for small instances (N <= 8)
- ComparatorResult: Common result container
"""

from .classical_pso import ClassicalPSO, ClassicalPSOConfig
from .common import ComparatorResult, evaluate_particle
from .exact_solver import ExactSolver
from .genetic_algorithm import GAConfig, GeneticAlgorithm
from .simulated_annealing import SAConfig, SimulatedAnnealing

__all__ = [
    "ComparatorResult",
    "evaluate_particle",
    "ClassicalPSO",
    "ClassicalPSOConfig",
    "GeneticAlgorithm",
    "GAConfig",
    "SimulatedAnnealing",
    "SAConfig",
    "ExactSolver",
]
