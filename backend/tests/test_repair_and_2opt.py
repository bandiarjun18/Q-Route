"""
tests/test_repair_and_2opt.py – Unit tests for Milestone 5 constraint repair
and 2-opt local search.

Coverage
--------
A. Capacity repair – fixable violation
   A1. Overflow customer is moved to the vehicle with slack.
   A2. No customer is lost after repair.
   A3. No customer is duplicated after repair.
   A4. All capacity constraints are satisfied after repair.

B. Capacity repair – unfixable violation
   B1. Repair does not falsely clear an unfixable violation.
   B2. compute_fitness still returns a finite (penalised) value.

C. 2-opt improvement
   C1. two_opt returns a solution with strictly lower cost on a known
       suboptimal route.

D. 2-opt safety
   D1. two_opt never returns a route with higher cost than the input.
   D2. two_opt never returns an infeasible route when the input is feasible.
   D3. two_opt with a single-customer route is a no-op.

E. Pipeline integration
   E1. decode → repair → 2-opt runs without exception on the synthetic VRP.
   E2. The final solution has all VRPSolution fields populated.

F. Full optimizer regression
   F1. QPSOOptimizer.run() produces a finite fitness on the synthetic problem.
   F2. Convergence history remains non-increasing.
   F3. best_solution has is_feasible / violations / objective_value set.
   F4. pre_repair_fitness and post_repair_fitness are populated.
   F5. pre_repair_fitness >= post_repair_fitness >= best_fitness (pipeline only
       improves or maintains fitness).

Run from backend/ directory:
    python -m pytest tests/test_repair_and_2opt.py -v
"""

from __future__ import annotations

import math

import pytest

from app.graph.model import TransportGraph
from app.qpso.config import QPSOConfig
from app.qpso.local_search import two_opt
from app.qpso.optimizer import QPSOOptimizer, QPSOResult
from app.qpso.repair import repair_capacity
from app.qpso.representation import _build_node_sequence, decode, encode_random
from app.vrp.feasibility import check_feasibility
from app.vrp.generator import generate_vrp_instance
from app.vrp.models import Customer, Vehicle, VehicleRoute, VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness


# =============================================================================
# Shared fixtures
# =============================================================================

@pytest.fixture()
def square_graph() -> TransportGraph:
    """
    4-node graph arranged at the corners of a unit square.

    Node layout (x, y):
        0 (depot)  at (0, 0)
        1 (customer) at (1, 0)
        2 (customer) at (0, 1)
        3 (customer) at (1, 1)

    All pairs are connected with direct edges in both directions.
    Distances are Euclidean; base_travel_time = distance; congestion = 1.0.
    """
    tg = TransportGraph()
    positions = {0: (0.0, 0.0), 1: (1.0, 0.0), 2: (0.0, 1.0), 3: (1.0, 1.0)}
    node_types = {0: "depot", 1: "customer", 2: "customer", 3: "customer"}

    for nid, (x, y) in positions.items():
        tg.add_node(nid, node_type=node_types[nid], x=x, y=y)

    import math as _math
    for u in range(4):
        for v in range(4):
            if u == v:
                continue
            xu, yu = positions[u]
            xv, yv = positions[v]
            dist = round(_math.sqrt((xu - xv) ** 2 + (yu - yv) ** 2), 6)
            tg.add_edge(
                u, v,
                distance=dist,
                base_travel_time=dist,
                congestion_factor=1.0,
            )
    return tg


@pytest.fixture()
def synthetic_problem() -> VRPProblem:
    """Standard synthetic VRP used throughout milestone tests."""
    return generate_vrp_instance(n_vehicles=2, n_customers=6, n_nodes=20, seed=42)


@pytest.fixture()
def tiny_weights() -> FitnessWeights:
    """Weights that make cost purely travel-time (no distance, no congestion)."""
    return FitnessWeights(wT=1.0, wD=0.0, wC=0.0)


# =============================================================================
# A. Capacity repair – fixable violation
# =============================================================================

class TestCapacityRepairFixable:
    """
    Scenario:
        V0 (capacity=10) is assigned all three customers (total demand=18).
        V1 (capacity=20) is idle.
        Repair should move the largest customer (C0, demand=8) to V1,
        leaving V0 with C1+C2 = 10 which exactly fills its capacity.
    """

    @pytest.fixture()
    def overloaded_problem(self, square_graph: TransportGraph) -> VRPProblem:
        vehicles = [
            Vehicle(vehicle_id=0, capacity=10.0, depot_node=0),
            Vehicle(vehicle_id=1, capacity=20.0, depot_node=0),
        ]
        customers = [
            Customer(customer_id=0, location_node=1, demand=8.0),
            Customer(customer_id=1, location_node=2, demand=6.0),
            Customer(customer_id=2, location_node=3, demand=4.0),
        ]
        return VRPProblem(graph=square_graph, vehicles=vehicles, customers=customers)

    @pytest.fixture()
    def overloaded_solution(
        self, overloaded_problem: VRPProblem
    ) -> VRPSolution:
        """V0 carries ALL three customers (demand 18 > capacity 10). V1 is idle."""
        cust_by_id = overloaded_problem.customer_by_id
        customers_on_v0 = [cust_by_id[0], cust_by_id[1], cust_by_id[2]]
        seq_v0 = _build_node_sequence(0, customers_on_v0, overloaded_problem.graph)
        seq_v1 = _build_node_sequence(0, [], overloaded_problem.graph)
        return VRPSolution(routes=[
            VehicleRoute(vehicle_id=0, depot_node=0,
                         visit_order=[0, 1, 2], node_sequence=seq_v0),
            VehicleRoute(vehicle_id=1, depot_node=0,
                         visit_order=[],       node_sequence=seq_v1),
        ])

    def test_repaired_solution_no_missing_customers(
        self, overloaded_solution: VRPSolution, overloaded_problem: VRPProblem
    ) -> None:
        """All customer IDs must still appear exactly once after repair."""
        repaired = repair_capacity(overloaded_solution, overloaded_problem)
        served = []
        for route in repaired.routes:
            served.extend(route.visit_order)
        assert sorted(served) == sorted(
            c.customer_id for c in overloaded_problem.customers
        )

    def test_repaired_solution_no_duplicates(
        self, overloaded_solution: VRPSolution, overloaded_problem: VRPProblem
    ) -> None:
        """No customer may appear in more than one route."""
        repaired = repair_capacity(overloaded_solution, overloaded_problem)
        served = []
        for route in repaired.routes:
            served.extend(route.visit_order)
        assert len(served) == len(set(served))

    def test_repaired_solution_capacity_respected(
        self, overloaded_solution: VRPSolution, overloaded_problem: VRPProblem
    ) -> None:
        """After repair, no vehicle should exceed its capacity."""
        repaired = repair_capacity(overloaded_solution, overloaded_problem)
        vehicle_by_id = {v.vehicle_id: v for v in overloaded_problem.vehicles}
        cust_by_id = overloaded_problem.customer_by_id
        for route in repaired.routes:
            veh = vehicle_by_id[route.vehicle_id]
            load = sum(cust_by_id[cid].demand for cid in route.visit_order)
            assert load <= veh.capacity + 1e-9, (
                f"Vehicle {route.vehicle_id} still over capacity: "
                f"load={load:.4f} > cap={veh.capacity}"
            )

    def test_largest_customer_moved_first(
        self, overloaded_solution: VRPSolution, overloaded_problem: VRPProblem
    ) -> None:
        """Repair sorts by demand desc: C0 (demand=8) is moved to V1 first."""
        repaired = repair_capacity(overloaded_solution, overloaded_problem)
        # C0 should be on V1 (the vehicle with slack)
        v1_route = next(r for r in repaired.routes if r.vehicle_id == 1)
        assert 0 in v1_route.visit_order, (
            "C0 (largest demand) should have been moved to V1"
        )

    def test_input_solution_not_mutated(
        self, overloaded_solution: VRPSolution, overloaded_problem: VRPProblem
    ) -> None:
        """repair_capacity must not mutate the original solution."""
        original_v0_visit = list(overloaded_solution.routes[0].visit_order)
        repair_capacity(overloaded_solution, overloaded_problem)
        assert overloaded_solution.routes[0].visit_order == original_v0_visit


# =============================================================================
# B. Capacity repair – unfixable violation
# =============================================================================

class TestCapacityRepairUnfixable:
    """
    Scenario:
        V0 (capacity=5) has three customers each with demand=4 (total=12).
        V1 (capacity=3) cannot absorb any customer (would need 4 <= 3 – false).
        Repair cannot fix this; the violation must persist.
    """

    @pytest.fixture()
    def tight_problem(self, square_graph: TransportGraph) -> VRPProblem:
        vehicles = [
            Vehicle(vehicle_id=0, capacity=5.0, depot_node=0),
            Vehicle(vehicle_id=1, capacity=3.0, depot_node=0),
        ]
        customers = [
            Customer(customer_id=0, location_node=1, demand=4.0),
            Customer(customer_id=1, location_node=2, demand=4.0),
            Customer(customer_id=2, location_node=3, demand=4.0),
        ]
        return VRPProblem(graph=square_graph, vehicles=vehicles, customers=customers)

    @pytest.fixture()
    def unfixable_solution(self, tight_problem: VRPProblem) -> VRPSolution:
        """V0 carries all three customers; V1 is idle. No vehicle can help."""
        cust_by_id = tight_problem.customer_by_id
        customers_on_v0 = [cust_by_id[0], cust_by_id[1], cust_by_id[2]]
        seq_v0 = _build_node_sequence(0, customers_on_v0, tight_problem.graph)
        seq_v1 = _build_node_sequence(0, [], tight_problem.graph)
        return VRPSolution(routes=[
            VehicleRoute(vehicle_id=0, depot_node=0,
                         visit_order=[0, 1, 2], node_sequence=seq_v0),
            VehicleRoute(vehicle_id=1, depot_node=0,
                         visit_order=[],       node_sequence=seq_v1),
        ])

    def test_repair_cannot_fix_violation(
        self, unfixable_solution: VRPSolution, tight_problem: VRPProblem
    ) -> None:
        """After repair, V0 must still be overloaded (repair couldn't help)."""
        repaired = repair_capacity(unfixable_solution, tight_problem)
        v0 = next(r for r in repaired.routes if r.vehicle_id == 0)
        load = sum(
            tight_problem.customer_by_id[cid].demand for cid in v0.visit_order
        )
        cap = next(v.capacity for v in tight_problem.vehicles if v.vehicle_id == 0)
        assert load > cap, (
            f"Violation should still exist: load={load} should exceed cap={cap}"
        )

    def test_unfixable_violation_detected_by_feasibility(
        self, unfixable_solution: VRPSolution, tight_problem: VRPProblem
    ) -> None:
        """check_feasibility must flag the remaining capacity violation."""
        repaired = repair_capacity(unfixable_solution, tight_problem)
        result = check_feasibility(repaired, tight_problem)
        assert not result.is_feasible
        assert any("capacity" in v.lower() for v in result.violations)

    def test_unfixable_fitness_is_finite_and_penalised(
        self, unfixable_solution: VRPSolution, tight_problem: VRPProblem
    ) -> None:
        """compute_fitness must return a finite penalised value (not inf)."""
        repaired = repair_capacity(unfixable_solution, tight_problem)
        fitness = compute_fitness(repaired, tight_problem)
        assert math.isfinite(fitness)
        # Must be above the plain base cost (penalty has been added).
        w = FitnessWeights()
        assert fitness > w.penalty_per_violation * 0.5  # at least partial penalty

    def test_no_customers_lost_after_unfixable_repair(
        self, unfixable_solution: VRPSolution, tight_problem: VRPProblem
    ) -> None:
        """Even when repair can't fix anything, no customers should be dropped."""
        repaired = repair_capacity(unfixable_solution, tight_problem)
        served = []
        for route in repaired.routes:
            served.extend(route.visit_order)
        assert sorted(served) == sorted(
            c.customer_id for c in tight_problem.customers
        )


# =============================================================================
# C. 2-opt improvement
# =============================================================================

class TestTwoOptImprovement:
    """
    Using the square_graph fixture, the visit order [1, 2, 3] (nodes A, B, C)
    produces a crossing route.  The optimal order is [1, 3, 2] (A, C, B) which
    has a strictly lower cost and avoids the diagonal traversal.

    With wT=1.0, wD=0.0, wC=0.0 and direct-edge Euclidean distances:
        route [A, B, C]: 0→1 (1.0) + 1→2 (√2≈1.414) + 2→3 (1.0) + 3→0 (√2≈1.414)
                       ≈ 4.828
        route [A, C, B]: 0→1 (1.0) + 1→3 (1.0) + 3→2 (1.0) + 2→0 (1.0) = 4.0
    2-opt reversal (i=1, j=2) transforms [A, B, C] → [A, C, B].
    """

    @pytest.fixture()
    def one_vehicle_problem(self, square_graph: TransportGraph) -> VRPProblem:
        """1 vehicle, 3 customers at nodes 1, 2, 3."""
        return VRPProblem(
            graph=square_graph,
            vehicles=[Vehicle(vehicle_id=0, capacity=100.0, depot_node=0)],
            customers=[
                Customer(customer_id=0, location_node=1, demand=1.0),
                Customer(customer_id=1, location_node=2, demand=1.0),
                Customer(customer_id=2, location_node=3, demand=1.0),
            ],
        )

    @pytest.fixture()
    def suboptimal_solution(
        self, one_vehicle_problem: VRPProblem
    ) -> VRPSolution:
        """
        Manually construct the suboptimal visit order [C0(node1), C1(node2), C2(node3)].
        2-opt should find that [C0, C2, C1] (nodes 1, 3, 2) is cheaper.
        """
        cust_by_id = one_vehicle_problem.customer_by_id
        order_abc = [cust_by_id[0], cust_by_id[1], cust_by_id[2]]
        seq = _build_node_sequence(0, order_abc, one_vehicle_problem.graph)
        return VRPSolution(routes=[
            VehicleRoute(
                vehicle_id=0, depot_node=0,
                visit_order=[0, 1, 2],
                node_sequence=seq,
            )
        ])

    def test_two_opt_finds_improvement(
        self,
        suboptimal_solution: VRPSolution,
        one_vehicle_problem: VRPProblem,
        tiny_weights: FitnessWeights,
    ) -> None:
        """two_opt must return a solution with strictly lower fitness."""
        initial_fit = compute_fitness(
            suboptimal_solution, one_vehicle_problem, tiny_weights
        )
        refined = two_opt(suboptimal_solution, one_vehicle_problem, tiny_weights)
        refined_fit = compute_fitness(refined, one_vehicle_problem, tiny_weights)
        assert refined_fit < initial_fit - 1e-9, (
            f"Expected two_opt to improve: initial={initial_fit:.6f}, "
            f"refined={refined_fit:.6f}"
        )

    def test_two_opt_resulting_visit_order_covers_all_customers(
        self,
        suboptimal_solution: VRPSolution,
        one_vehicle_problem: VRPProblem,
        tiny_weights: FitnessWeights,
    ) -> None:
        """After 2-opt, all customers must still be served."""
        refined = two_opt(suboptimal_solution, one_vehicle_problem, tiny_weights)
        served = []
        for route in refined.routes:
            served.extend(route.visit_order)
        assert sorted(served) == sorted(
            c.customer_id for c in one_vehicle_problem.customers
        )

    def test_two_opt_optimal_order_matches_expected(
        self,
        suboptimal_solution: VRPSolution,
        one_vehicle_problem: VRPProblem,
        tiny_weights: FitnessWeights,
    ) -> None:
        """
        With the square graph and travel-time-only weights, the optimal
        visit order for a single vehicle serving nodes 1, 2, 3 from depot 0
        must achieve a total route cost of 4.0 (all unit-length edges).
        """
        refined = two_opt(suboptimal_solution, one_vehicle_problem, tiny_weights)
        route = refined.routes[0]
        from app.vrp.objective import route_components
        t, _d, _c = route_components(one_vehicle_problem.graph, route.node_sequence)
        # wT=1.0, wD=0.0 so cost = travel_time = route distance
        assert abs(t - 4.0) < 1e-6, (
            f"Expected optimal route cost 4.0, got {t:.6f}"
        )


# =============================================================================
# D. 2-opt safety
# =============================================================================

class TestTwoOptSafety:

    @pytest.fixture()
    def feasible_problem(self, square_graph: TransportGraph) -> VRPProblem:
        """2 vehicles, 2 customers — comfortable capacity."""
        return VRPProblem(
            graph=square_graph,
            vehicles=[
                Vehicle(vehicle_id=0, capacity=50.0, depot_node=0),
                Vehicle(vehicle_id=1, capacity=50.0, depot_node=0),
            ],
            customers=[
                Customer(customer_id=0, location_node=1, demand=5.0),
                Customer(customer_id=1, location_node=3, demand=5.0),
            ],
        )

    @pytest.fixture()
    def feasible_solution(self, feasible_problem: VRPProblem) -> VRPSolution:
        """One customer per vehicle — already feasible."""
        cust_by_id = feasible_problem.customer_by_id
        seq0 = _build_node_sequence(0, [cust_by_id[0]], feasible_problem.graph)
        seq1 = _build_node_sequence(0, [cust_by_id[1]], feasible_problem.graph)
        return VRPSolution(routes=[
            VehicleRoute(vehicle_id=0, depot_node=0,
                         visit_order=[0], node_sequence=seq0),
            VehicleRoute(vehicle_id=1, depot_node=0,
                         visit_order=[1], node_sequence=seq1),
        ])

    def test_two_opt_never_worsens_feasible_solution(
        self, feasible_solution: VRPSolution, feasible_problem: VRPProblem
    ) -> None:
        """two_opt output fitness must be ≤ input fitness."""
        w = FitnessWeights()
        initial_fit = compute_fitness(feasible_solution, feasible_problem, w)
        refined = two_opt(feasible_solution, feasible_problem, w)
        refined_fit = compute_fitness(refined, feasible_problem, w)
        assert refined_fit <= initial_fit + 1e-9, (
            f"two_opt worsened solution: {initial_fit:.6f} → {refined_fit:.6f}"
        )

    def test_two_opt_preserves_feasibility(
        self, feasible_solution: VRPSolution, feasible_problem: VRPProblem
    ) -> None:
        """An input-feasible solution must stay feasible after two_opt."""
        # Verify input IS feasible.
        assert check_feasibility(feasible_solution, feasible_problem).is_feasible
        refined = two_opt(feasible_solution, feasible_problem)
        result = check_feasibility(refined, feasible_problem)
        assert result.is_feasible, (
            f"two_opt produced infeasible solution: {result.violations}"
        )

    def test_two_opt_single_customer_route_unchanged(
        self, square_graph: TransportGraph
    ) -> None:
        """A route with exactly one customer has no valid 2-opt reversal."""
        problem = VRPProblem(
            graph=square_graph,
            vehicles=[Vehicle(vehicle_id=0, capacity=50.0, depot_node=0)],
            customers=[Customer(customer_id=0, location_node=1, demand=1.0)],
        )
        cust = problem.customers[0]
        seq = _build_node_sequence(0, [cust], problem.graph)
        initial_sol = VRPSolution(routes=[
            VehicleRoute(vehicle_id=0, depot_node=0,
                         visit_order=[0], node_sequence=seq),
        ])
        refined = two_opt(initial_sol, problem)
        # visit_order must be unchanged (nothing to reverse)
        assert refined.routes[0].visit_order == [0]

    def test_two_opt_does_not_mutate_input(
        self, feasible_solution: VRPSolution, feasible_problem: VRPProblem
    ) -> None:
        """two_opt must return a new solution without mutating the input."""
        original_order = list(feasible_solution.routes[0].visit_order)
        two_opt(feasible_solution, feasible_problem)
        assert feasible_solution.routes[0].visit_order == original_order


# =============================================================================
# E. Pipeline integration
# =============================================================================

class TestPipelineIntegration:

    def test_pipeline_runs_without_exception(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """decode → repair → 2-opt must complete without raising."""
        import numpy as np
        rng = np.random.default_rng(42)
        n = len(synthetic_problem.customers)
        keys = encode_random(n, rng)
        sol = decode(keys, synthetic_problem)
        repaired = repair_capacity(sol, synthetic_problem)
        refined = two_opt(repaired, synthetic_problem)
        assert refined is not None

    def test_pipeline_covers_all_customers(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """All customers must be served exactly once after the full pipeline."""
        import numpy as np
        rng = np.random.default_rng(0)
        n = len(synthetic_problem.customers)
        keys = encode_random(n, rng)
        sol = decode(keys, synthetic_problem)
        repaired = repair_capacity(sol, synthetic_problem)
        refined = two_opt(repaired, synthetic_problem)

        served = []
        for route in refined.routes:
            served.extend(route.visit_order)
        assert sorted(served) == sorted(
            c.customer_id for c in synthetic_problem.customers
        )

    def test_pipeline_result_has_correct_route_count(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """Exactly one route per vehicle must be present."""
        import numpy as np
        rng = np.random.default_rng(7)
        n = len(synthetic_problem.customers)
        keys = encode_random(n, rng)
        sol = decode(keys, synthetic_problem)
        repaired = repair_capacity(sol, synthetic_problem)
        refined = two_opt(repaired, synthetic_problem)
        assert len(refined.routes) == len(synthetic_problem.vehicles)

    def test_pipeline_fitness_is_finite(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """The final pipeline solution must have finite fitness."""
        import numpy as np
        rng = np.random.default_rng(99)
        n = len(synthetic_problem.customers)
        keys = encode_random(n, rng)
        sol = decode(keys, synthetic_problem)
        repaired = repair_capacity(sol, synthetic_problem)
        refined = two_opt(repaired, synthetic_problem)
        fitness = compute_fitness(refined, synthetic_problem)
        assert math.isfinite(fitness)


# =============================================================================
# F. Full optimizer regression (Milestone 4 properties must be preserved)
# =============================================================================

class TestOptimizerRegression:

    @pytest.fixture()
    def tiny_cfg(self) -> QPSOConfig:
        return QPSOConfig(n_particles=5, max_iterations=10, seed=42)

    @pytest.fixture()
    def tiny_problem(self, square_graph: TransportGraph) -> VRPProblem:
        return VRPProblem(
            graph=square_graph,
            vehicles=[
                Vehicle(vehicle_id=0, capacity=50.0, depot_node=0),
                Vehicle(vehicle_id=1, capacity=50.0, depot_node=0),
            ],
            customers=[
                Customer(customer_id=0, location_node=1, demand=5.0),
                Customer(customer_id=1, location_node=2, demand=5.0),
                Customer(customer_id=2, location_node=3, demand=5.0),
            ],
        )

    def test_optimizer_best_fitness_finite(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert math.isfinite(result.best_fitness)

    def test_optimizer_convergence_non_increasing(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        history = result.convergence_history
        iters = sorted(history.keys())
        for i in range(len(iters) - 1):
            t, t1 = iters[i], iters[i + 1]
            assert history[t] >= history[t1] - 1e-9, (
                f"Convergence increased: iteration {t}→{t1}: "
                f"{history[t]:.6f} → {history[t1]:.6f}"
            )

    def test_optimizer_best_solution_fields_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        sol = result.best_solution
        assert isinstance(sol.is_feasible, bool)
        assert isinstance(sol.violations, list)
        assert sol.objective_value is not None
        assert math.isfinite(sol.objective_value)

    def test_optimizer_pre_repair_fitness_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """New M5 field: pre_repair_fitness must be a finite float."""
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert result.pre_repair_fitness is not None
        assert math.isfinite(result.pre_repair_fitness)

    def test_optimizer_post_repair_fitness_populated(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """New M5 field: post_repair_fitness must be a finite float."""
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        assert result.post_repair_fitness is not None
        assert math.isfinite(result.post_repair_fitness)

    def test_pipeline_only_improves_fitness(
        self, tiny_problem: VRPProblem, tiny_cfg: QPSOConfig
    ) -> None:
        """
        For the globally best particle:
            pre_repair_fitness >= post_repair_fitness >= best_fitness
        Each stage can only improve or maintain fitness, never worsen it.
        """
        result = QPSOOptimizer(tiny_problem, tiny_cfg).run()
        pre = result.pre_repair_fitness
        post = result.post_repair_fitness
        final = result.best_fitness
        assert pre is not None and post is not None
        assert post <= pre + 1e-9, (
            f"Repair worsened fitness: pre={pre:.6f}, post={post:.6f}"
        )
        assert final <= post + 1e-9, (
            f"2-opt worsened fitness: post_repair={post:.6f}, final={final:.6f}"
        )

    def test_optimizer_synthetic_scenario(
        self, synthetic_problem: VRPProblem
    ) -> None:
        """Full optimizer run on the standard synthetic VRP."""
        cfg = QPSOConfig(n_particles=10, max_iterations=20, seed=42)
        result = QPSOOptimizer(synthetic_problem, cfg).run()
        assert math.isfinite(result.best_fitness)
        assert len(result.convergence_history) > 0
        assert result.n_iterations_run > 0
