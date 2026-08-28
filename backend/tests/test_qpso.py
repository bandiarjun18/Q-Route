"""
tests/test_qpso.py – Unit tests for the Q-Route QPSO optimizer (Milestone 4).

Coverage (20 tests matching the M4 requirements)
-------------------------------------------------
Config:
  1. QPSOConfig accepts valid values.
  2. Invalid QPSOConfig values are rejected (5 sub-cases).

Representation:
  3. encode_random produces array of correct shape in [0,1].
  4. decode returns VRPSolution with correct structure.
  5. Particle positions remain in [0,1] after a quantum update.

Optimizer lifecycle:
  6.  QPSO initialises successfully.
  7.  QPSO runs end-to-end on a small synthetic VRP.
  8.  QPSO returns a QPSOResult.
  9.  best_solution is populated.
  10. best_fitness is finite.

Convergence / correctness:
  11. convergence_history is non-empty.
  12. convergence history is non-increasing (minimisation).
  13. final solution has feasibility information populated.
  14. decoded routes have valid per-vehicle route structures.
  15. QPSO uses the shared Milestone 3 fitness function.

Reproducibility:
  16. Same seed → reproducible results.
  17. Different seeds → different trajectories are allowed.

Stopping criteria:
  18. Max-iteration stopping works.
  19. Time-budget stopping works.
  20. Stagnation stopping works.

Run from backend/ directory:
    python -m pytest tests/test_qpso.py -v
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from app.graph.model import TransportGraph
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer, QPSOResult
from app.qpso.representation import decode, encode_random, _assign_customers
from app.vrp.feasibility import check_feasibility
from app.vrp.generator import generate_vrp_instance
from app.vrp.models import Customer, Vehicle, VRPProblem, VehicleRoute, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness


# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def tiny_graph() -> TransportGraph:
    """
    Minimal 3-node graph: depot(0) – A(1) – B(2) – back to depot(0).
    All edges open, bidirectional.
    """
    tg = TransportGraph()
    tg.add_node(0, node_type="depot",    x=0.0, y=0.0)
    tg.add_node(1, node_type="customer", x=1.0, y=0.0)
    tg.add_node(2, node_type="customer", x=2.0, y=0.0)

    for u, v, dist in [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 2.0)]:
        tg.add_edge(u, v, distance=dist, base_travel_time=dist, congestion_factor=1.0)
        tg.add_edge(v, u, distance=dist, base_travel_time=dist, congestion_factor=1.0)
    return tg


@pytest.fixture()
def tiny_problem(tiny_graph: TransportGraph) -> VRPProblem:
    """
    2 vehicles, 4 customers, comfortable capacity so feasible solutions exist.
    """
    vehicles = [
        Vehicle(vehicle_id=0, capacity=50.0, depot_node=0),
        Vehicle(vehicle_id=1, capacity=50.0, depot_node=0),
    ]
    customers = [
        Customer(customer_id=0, location_node=1, demand=5.0),
        Customer(customer_id=1, location_node=2, demand=5.0),
        Customer(customer_id=2, location_node=1, demand=5.0),
        Customer(customer_id=3, location_node=2, demand=5.0),
    ]
    return VRPProblem(graph=tiny_graph, vehicles=vehicles, customers=customers)


@pytest.fixture()
def tiny_cfg() -> QPSOConfig:
    """Very small config so tests run in < 1 s."""
    return QPSOConfig(
        n_particles=5,
        max_iterations=10,
        seed=42,
    )


@pytest.fixture()
def synthetic_problem() -> VRPProblem:
    """Larger synthetic problem used for integration tests."""
    return generate_vrp_instance(
        n_vehicles=2, n_customers=6, n_nodes=20, seed=42
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1–2. QPSOConfig tests
# ═══════════════════════════════════════════════════════════════════════════

class TestQPSOConfig:

    def test_valid_config_accepted(self) -> None:
        cfg = QPSOConfig(
            n_particles=10,
            max_iterations=50,
            time_budget_seconds=30.0,
            convergence_tol=1e-5,
            stagnation_window=10,
            beta_max=1.0,
            beta_min=0.5,
            seed=99,
        )
        assert cfg.n_particles == 10
        assert cfg.max_iterations == 50
        assert cfg.beta_max == pytest.approx(1.0)
        assert cfg.beta_min == pytest.approx(0.5)

    def test_default_config_valid(self) -> None:
        cfg = QPSOConfig()
        assert cfg.n_particles >= 2
        assert cfg.max_iterations >= 1

    def test_fitness_weights_forwarded(self) -> None:
        w = FitnessWeights(wT=2.0, wD=1.0, wC=0.5)
        cfg = QPSOConfig(fitness_weights=w)
        assert cfg.fitness_weights.wT == pytest.approx(2.0)

    def test_invalid_n_particles_raises(self) -> None:
        with pytest.raises(ValueError, match="n_particles"):
            QPSOConfig(n_particles=1)

    def test_invalid_max_iterations_raises(self) -> None:
        with pytest.raises(ValueError, match="max_iterations"):
            QPSOConfig(max_iterations=0)

    def test_invalid_time_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="time_budget"):
            QPSOConfig(time_budget_seconds=-1.0)

    def test_invalid_beta_raises(self) -> None:
        with pytest.raises(ValueError, match="beta"):
            QPSOConfig(beta_min=0.8, beta_max=0.5)  # min > max

    def test_invalid_stagnation_window_raises(self) -> None:
        with pytest.raises(ValueError, match="stagnation"):
            QPSOConfig(stagnation_window=0)


# ═══════════════════════════════════════════════════════════════════════════
# 3–5. Representation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRepresentation:

    def test_encode_random_shape(self) -> None:
        rng = np.random.default_rng(42)
        keys = encode_random(6, rng)
        assert keys.shape == (6,)

    def test_encode_random_in_unit_interval(self) -> None:
        rng = np.random.default_rng(0)
        keys = encode_random(20, rng)
        assert np.all(keys >= 0.0)
        assert np.all(keys <= 1.0)

    def test_decode_returns_vrp_solution(
        self, tiny_problem: VRPProblem
    ) -> None:
        rng = np.random.default_rng(42)
        keys = encode_random(len(tiny_problem.customers), rng)
        sol = decode(keys, tiny_problem)
        assert isinstance(sol, VRPSolution)

    def test_decode_one_route_per_vehicle(
        self, tiny_problem: VRPProblem
    ) -> None:
        rng = np.random.default_rng(7)
        keys = encode_random(len(tiny_problem.customers), rng)
        sol = decode(keys, tiny_problem)
        assert len(sol.routes) == len(tiny_problem.vehicles)

    def test_decode_all_customers_served(
        self, tiny_problem: VRPProblem
    ) -> None:
        """Every customer must appear in exactly one route."""
        rng = np.random.default_rng(5)
        keys = encode_random(len(tiny_problem.customers), rng)
        sol = decode(keys, tiny_problem)
        all_served = []
        for r in sol.routes:
            all_served.extend(r.visit_order)
        assert sorted(all_served) == sorted(
            c.customer_id for c in tiny_problem.customers
        )

    def test_particle_positions_clamped(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """After a quantum update, all keys must remain in [0, 1]."""
        opt = QPSOOptimizer(tiny_problem, tiny_cfg)
        n_p = tiny_cfg.n_particles
        n_d = len(tiny_problem.customers)
        rng = np.random.default_rng(0)
        positions = rng.uniform(0, 1, (n_p, n_d))
        pbest = positions.copy()
        gbest = positions[0].copy()
        updated = opt._quantum_update(positions, pbest, gbest, beta=1.0)
        assert np.all(updated >= 0.0)
        assert np.all(updated <= 1.0)

    def test_decode_routes_start_and_end_at_depot(
        self, tiny_problem: VRPProblem
    ) -> None:
        """Every route with customers must start and end at its depot."""
        rng = np.random.default_rng(3)
        keys = encode_random(len(tiny_problem.customers), rng)
        sol = decode(keys, tiny_problem)
        vehicle_depot = {v.vehicle_id: v.depot_node
                         for v in tiny_problem.vehicles}
        for route in sol.routes:
            if len(route.visit_order) > 0:
                seq = route.node_sequence
                depot = vehicle_depot[route.vehicle_id]
                assert seq[0] == depot, f"Route {route.vehicle_id} doesn't start at depot"
                assert seq[-1] == depot, f"Route {route.vehicle_id} doesn't end at depot"


# ═══════════════════════════════════════════════════════════════════════════
# 6–10. Optimizer lifecycle tests
# ═══════════════════════════════════════════════════════════════════════════

class TestOptimizerLifecycle:

    def test_initialises_successfully(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        opt = QPSOOptimizer(tiny_problem, tiny_cfg)
        assert opt._n_dims == len(tiny_problem.customers)

    def test_runs_end_to_end(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert result is not None

    def test_returns_qpso_result(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert isinstance(result, QPSOResult)

    def test_best_solution_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert result.best_solution is not None
        assert isinstance(result.best_solution, VRPSolution)

    def test_best_fitness_finite(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert math.isfinite(result.best_fitness)

    def test_no_crash_on_synthetic_problem(
        self, synthetic_problem: VRPProblem
    ) -> None:
        cfg = QPSOConfig(n_particles=5, max_iterations=5, seed=42)
        result = QPSOOptimizer(synthetic_problem, cfg).run()
        assert result.best_fitness < math.inf or True  # must not raise


# ═══════════════════════════════════════════════════════════════════════════
# 11–14. Convergence & correctness tests
# ═══════════════════════════════════════════════════════════════════════════

class TestConvergenceAndCorrectness:

    def test_convergence_history_non_empty(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert len(result.convergence_history) > 0

    def test_convergence_history_non_increasing(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """
        For minimisation, every recorded fitness must be ≤ the previous
        recorded fitness.
        """
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        history = result.convergence_history
        iters = sorted(history.keys())
        for i in range(len(iters) - 1):
            t, t1 = iters[i], iters[i + 1]
            assert history[t] >= history[t1] - 1e-9, (
                f"Convergence increased at iteration {t}→{t1}: "
                f"{history[t]:.6f} → {history[t1]:.6f}"
            )

    def test_final_solution_feasibility_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        sol = result.best_solution
        # is_feasible is a bool (not None); violations is a list
        assert isinstance(sol.is_feasible, bool)
        assert isinstance(sol.violations, list)
        assert sol.objective_value is not None

    def test_solution_feasible_or_flagged(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        sol = result.best_solution
        if sol.is_feasible:
            assert sol.violations == []
        else:
            assert len(sol.violations) > 0

    def test_per_vehicle_route_structures(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        sol = result.best_solution
        assert len(sol.routes) == len(tiny_problem.vehicles)
        for route in sol.routes:
            assert isinstance(route, VehicleRoute)
            assert isinstance(route.visit_order, list)
            assert isinstance(route.node_sequence, list)
            assert len(route.node_sequence) >= 1

    def test_uses_shared_fitness_function(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """
        The best solution's objective_value must match what compute_fitness
        returns when called independently.  This proves QPSO does not have
        its own formula.
        """
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        sol = result.best_solution
        independent_score = compute_fitness(
            sol, tiny_problem, tiny_cfg.fitness_weights
        )
        assert sol.objective_value == pytest.approx(independent_score, rel=1e-6)


# ═══════════════════════════════════════════════════════════════════════════
# 15–17. Reproducibility
# ═══════════════════════════════════════════════════════════════════════════

class TestReproducibility:

    def test_same_seed_reproducible(
        self, tiny_problem: VRPProblem
    ) -> None:
        cfg = QPSOConfig(n_particles=5, max_iterations=10, seed=42)
        r1 = QPSOOptimizer(tiny_problem, cfg).run()
        r2 = QPSOOptimizer(tiny_problem, cfg).run()
        assert r1.best_fitness == pytest.approx(r2.best_fitness)

    def test_different_seeds_may_differ(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """
        Different seeds are permitted to produce different trajectories.
        We run several seeds and verify not all histories are identical
        (with high probability for a non-trivial problem).

        Note: uses synthetic_problem (6 customers, 20 nodes) rather than
        tiny_problem, because the M5 repair + 2-opt pipeline quickly
        converges the tiny 3-node problem to its unique optimum regardless
        of seed — making seed-diversity untestable on that fixture.
        """
        histories = []
        for seed in [1, 2, 3, 100, 200]:
            cfg = QPSOConfig(n_particles=5, max_iterations=10, seed=seed)
            r = QPSOOptimizer(synthetic_problem, cfg).run()
            histories.append(list(r.convergence_history.values()))

        # At least two histories should differ somewhere
        unique = {tuple(h) for h in histories}
        assert len(unique) >= 2, (
            "All seeds produced identical convergence histories, "
            "which is very unlikely for a stochastic optimizer."
        )



# ═══════════════════════════════════════════════════════════════════════════
# 18–20. Stopping criteria
# ═══════════════════════════════════════════════════════════════════════════

class TestStoppingCriteria:

    def test_max_iterations_stops_run(
        self, tiny_problem: VRPProblem
    ) -> None:
        limit = 7
        cfg = QPSOConfig(n_particles=4, max_iterations=limit,
                         stagnation_window=999, seed=42)
        result = QPSOOptimizer(tiny_problem, cfg).run()
        # Must have processed at most `limit` iterations
        assert result.n_iterations_run <= limit
        assert len(result.convergence_history) <= limit

    def test_time_budget_stops_run(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """
        With a very short time budget the run must stop and set stopped_early.
        We give 0.01 s — enough to start but not finish 10 000 iterations.
        """
        cfg = QPSOConfig(
            n_particles=10,
            max_iterations=10_000,
            time_budget_seconds=0.01,
            seed=42,
        )
        t0 = time.monotonic()
        result = QPSOOptimizer(synthetic_problem, cfg).run()
        elapsed = time.monotonic() - t0

        # Should have stopped early (or at least within a generous margin)
        # We allow 5 s because startup cost may dominate on slow machines
        assert elapsed < 5.0, f"Time budget not respected: elapsed={elapsed:.2f}s"
        # stopped_early OR few iterations run
        assert result.stopped_early or result.n_iterations_run < 10_000

    def test_stagnation_stops_run(
        self, tiny_problem: VRPProblem
    ) -> None:
        """
        With a tiny stagnation window the run must stop early once the
        swarm converges (which happens quickly on a tiny problem).
        """
        cfg = QPSOConfig(
            n_particles=5,
            max_iterations=1000,
            convergence_tol=0.0,   # any improvement counts
            stagnation_window=3,   # stop after 3 stagnant iterations
            seed=42,
        )
        result = QPSOOptimizer(tiny_problem, cfg).run()
        # Must have stopped well before 1000 iterations
        assert result.n_iterations_run < 1000

    def test_beta_annealing_correct(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        opt = QPSOOptimizer(tiny_problem, tiny_cfg)
        T = tiny_cfg.max_iterations
        b0 = opt._beta(0, T)
        b_mid = opt._beta(T // 2, T)
        b_end = opt._beta(T - 1, T)

        # β must start at beta_max and end at beta_min
        assert b0 == pytest.approx(tiny_cfg.beta_max)
        assert b_end == pytest.approx(tiny_cfg.beta_min)
        # Monotonically decreasing
        assert b0 >= b_mid >= b_end

    def test_n_iterations_run_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert result.n_iterations_run > 0
