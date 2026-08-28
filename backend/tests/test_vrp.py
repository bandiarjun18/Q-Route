"""
tests/test_vrp.py – Unit tests for the Q-Route VRP engine (Milestone 3).

Coverage
--------
1. Models            – Vehicle / Customer / VRPProblem field validation,
                       VehicleRoute / VRPSolution structure.
2. Generator         – synthetic VRP instance creation, JSON round-trip,
                       reproducibility, configurable counts.
3. Feasibility       – one test per constraint:
                       a. Known-feasible solution passes (all clear)
                       b. Capacity violation detected
                       c. Missing customer detected
                       d. Closed-road usage detected
                       e. Depot constraint violated (wrong start / wrong end)
                       f. Disconnected / invalid route segment detected
4. Objective         – fitness value on a known route, configurable weights,
                       penalty added for infeasible solutions.

Run from backend/ directory:
    python -m pytest tests/test_vrp.py -v
"""

from __future__ import annotations

import json
import math

import pytest

from app.graph.model import TransportGraph, WeightConfig
from app.vrp.models import (
    Vehicle,
    Customer,
    VRPProblem,
    VehicleRoute,
    VRPSolution,
)
from app.vrp.feasibility import check_feasibility, FeasibilityResult
from app.vrp.objective import compute_fitness, FitnessWeights, route_components
from app.vrp.generator import (
    generate_vrp_instance,
    save_vrp_json,
    load_vrp_json,
    vrp_problem_to_dict,
    vrp_problem_from_dict,
)


# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def simple_graph() -> TransportGraph:
    """
    Small, deterministic graph for VRP tests.

    Topology (all edges open, bidirectional):

        depot(0) ──2km──► A(1) ──3km──► B(2) ──2km──► depot(0)
                    │                           ▲
                    └──────────5km──────────────┘

    All edges: distance = as labelled, base_travel_time = distance/2 min,
               congestion_factor = 1.0.
    """
    tg = TransportGraph()
    tg.add_node(0, node_type="depot",    x=0.0, y=0.0)
    tg.add_node(1, node_type="customer", x=2.0, y=0.0)
    tg.add_node(2, node_type="customer", x=5.0, y=0.0)

    def add_bi(u, v, dist):
        tg.add_edge(u, v, distance=dist, base_travel_time=dist / 2.0, congestion_factor=1.0)
        tg.add_edge(v, u, distance=dist, base_travel_time=dist / 2.0, congestion_factor=1.0)

    add_bi(0, 1, 2.0)
    add_bi(1, 2, 3.0)
    add_bi(0, 2, 5.0)

    return tg


@pytest.fixture()
def simple_problem(simple_graph: TransportGraph) -> VRPProblem:
    """
    Two-vehicle, two-customer VRP problem on simple_graph.

    Vehicle 0: capacity 20, depot 0
    Vehicle 1: capacity 20, depot 0
    Customer 0: node 1, demand 5
    Customer 1: node 2, demand 5
    """
    vehicles = [
        Vehicle(vehicle_id=0, capacity=20.0, depot_node=0),
        Vehicle(vehicle_id=1, capacity=20.0, depot_node=0),
    ]
    customers = [
        Customer(customer_id=0, location_node=1, demand=5.0),
        Customer(customer_id=1, location_node=2, demand=5.0),
    ]
    return VRPProblem(graph=simple_graph, vehicles=vehicles, customers=customers)


@pytest.fixture()
def feasible_solution(simple_problem: VRPProblem) -> VRPSolution:
    """
    A known-feasible solution to simple_problem.

    Vehicle 0 serves customer 0 (node 1): [0, 1, 0]
    Vehicle 1 serves customer 1 (node 2): [0, 2, 0]
    """
    routes = [
        VehicleRoute(
            vehicle_id=0,
            depot_node=0,
            visit_order=[0],          # customer_id 0
            node_sequence=[0, 1, 0],  # depot → cust-0-node → depot
        ),
        VehicleRoute(
            vehicle_id=1,
            depot_node=0,
            visit_order=[1],          # customer_id 1
            node_sequence=[0, 2, 0],  # depot → cust-1-node → depot
        ),
    ]
    return VRPSolution(routes=routes)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Model tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVRPModels:

    def test_vehicle_fields(self) -> None:
        v = Vehicle(vehicle_id="V1", capacity=50.0, depot_node=0)
        assert v.vehicle_id == "V1"
        assert v.capacity == pytest.approx(50.0)
        assert v.depot_node == 0

    def test_vehicle_zero_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            Vehicle(vehicle_id=0, capacity=0.0, depot_node=0)

    def test_vehicle_negative_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            Vehicle(vehicle_id=0, capacity=-5.0, depot_node=0)

    def test_customer_fields(self) -> None:
        c = Customer(customer_id="C3", location_node=7, demand=8.5)
        assert c.customer_id == "C3"
        assert c.location_node == 7
        assert c.demand == pytest.approx(8.5)

    def test_customer_negative_demand_raises(self) -> None:
        with pytest.raises(ValueError, match="demand"):
            Customer(customer_id=0, location_node=1, demand=-1.0)

    def test_customer_zero_demand_ok(self) -> None:
        c = Customer(customer_id=0, location_node=1, demand=0.0)
        assert c.demand == pytest.approx(0.0)

    def test_vrp_problem_requires_vehicles(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="vehicle"):
            VRPProblem(
                graph=simple_graph,
                vehicles=[],
                customers=[Customer(0, 1, 5.0)],
            )

    def test_vrp_problem_requires_customers(self, simple_graph: TransportGraph) -> None:
        with pytest.raises(ValueError, match="customer"):
            VRPProblem(
                graph=simple_graph,
                vehicles=[Vehicle(0, 20.0, 0)],
                customers=[],
            )

    def test_vrp_problem_customer_ids(self, simple_problem: VRPProblem) -> None:
        assert simple_problem.customer_ids == frozenset({0, 1})

    def test_vrp_problem_customer_by_id(self, simple_problem: VRPProblem) -> None:
        mapping = simple_problem.customer_by_id
        assert mapping[0].location_node == 1
        assert mapping[1].location_node == 2

    def test_vehicle_route_auto_fill_sequence(self) -> None:
        """Empty node_sequence should auto-fill to [depot, depot]."""
        route = VehicleRoute(vehicle_id=0, depot_node=99, visit_order=[])
        assert route.node_sequence == [99, 99]

    def test_vrp_solution_defaults(self) -> None:
        sol = VRPSolution()
        assert sol.routes == []
        assert sol.is_feasible is False
        assert sol.objective_value is None
        assert sol.violations == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Generator tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVRPGenerator:

    def test_vehicle_count(self) -> None:
        problem = generate_vrp_instance(n_vehicles=3, n_customers=5, seed=42)
        assert len(problem.vehicles) == 3

    def test_customer_count(self) -> None:
        problem = generate_vrp_instance(n_vehicles=2, n_customers=7, seed=42)
        assert len(problem.customers) == 7

    def test_vehicle_ids_unique(self) -> None:
        problem = generate_vrp_instance(n_vehicles=4, seed=42)
        ids = [v.vehicle_id for v in problem.vehicles]
        assert len(ids) == len(set(ids))

    def test_customer_ids_unique(self) -> None:
        problem = generate_vrp_instance(n_customers=8, seed=42)
        ids = [c.customer_id for c in problem.customers]
        assert len(ids) == len(set(ids))

    def test_depots_assigned(self) -> None:
        """All vehicle depots must be nodes in the graph."""
        problem = generate_vrp_instance(seed=42)
        g = problem.graph.graph
        for v in problem.vehicles:
            assert g.has_node(v.depot_node), (
                f"Vehicle {v.vehicle_id} depot {v.depot_node} not in graph"
            )

    def test_customer_nodes_in_graph(self) -> None:
        problem = generate_vrp_instance(seed=42)
        g = problem.graph.graph
        for c in problem.customers:
            assert g.has_node(c.location_node), (
                f"Customer {c.customer_id} node {c.location_node} not in graph"
            )

    def test_demands_in_range(self) -> None:
        problem = generate_vrp_instance(
            demand_min=2.0, demand_max=8.0, seed=99
        )
        for c in problem.customers:
            assert 2.0 <= c.demand <= 8.0, (
                f"Customer {c.customer_id} demand {c.demand} out of [2, 8]"
            )

    def test_reproducible_same_seed(self) -> None:
        p1 = generate_vrp_instance(seed=77)
        p2 = generate_vrp_instance(seed=77)
        assert [c.demand for c in p1.customers] == [c.demand for c in p2.customers]
        assert [c.location_node for c in p1.customers] == [
            c.location_node for c in p2.customers
        ]

    def test_different_seeds_differ(self) -> None:
        p1 = generate_vrp_instance(seed=1)
        p2 = generate_vrp_instance(seed=2)
        demands_1 = [c.demand for c in p1.customers]
        demands_2 = [c.demand for c in p2.customers]
        assert demands_1 != demands_2

    def test_json_round_trip(self, tmp_path) -> None:
        problem = generate_vrp_instance(n_vehicles=2, n_customers=4, seed=42)
        out = tmp_path / "vrp.json"
        save_vrp_json(problem, out)
        loaded = load_vrp_json(out)

        assert len(loaded.vehicles) == len(problem.vehicles)
        assert len(loaded.customers) == len(problem.customers)
        assert loaded.graph.node_count() == problem.graph.node_count()
        assert loaded.graph.edge_count() == problem.graph.edge_count()

    def test_json_fields_present(self, tmp_path) -> None:
        problem = generate_vrp_instance(seed=42)
        out = tmp_path / "vrp.json"
        save_vrp_json(problem, out)
        raw = json.loads(out.read_text(encoding="utf-8"))
        for key in ("meta", "graph", "vehicles", "customers"):
            assert key in raw, f"Missing key: {key}"

    def test_to_dict_from_dict_round_trip(self) -> None:
        problem = generate_vrp_instance(seed=42)
        d = vrp_problem_to_dict(problem)
        restored = vrp_problem_from_dict(d)
        assert len(restored.vehicles) == len(problem.vehicles)
        assert len(restored.customers) == len(problem.customers)

    def test_saves_to_data_dir(self, tmp_path) -> None:
        problem = generate_vrp_instance(seed=42)
        out = tmp_path / "data" / "test_vrp.json"
        saved = save_vrp_json(problem, out)
        assert saved.exists()

    def test_custom_graph_accepted(self, simple_graph: TransportGraph) -> None:
        """Generator accepts a pre-built TransportGraph."""
        problem = generate_vrp_instance(
            n_vehicles=1,
            n_customers=2,
            graph=simple_graph,
            seed=42,
        )
        assert problem.graph is simple_graph
        assert len(problem.customers) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 3. Feasibility checker tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFeasibilityChecker:

    # ── 3a. Known-feasible solution passes ──────────────────────────────────

    def test_feasible_solution_passes(
        self,
        feasible_solution: VRPSolution,
        simple_problem: VRPProblem,
    ) -> None:
        result = check_feasibility(feasible_solution, simple_problem)
        assert result.is_feasible is True
        assert result.violations == []

    # ── 3b. Capacity violation ───────────────────────────────────────────────

    def test_capacity_violation_detected(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """Assign both customers to a vehicle with capacity 4 < total demand 10."""
        small_vehicle = Vehicle(vehicle_id=0, capacity=4.0, depot_node=0)
        idle_vehicle = Vehicle(vehicle_id=1, capacity=100.0, depot_node=0)
        problem = VRPProblem(
            graph=simple_problem.graph,
            vehicles=[small_vehicle, idle_vehicle],
            customers=simple_problem.customers,
        )
        # Vehicle 0 gets both customers (demand 5+5=10 > capacity 4)
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0, 1],           # both customers
                node_sequence=[0, 1, 2, 0],   # depot→C0→C1→depot
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[],
                node_sequence=[0, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, problem)
        assert result.is_feasible is False
        assert any("capacity" in v.lower() for v in result.violations)

    # ── 3c. Missing required customer ───────────────────────────────────────

    def test_missing_customer_detected(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """Route that only serves customer 0 — customer 1 is missing."""
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0],           # only customer 0
                node_sequence=[0, 1, 0],
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[],            # idle — customer 1 unserved
                node_sequence=[0, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, simple_problem)
        assert result.is_feasible is False
        assert any("coverage" in v.lower() or "not served" in v.lower()
                   for v in result.violations)

    # ── 3d. Closed-road usage ───────────────────────────────────────────────

    def test_closed_road_detected(
        self,
        simple_problem: VRPProblem,
        simple_graph: TransportGraph,
    ) -> None:
        """Close edge 0→1; a route using 0→1 must be flagged."""
        simple_graph.close_edge(0, 1)
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0],
                node_sequence=[0, 1, 0],   # uses closed 0→1
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[1],
                node_sequence=[0, 2, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, simple_problem)
        assert result.is_feasible is False
        assert any("closed" in v.lower() for v in result.violations)

    # ── 3e. Depot constraint violated ───────────────────────────────────────

    def test_depot_wrong_start_detected(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """Route starts at node 1 instead of depot node 0."""
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0],
                node_sequence=[1, 0, 0],   # wrong start
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[1],
                node_sequence=[0, 2, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, simple_problem)
        assert result.is_feasible is False
        assert any("depot" in v.lower() or "start" in v.lower()
                   for v in result.violations)

    def test_depot_wrong_end_detected(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """Route ends at node 1 instead of returning to depot node 0."""
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0],
                node_sequence=[0, 1],      # does not return to depot
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[1],
                node_sequence=[0, 2, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, simple_problem)
        assert result.is_feasible is False
        assert any("depot" in v.lower() or "end" in v.lower()
                   for v in result.violations)

    # ── 3f. Disconnected / invalid route segment ────────────────────────────

    def test_disconnected_route_detected(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """node_sequence includes node 99 which doesn't exist in the graph."""
        routes = [
            VehicleRoute(
                vehicle_id=0,
                depot_node=0,
                visit_order=[0],
                node_sequence=[0, 99, 0],  # node 99 doesn't exist → no edge
            ),
            VehicleRoute(
                vehicle_id=1,
                depot_node=0,
                visit_order=[1],
                node_sequence=[0, 2, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        result = check_feasibility(solution, simple_problem)
        assert result.is_feasible is False
        assert any(
            "no edge" in v.lower() or "disconnected" in v.lower() or "invalid" in v.lower()
            for v in result.violations
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Objective function tests
# ═══════════════════════════════════════════════════════════════════════════

class TestObjectiveFunction:

    def test_route_components_known_values(
        self, simple_graph: TransportGraph
    ) -> None:
        """
        Edge 0→1: dist=2, time=1, cong=1 → eff_time=1, cong_pen=0
        Edge 1→0: dist=2, time=1, cong=1 → same
        node_sequence = [0, 1, 0]
        Expected: travel_time=2.0, distance=4.0, congestion=0.0
        """
        t, d, c = route_components(simple_graph, [0, 1, 0])
        assert t == pytest.approx(2.0)   # 1.0 + 1.0
        assert d == pytest.approx(4.0)   # 2.0 + 2.0
        assert c == pytest.approx(0.0)   # congestion_factor=1, so 0+0

    def test_route_components_single_node_zero(
        self, simple_graph: TransportGraph
    ) -> None:
        t, d, c = route_components(simple_graph, [0])
        assert t == pytest.approx(0.0)
        assert d == pytest.approx(0.0)
        assert c == pytest.approx(0.0)

    def test_route_components_closed_edge_inf(
        self, simple_graph: TransportGraph
    ) -> None:
        simple_graph.close_edge(0, 1)
        t, d, c = route_components(simple_graph, [0, 1, 0])
        assert t == math.inf
        assert d == math.inf
        assert c == math.inf

    def test_route_components_missing_edge_inf(
        self, simple_graph: TransportGraph
    ) -> None:
        t, d, c = route_components(simple_graph, [0, 99, 0])
        assert t == math.inf

    def test_fitness_feasible_solution_finite(
        self,
        feasible_solution: VRPSolution,
        simple_problem: VRPProblem,
    ) -> None:
        score = compute_fitness(feasible_solution, simple_problem)
        assert math.isfinite(score)
        assert score > 0.0

    def test_fitness_manual_calculation(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """
        Vehicle 0: [0→1→0]: 2 edges each dist=2, time=1, cong_factor=1
            travel_time = 2*1*1 = 2.0
            distance    = 2*2   = 4.0
            congestion  = 2*0   = 0.0
        Vehicle 1: [0→2→0]: 2 edges each dist=5, time=2.5, cong_factor=1
            travel_time = 2*2.5*1 = 5.0
            distance    = 2*5     = 10.0
            congestion  = 2*0     = 0.0
        Totals: time=7.0, dist=14.0, cong=0.0
        With wT=1, wD=1, wC=1, penalty=0 (feasible):
            Fitness = 1*7 + 1*14 + 1*0 = 21.0
        """
        routes = [
            VehicleRoute(
                vehicle_id=0, depot_node=0,
                visit_order=[0], node_sequence=[0, 1, 0],
            ),
            VehicleRoute(
                vehicle_id=1, depot_node=0,
                visit_order=[1], node_sequence=[0, 2, 0],
            ),
        ]
        solution = VRPSolution(routes=routes)
        weights = FitnessWeights(wT=1.0, wD=1.0, wC=1.0, penalty_per_violation=0.0)
        score = compute_fitness(solution, simple_problem, weights)
        assert score == pytest.approx(21.0)

    def test_configurable_weights_change_fitness(
        self,
        feasible_solution: VRPSolution,
        simple_problem: VRPProblem,
    ) -> None:
        """Different weight settings must produce different fitness values."""
        w1 = FitnessWeights(wT=1.0, wD=0.0, wC=0.0, penalty_per_violation=0.0)
        w2 = FitnessWeights(wT=0.0, wD=1.0, wC=0.0, penalty_per_violation=0.0)
        score1 = compute_fitness(feasible_solution, simple_problem, w1)
        score2 = compute_fitness(feasible_solution, simple_problem, w2)
        # Distance-weighted score should differ from time-weighted
        assert score1 != pytest.approx(score2)

    def test_infeasible_solution_has_penalty(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """Missing a customer should raise the fitness above the feasible baseline."""
        # Feasible
        feasible_routes = [
            VehicleRoute(0, 0, [0], [0, 1, 0]),
            VehicleRoute(1, 0, [1], [0, 2, 0]),
        ]
        feasible_sol = VRPSolution(routes=feasible_routes)

        # Infeasible: customer 1 not served
        infeasible_routes = [
            VehicleRoute(0, 0, [0], [0, 1, 0]),
            VehicleRoute(1, 0, [],  [0, 0]),
        ]
        infeasible_sol = VRPSolution(routes=infeasible_routes)

        weights = FitnessWeights(penalty_per_violation=1_000.0)
        feasible_score = compute_fitness(feasible_sol, simple_problem, weights)
        infeasible_score = compute_fitness(infeasible_sol, simple_problem, weights)

        assert infeasible_score > feasible_score

    def test_fitness_closed_road_returns_inf(
        self,
        simple_problem: VRPProblem,
        simple_graph: TransportGraph,
    ) -> None:
        """A route using a closed edge must yield math.inf fitness."""
        simple_graph.close_edge(0, 1)
        routes = [
            VehicleRoute(0, 0, [0], [0, 1, 0]),  # closed edge
            VehicleRoute(1, 0, [1], [0, 2, 0]),
        ]
        solution = VRPSolution(routes=routes)
        score = compute_fitness(solution, simple_problem)
        assert score == math.inf

    def test_fitness_weights_default_values(self) -> None:
        w = FitnessWeights()
        assert w.wT == pytest.approx(1.0)
        assert w.wD == pytest.approx(0.5)
        assert w.wC == pytest.approx(0.3)
        assert w.penalty_per_violation == pytest.approx(1_000.0)

    def test_fitness_weights_negative_penalty_raises(self) -> None:
        with pytest.raises(ValueError, match="penalty"):
            FitnessWeights(penalty_per_violation=-1.0)

    def test_fitness_none_weights_uses_defaults(
        self,
        feasible_solution: VRPSolution,
        simple_problem: VRPProblem,
    ) -> None:
        """compute_fitness(…, weights=None) must use FitnessWeights() defaults."""
        score_none = compute_fitness(feasible_solution, simple_problem, None)
        score_default = compute_fitness(
            feasible_solution, simple_problem, FitnessWeights()
        )
        assert score_none == pytest.approx(score_default)

    def test_zero_penalty_infeasible_still_finite(
        self,
        simple_problem: VRPProblem,
    ) -> None:
        """
        With penalty=0, a coverage-violation (unserved customer) still yields a
        finite score because the route components themselves are finite.

        Vehicle 1 stays at the depot using a single-node sequence so that
        route_components returns (0, 0, 0) rather than inf.  The infeasibility
        comes purely from the missing-customer coverage violation.
        """
        infeasible_routes = [
            VehicleRoute(0, 0, [0], [0, 1, 0]),
            # Vehicle 1: stays at depot — single-element sequence → zero cost
            VehicleRoute(1, 0, [], node_sequence=[0]),
        ]
        infeasible_sol = VRPSolution(routes=infeasible_routes)
        weights = FitnessWeights(penalty_per_violation=0.0)
        score = compute_fitness(infeasible_sol, simple_problem, weights)
        assert math.isfinite(score)
