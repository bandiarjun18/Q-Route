"""
app/qpso/optimizer.py – Discrete QPSO optimizer for multi-vehicle VRP.

Algorithm overview
------------------
This implements Quantum-behaved Particle Swarm Optimization (QPSO) adapted
for the discrete Vehicle Routing Problem via priority-key encoding.

Each particle encodes a candidate solution as a vector of N real-valued
priority keys (one per customer).  The continuous QPSO quantum update rule
operates directly on these keys; the decoder in ``representation.py``
translates each updated particle into a concrete VRPSolution for fitness
evaluation.

QPSO quantum update (Sun et al., 2004)
---------------------------------------
For each particle i and each dimension d at iteration t:

    φ_d   ~ Uniform(0, 1)
    p_d   = φ_d · pbest_id + (1−φ_d) · gbest_d      # local attractor
    u_d   ~ Uniform(0, 1)
    sign  ~ choice(±1)
    β(t)  = beta_max − (beta_max − beta_min) · t / T  # annealing

    x_new_id = p_d  +  sign · β(t) · |x_id − p_d| · ln(1 / u_d)

Keys are clamped to [0, 1] after each update (the decoder uses only
relative order, so clamping does not distort the solution space).

Fitness
-------
``compute_fitness`` from ``app.vrp.objective`` is the SOLE fitness function.
This module never redefines the formula.

Evaluation pipeline (Milestone 5)
----------------------------------
Each particle evaluation now follows:

    decode  →  capacity repair  →  2-opt refinement  →  fitness evaluation

This pipeline is implemented inside ``_evaluate``.  The quantum update,
pbest/gbest tracking, and convergence-history logic are unchanged.

Stopping criteria (first to trigger)
-------------------------------------
1. ``max_iterations`` reached.
2. Wall-clock time exceeds ``time_budget_seconds``.
3. Global-best fitness has not improved by more than ``convergence_tol``
   for ``stagnation_window`` consecutive iterations.

Public API
----------
QPSOResult     – result dataclass
QPSOOptimizer  – main optimiser class; call ``.run()`` to execute
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.vrp.feasibility import check_feasibility
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import compute_fitness

from .config import QPSOConfig
from .local_search import two_opt
from .repair import repair_capacity
from .representation import decode, encode_random


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class QPSOResult:
    """
    Output of a completed QPSO run.

    Attributes
    ----------
    best_solution       : VRPSolution  – best decoded+repaired+refined solution
    best_fitness        : float        – objective value of best_solution
                                         (after repair and 2-opt)
    convergence_history : dict[int, float]
                                       – maps iteration index → global-best
                                         fitness at that iteration; useful for
                                         plotting convergence curves
    n_iterations_run    : int          – actual number of iterations completed
    stopped_early       : bool         – True if a stopping criterion other than
                                         max_iterations triggered the stop
    pre_repair_fitness  : Optional[float]
                                       – raw decoded fitness of the globally
                                         best particle, before any repair or
                                         local search (None if not available)
    post_repair_fitness : Optional[float]
                                       – fitness of the globally best particle
                                         after capacity repair but before 2-opt
                                         (None if not available)
    """

    best_solution: VRPSolution
    best_fitness: float
    convergence_history: dict[int, float] = field(default_factory=dict)
    n_iterations_run: int = 0
    stopped_early: bool = False
    pre_repair_fitness: Optional[float] = None
    post_repair_fitness: Optional[float] = None


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

class QPSOOptimizer:
    """
    Quantum-behaved Particle Swarm Optimizer for multi-vehicle VRP.

    Parameters
    ----------
    problem : VRPProblem  – the VRP instance to solve
    config  : QPSOConfig  – hyper-parameter bundle

    Usage
    -----
        from app.qpso.optimizer import QPSOOptimizer
        from app.qpso.config    import QPSOConfig

        result = QPSOOptimizer(problem, QPSOConfig(n_particles=20,
                                                   max_iterations=100)).run()
        print(result.best_fitness, result.best_solution.is_feasible)
    """

    def __init__(self, problem: VRPProblem, config: QPSOConfig) -> None:
        self.problem = problem
        self.config = config
        self._n_dims = len(problem.customers)  # one key per customer
        self._rng = np.random.default_rng(config.seed)

        if self._n_dims == 0:
            raise ValueError("VRPProblem must have at least one customer.")
        if len(problem.vehicles) == 0:
            raise ValueError("VRPProblem must have at least one vehicle.")

    # ------------------------------------------------------------------
    # Fitness evaluation (full pipeline)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        keys: np.ndarray,
    ) -> tuple[float, VRPSolution, float, float]:
        """
        Decode → repair → 2-opt → fitness evaluation.

        Parameters
        ----------
        keys : np.ndarray – particle position (priority-key vector)

        Returns
        -------
        (final_fitness, refined_solution, pre_repair_fitness, post_repair_fitness)

        ``final_fitness``      – fitness after repair and 2-opt
        ``refined_solution``   – VRPSolution with is_feasible / violations /
                                  objective_value populated
        ``pre_repair_fitness`` – fitness of the raw decoded solution (before
                                  any repair or local search)
        ``post_repair_fitness``– fitness after capacity repair but before 2-opt
        """
        weights = self.config.fitness_weights

        # 1. Decode raw solution from particle keys.
        raw_sol = decode(keys, self.problem)

        # 2. Record pre-repair fitness (for reporting / analysis).
        pre_repair_fit = compute_fitness(raw_sol, self.problem, weights)

        # 3. Capacity repair: move overflow customers to vehicles with slack.
        repaired_sol = repair_capacity(raw_sol, self.problem)

        # 4. Record post-repair fitness (for reporting / analysis).
        post_repair_fit = compute_fitness(repaired_sol, self.problem, weights)

        # 5. 2-opt local search on each feasible route.
        refined_sol = two_opt(repaired_sol, self.problem, weights)

        # 6. Compute final fitness using the shared objective function.
        final_fit = compute_fitness(refined_sol, self.problem, weights)

        # 7. Populate feasibility fields on the refined solution object.
        feas_result = check_feasibility(refined_sol, self.problem)
        refined_sol.is_feasible = feas_result.is_feasible
        refined_sol.violations = feas_result.violations
        refined_sol.objective_value = final_fit

        return final_fit, refined_sol, pre_repair_fit, post_repair_fit

    # ------------------------------------------------------------------
    # Beta annealing
    # ------------------------------------------------------------------

    def _beta(self, t: int, T: int) -> float:
        """
        Contraction-expansion coefficient at iteration t out of T.

        Anneals linearly from beta_max (t=0) to beta_min (t=T-1).
        """
        if T <= 1:
            return self.config.beta_min
        return (
            self.config.beta_max
            - (self.config.beta_max - self.config.beta_min) * t / (T - 1)
        )

    # ------------------------------------------------------------------
    # Quantum position update
    # ------------------------------------------------------------------

    def _quantum_update(
        self,
        positions: np.ndarray,
        pbest_pos: np.ndarray,
        gbest_pos: np.ndarray,
        beta: float,
    ) -> np.ndarray:
        """
        Apply one QPSO quantum update step to all particles simultaneously.

        Parameters
        ----------
        positions  : shape (n_particles, n_dims) – current positions
        pbest_pos  : shape (n_particles, n_dims) – personal best positions
        gbest_pos  : shape (n_dims,)             – global best position
        beta       : float                       – current β coefficient

        Returns
        -------
        new_positions : shape (n_particles, n_dims), clamped to [0, 1]
        """
        n_p, n_d = positions.shape

        # φ ~ U(0,1) per particle per dimension
        phi = self._rng.uniform(0.0, 1.0, size=(n_p, n_d))

        # Local attractor: weighted mean of personal-best and global-best
        attractors = phi * pbest_pos + (1.0 - phi) * gbest_pos  # (n_p, n_d)

        # u ~ U(0,1) for quantum tunnelling magnitude
        u = self._rng.uniform(0.0, 1.0, size=(n_p, n_d))
        # Avoid log(0): u is drawn from (0,1] so clamp tiny values
        u = np.clip(u, 1e-15, 1.0)

        # Random ±1 sign per entry
        sign = self._rng.choice([-1.0, 1.0], size=(n_p, n_d))

        # Quantum step: tunnel around the attractor
        step = beta * np.abs(positions - attractors) * np.log(1.0 / u)
        new_positions = attractors + sign * step

        # Clamp to [0, 1] — only relative order matters, clamping is safe
        return np.clip(new_positions, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Main optimisation loop
    # ------------------------------------------------------------------

    def run(self) -> QPSOResult:
        """
        Execute the QPSO optimisation and return the best solution found.

        Flow
        ----
        1. Initialise particle positions randomly.
        2. Evaluate all particles (decode → repair → 2-opt → fitness);
           set personal-best = initial positions.
        3. Identify global-best.
        4. For each iteration:
           a. Record global-best fitness in convergence_history.
           b. Check time budget.
           c. Apply quantum update to all particles.
           d. Evaluate new positions (full pipeline); update pbests/gbest.
           e. Update convergence_history with post-update gbest.
           f. Check stagnation stopping criterion.
        5. Return QPSOResult.
        """
        cfg = self.config
        n_p = cfg.n_particles
        n_d = self._n_dims
        T = cfg.max_iterations

        # ── 1. Initialise particle positions ────────────────────────────
        positions = np.stack(
            [encode_random(n_d, self._rng) for _ in range(n_p)]
        )                                            # (n_p, n_d)

        # ── 2. Initial evaluation ────────────────────────────────────────
        pbest_pos = positions.copy()                  # personal-best positions
        pbest_fit = np.full(n_p, math.inf)            # personal-best fitnesses

        # Store all initial evaluations so we can extract gbest without
        # a redundant second call to _evaluate.
        init_evals: list[tuple[float, VRPSolution, float, float]] = []
        for i in range(n_p):
            ev = self._evaluate(positions[i])
            pbest_fit[i] = ev[0]
            init_evals.append(ev)

        # ── 3. Global best ───────────────────────────────────────────────
        gbest_idx = int(np.argmin(pbest_fit))
        gbest_pos = pbest_pos[gbest_idx].copy()
        gbest_fit = float(pbest_fit[gbest_idx])
        gbest_solution = init_evals[gbest_idx][1]
        gbest_pre_repair_fit: float = init_evals[gbest_idx][2]
        gbest_post_repair_fit: float = init_evals[gbest_idx][3]

        convergence_history: dict[int, float] = {}
        stagnation_count = 0
        stopped_early = False
        t_start = time.monotonic()
        actual_iterations = 0

        # ── 4. Main loop ─────────────────────────────────────────────────
        for t in range(T):
            # a. Record global-best fitness BEFORE this iteration's update
            convergence_history[t] = gbest_fit
            actual_iterations = t + 1

            # b. Check time budget
            if (
                cfg.time_budget_seconds is not None
                and (time.monotonic() - t_start) >= cfg.time_budget_seconds
            ):
                stopped_early = True
                break

            # c. Quantum update
            beta = self._beta(t, T)
            positions = self._quantum_update(positions, pbest_pos, gbest_pos, beta)

            # d. Evaluate & update personal/global bests
            for i in range(n_p):
                fit, sol, pre_rf, post_rf = self._evaluate(positions[i])
                if fit < pbest_fit[i]:
                    pbest_fit[i] = fit
                    pbest_pos[i] = positions[i].copy()

                if fit < gbest_fit:
                    gbest_fit = fit
                    gbest_pos = positions[i].copy()
                    gbest_solution = sol
                    gbest_pre_repair_fit = pre_rf
                    gbest_post_repair_fit = post_rf

            # e. Update convergence record to reflect post-update gbest_fit.
            # This ensures history[t] always holds the best fitness *after*
            # processing iteration t (non-increasing guarantee holds).
            convergence_history[t] = gbest_fit

            # f. Stagnation check: compare current vs previous recorded value
            prev_best = convergence_history.get(t - 1, gbest_fit) if t > 0 else gbest_fit
            if prev_best - gbest_fit <= cfg.convergence_tol:
                stagnation_count += 1
            else:
                stagnation_count = 0

            if stagnation_count >= cfg.stagnation_window:
                stopped_early = True
                break

        # Ensure best_solution has all fields populated
        feas_result = check_feasibility(gbest_solution, self.problem)
        gbest_solution.is_feasible = feas_result.is_feasible
        gbest_solution.violations = feas_result.violations
        gbest_solution.objective_value = gbest_fit

        return QPSOResult(
            best_solution=gbest_solution,
            best_fitness=gbest_fit,
            convergence_history=convergence_history,
            n_iterations_run=actual_iterations,
            stopped_early=stopped_early,
            pre_repair_fitness=gbest_pre_repair_fit,
            post_repair_fitness=gbest_post_repair_fit,
        )
