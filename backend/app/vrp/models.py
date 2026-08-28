"""
app/vrp/models.py – Core data models for Q-Route VRP.

Defines
-------
Vehicle       – a single delivery vehicle with capacity and home depot.
Customer      – a delivery stop with location and demand.
VRPProblem    – the full problem instance (graph + fleet + customers).
VehicleRoute  – a single vehicle's planned route (assignment + visit order
                + full node sequence through the graph).
VRPSolution   – a complete solution to a VRPProblem: one VehicleRoute per
                vehicle, feasibility flag, and pre-computed objective value.

Design notes
------------
- All types are plain dataclasses so they are trivially serialisable.
- No business logic lives here; feasibility checking and fitness computation
  are in feasibility.py and objective.py respectively.
- ``VehicleRoute.node_sequence`` carries the *full* list of graph node ids
  the vehicle visits, including the depot at the start and end:
      [depot, ..., cust_A, ..., cust_B, ..., depot]
  This makes road-availability and connectivity checks straightforward.
- ``VRPSolution.objective_value`` is populated by ``compute_fitness()`` and
  defaults to ``None`` until it has been evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.graph.model import TransportGraph


# ---------------------------------------------------------------------------
# Fleet / demand primitives
# ---------------------------------------------------------------------------

@dataclass
class Vehicle:
    """
    A delivery vehicle.

    Attributes
    ----------
    vehicle_id : any hashable  – unique identifier (e.g. 0, "V1")
    capacity   : float         – maximum total demand this vehicle can carry
    depot_node : any           – graph node id where this vehicle starts and
                                 must return to at the end of its route
    """

    vehicle_id: Any
    capacity: float
    depot_node: Any

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError(
                f"Vehicle {self.vehicle_id!r}: capacity must be > 0, "
                f"got {self.capacity}"
            )


@dataclass
class Customer:
    """
    A customer / delivery order.

    Attributes
    ----------
    customer_id   : any hashable – unique identifier (e.g. 0, "C3")
    location_node : any          – graph node id where delivery takes place
    demand        : float        – units of capacity consumed by this order
    """

    customer_id: Any
    location_node: Any
    demand: float

    def __post_init__(self) -> None:
        if self.demand < 0:
            raise ValueError(
                f"Customer {self.customer_id!r}: demand must be >= 0, "
                f"got {self.demand}"
            )


# ---------------------------------------------------------------------------
# Problem container
# ---------------------------------------------------------------------------

@dataclass
class VRPProblem:
    """
    A complete Multi-Vehicle VRP instance.

    Attributes
    ----------
    graph     : TransportGraph – the underlying road network
    vehicles  : list[Vehicle]  – the fleet
    customers : list[Customer] – all orders that must be served

    Helper properties
    -----------------
    customer_ids        – frozenset of all customer_id values
    customer_by_id      – dict mapping customer_id → Customer
    required_node_ids   – frozenset of all location_node values
    """

    graph: TransportGraph
    vehicles: list[Vehicle]
    customers: list[Customer]

    def __post_init__(self) -> None:
        if not self.vehicles:
            raise ValueError("VRPProblem must have at least one vehicle.")
        if not self.customers:
            raise ValueError("VRPProblem must have at least one customer.")

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def customer_ids(self) -> frozenset:
        return frozenset(c.customer_id for c in self.customers)

    @property
    def customer_by_id(self) -> dict:
        return {c.customer_id: c for c in self.customers}

    @property
    def required_node_ids(self) -> frozenset:
        return frozenset(c.location_node for c in self.customers)


# ---------------------------------------------------------------------------
# Solution structure
# ---------------------------------------------------------------------------

@dataclass
class VehicleRoute:
    """
    The planned route for a single vehicle.

    Attributes
    ----------
    vehicle_id    : any           – matches Vehicle.vehicle_id
    depot_node    : any           – home depot (start and end of route)
    visit_order   : list          – ordered list of *customer_id* values the
                                    vehicle serves (may be empty)
    node_sequence : list          – full ordered list of *graph node ids*
                                    the vehicle traverses, including depot
                                    at position [0] and [-1].
                                    Example: [depot, A, B, C, depot]
                                    where A/B/C are customer location nodes
                                    (possibly with intermediate routing nodes
                                    between them when the planner expands
                                    shortest paths).

    Notes
    -----
    - An empty route (vehicle serves no customers) has
        visit_order   = []
        node_sequence = [depot_node, depot_node]   (starts and ends at depot)
    - The feasibility checker inspects node_sequence to verify:
        * first and last element == depot_node
        * every consecutive pair is a real, open graph edge
    """

    vehicle_id: Any
    depot_node: Any
    visit_order: list = field(default_factory=list)
    node_sequence: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.node_sequence:
            # Auto-fill trivial (stay-at-depot) sequence
            self.node_sequence = [self.depot_node, self.depot_node]


@dataclass
class VRPSolution:
    """
    A complete solution to a VRPProblem.

    Attributes
    ----------
    routes         : list[VehicleRoute]  – one entry per vehicle
    is_feasible    : bool                – True iff all hard constraints pass
    objective_value: Optional[float]     – fitness score (None until evaluated)
    violations     : list[str]           – human-readable constraint violations
                                           (empty when is_feasible is True)

    Usage
    -----
    Construct the routes list, then call::

        from app.vrp.feasibility import check_feasibility
        from app.vrp.objective   import compute_fitness, FitnessWeights

        result   = check_feasibility(solution, problem)
        solution.is_feasible    = result.is_feasible
        solution.violations     = result.violations
        solution.objective_value = compute_fitness(solution, problem, FitnessWeights())
    """

    routes: list[VehicleRoute] = field(default_factory=list)
    is_feasible: bool = False
    objective_value: Optional[float] = None
    violations: list[str] = field(default_factory=list)
