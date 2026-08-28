"""
app/qpso/config.py – Configuration for the Q-Route QPSO optimizer.

All tunable hyper-parameters live here so callers never need to reach
into the optimizer internals.

Usage
-----
    from app.qpso.config import QPSOConfig
    from app.vrp.objective import FitnessWeights

    cfg = QPSOConfig(n_particles=30, max_iterations=200, seed=42)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.vrp.objective import FitnessWeights


@dataclass
class QPSOConfig:
    """
    Hyper-parameter bundle for ``QPSOOptimizer``.

    Attributes
    ----------
    n_particles       : int            – swarm size (number of particles)
    max_iterations    : int            – hard upper bound on iterations
    time_budget_seconds: Optional[float] – wall-clock limit in seconds;
                                          None = unlimited
    convergence_tol   : float          – early-stop threshold: if the global
                                         best fitness does not improve by more
                                         than this value for ``stagnation_window``
                                         consecutive iterations, stop early
    stagnation_window : int            – number of stagnant iterations before
                                         early termination
    beta_max          : float          – initial contraction-expansion coefficient
                                         (controls quantum tunnelling range)
    beta_min          : float          – final coefficient after annealing
    seed              : int            – NumPy RNG seed for reproducibility
    fitness_weights   : FitnessWeights – objective-function weights forwarded
                                         to ``compute_fitness``; defaults to
                                         the project-standard values

    Notes
    -----
    β anneals linearly from ``beta_max`` (iteration 0) to ``beta_min``
    (iteration ``max_iterations - 1``):

        β(t) = beta_max − (beta_max − beta_min) · t / max_iterations

    A β of 1.0 gives wide quantum tunnelling (exploration); 0.5 gives
    tight tunnelling (exploitation).  The annealing schedule therefore
    naturally transitions from global search to local refinement.
    """

    n_particles: int = 30
    max_iterations: int = 200
    time_budget_seconds: Optional[float] = None
    convergence_tol: float = 1e-6
    stagnation_window: int = 20
    beta_max: float = 1.0
    beta_min: float = 0.5
    seed: int = 42
    fitness_weights: FitnessWeights = field(default_factory=FitnessWeights)

    def __post_init__(self) -> None:
        if self.n_particles < 2:
            raise ValueError(
                f"n_particles must be >= 2, got {self.n_particles}"
            )
        if self.max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >= 1, got {self.max_iterations}"
            )
        if self.time_budget_seconds is not None and self.time_budget_seconds <= 0:
            raise ValueError(
                f"time_budget_seconds must be > 0, got {self.time_budget_seconds}"
            )
        if not (0.0 < self.beta_min <= self.beta_max):
            raise ValueError(
                f"Need 0 < beta_min <= beta_max, "
                f"got beta_min={self.beta_min}, beta_max={self.beta_max}"
            )
        if self.stagnation_window < 1:
            raise ValueError(
                f"stagnation_window must be >= 1, got {self.stagnation_window}"
            )
