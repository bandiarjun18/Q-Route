"""
experiments/comparators/exact_solver.py – Exact / Exhaustive Combinatorial Solver for small VRP instances.

Target instance size: N <= 8 customers.

Enumerates all possible customer permutations and multi-vehicle partitionings to find
the globally optimal solution under the canonical Q-Route objective function.

Safety guarantee:
- Explicitly raises ValueError if N > 8 to prevent exponential freeze.
"""

from __future__ import annotations

import itertools
import math
import time
from typing import Any

from app.qpso.local_search import two_opt
from app.qpso.repair import repair_capacity
from app.qpso.representation import _build_node_sequence
from app.vrp.feasibility import check_feasibility
from app.vrp.models import Customer, Vehicle, VehicleRoute, VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness

from .common import ComparatorResult


class ExactSolver:
    """
    Exact / Exhaustive Search Solver for small Multi-Vehicle VRP instances (N <= 8).
    """

    MAX_CUSTOMERS = 8

    def __init__(self, problem: VRPProblem, fitness_weights: FitnessWeights | None = None):
        self.problem = problem
        self.weights = fitness_weights or FitnessWeights()
        self.n_customers = len(problem.customers)

        if self.n_customers > self.MAX_CUSTOMERS:
            raise ValueError(
                f"ExactSolver is restricted to small instances with N <= {self.MAX_CUSTOMERS} customers "
                f"to prevent combinatorial explosion. Provided instance has N={self.n_customers}."
            )

    def _generate_partitions(
        self,
        elements: list[Customer],
        n_vehicles: int,
    ) -> itertools.product:
        """
        Generate all assignments of elements into n_vehicles buckets.
        Each vehicle gets an ordered list of assigned customers.
        """
        # Assign each element to vehicle index 0..n_vehicles-1
        return itertools.product(range(n_vehicles), repeat=len(elements))

    def solve(self, seed: int = 42) -> ComparatorResult:
        """
        Execute exhaustive search over all customer permutations and vehicle assignments.
        """
        start_time = time.perf_counter()

        customers = self.problem.customers
        vehicles = self.problem.vehicles
        n_v = len(vehicles)
        graph = self.problem.graph

        best_solution: VRPSolution | None = None
        best_fitness = math.inf
        total_explored = 0
        feasible_explored = 0

        convergence_history: dict[int, float] = {}

        # 1. Enumerate all permutations of customers
        for perm in itertools.permutations(customers):
            # 2. Enumerate all partitions of this permutation across vehicles
            for assignment in self._generate_partitions(list(perm), n_v):
                total_explored += 1

                # Group customers per vehicle maintaining permutation order
                v_groups: list[list[Customer]] = [[] for _ in range(n_v)]
                for cust, v_idx in zip(perm, assignment):
                    v_groups[v_idx].append(cust)

                # Check capacity bounds early
                capacity_ok = True
                for v_idx, group in enumerate(v_groups):
                    demand = sum(c.demand for c in group)
                    if demand > vehicles[v_idx].capacity:
                        capacity_ok = False
                        break

                # Build candidate routes
                routes: list[VehicleRoute] = []
                for v_idx, vehicle in enumerate(vehicles):
                    assigned = v_groups[v_idx]
                    visit_order = [c.customer_id for c in assigned]
                    node_seq = _build_node_sequence(vehicle.depot_node, assigned, graph)
                    routes.append(
                        VehicleRoute(
                            vehicle_id=vehicle.vehicle_id,
                            depot_node=vehicle.depot_node,
                            visit_order=visit_order,
                            node_sequence=node_seq,
                        )
                    )

                candidate_sol = VRPSolution(routes=routes)
                # Apply 2-opt intra-route improvement
                refined_sol = two_opt(candidate_sol, self.problem, self.weights)
                fit = compute_fitness(refined_sol, self.problem, self.weights)

                feas = check_feasibility(refined_sol, self.problem)
                if feas.is_feasible:
                    feasible_explored += 1

                if fit < best_fitness:
                    best_fitness = fit
                    best_solution = refined_sol
                    convergence_history[total_explored] = float(best_fitness)

        elapsed = time.perf_counter() - start_time

        # Fallback if no valid solution was found
        if best_solution is None:
            # Build trivial baseline
            routes = [
                VehicleRoute(
                    vehicle_id=v.vehicle_id,
                    depot_node=v.depot_node,
                    visit_order=[],
                    node_sequence=[v.depot_node],
                )
                for v in vehicles
            ]
            best_solution = VRPSolution(routes=routes)
            best_fitness = compute_fitness(best_solution, self.problem, self.weights)

        feasibility = check_feasibility(best_solution, self.problem)
        convergence_history[total_explored] = float(best_fitness)

        return ComparatorResult(
            algorithm_name="Exact_Brute_Force",
            best_solution=best_solution,
            best_fitness=float(best_fitness),
            convergence_history=convergence_history,
            runtime_seconds=elapsed,
            is_feasible=feasibility.is_feasible,
            seed=seed,
            iterations_completed=total_explored,
            extra_telemetry={
                "total_candidates_evaluated": total_explored,
                "feasible_candidates_found": feasible_explored,
                "violations": feasibility.violations,
            },
        )
