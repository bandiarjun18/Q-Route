"""
app/incidents/rerouting.py – Incident-Aware Dynamic Selective Rerouting for Q-Route (Milestone 12).

Provides:
- detect_affected_routes: Isolates routes that intersect an active incident or closed edge.
- selective_reroute: Preserves unaffected vehicle routes and re-optimizes only affected vehicles.
- RerouteResult: Structured outcome of selective dynamic rerouting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

from app.graph.model import TransportGraph
from app.incidents.model import IncidentLayer
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.routes.model import ActiveRoute, RouteStatus
from app.routes.validation import validate_route
from app.vrp.feasibility import check_feasibility
from app.vrp.models import Customer, Vehicle, VehicleRoute, VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights, compute_fitness

if TYPE_CHECKING:
    from app.routes.manager import RouteManager

logger = logging.getLogger(__name__)



@dataclass
class RerouteResult:
    """
    Result container for selective incident rerouting.

    Attributes
    ----------
    affected_vehicle_ids   : list[Any]        – IDs of vehicles whose routes crossed incidents.
    unaffected_vehicle_ids : list[Any]        – IDs of vehicles whose routes remained unchanged.
    updated_routes         : list[ActiveRoute] – Newly computed routes for affected vehicles.
    preserved_routes       : list[ActiveRoute] – Unaltered routes for unaffected vehicles.
    all_active_routes      : list[ActiveRoute] – Combined active routes in RouteManager.
    is_feasible            : bool              – True iff all updated routes satisfy hard constraints.
    stopped_early          : bool              – Whether QPSO stopped before max iterations.
    n_iterations_run       : int               – Iterations executed during re-optimization.
    post_incident_fitness  : Optional[float]   – Global solution fitness after rerouting.
    """

    affected_vehicle_ids: list[Any] = field(default_factory=list)
    unaffected_vehicle_ids: list[Any] = field(default_factory=list)
    updated_routes: list[ActiveRoute] = field(default_factory=list)
    preserved_routes: list[ActiveRoute] = field(default_factory=list)
    all_active_routes: list[ActiveRoute] = field(default_factory=list)
    is_feasible: bool = True
    stopped_early: bool = False
    n_iterations_run: int = 0
    post_incident_fitness: Optional[float] = None


def detect_affected_routes(
    rm: RouteManager,
    incident_layer: IncidentLayer,
    graph: Optional[TransportGraph] = None,
) -> tuple[list[ActiveRoute], list[ActiveRoute]]:
    """
    Classify active routes into affected and unaffected groups.

    A route is affected if:
    1. Any consecutive edge (u, v) in its node_sequence has an active incident in `incident_layer`.
    2. Or any edge (u, v) in the graph has `road_status == 'closed'`.

    Parameters
    ----------
    rm             : RouteManager – active routes registry.
    incident_layer : IncidentLayer – registered disruptions.
    graph          : TransportGraph | None – optional graph to verify closed edges.

    Returns
    -------
    tuple[list[ActiveRoute], list[ActiveRoute]]
        (affected_routes, unaffected_routes)
    """
    live_routes = rm.list_active()
    affected: list[ActiveRoute] = []
    unaffected: list[ActiveRoute] = []

    for route in live_routes:
        seq = route.node_sequence
        is_affected = False

        for u, v in zip(seq[:-1], seq[1:]):
            # Check incident layer
            if incident_layer.has_incident(u, v):
                is_affected = True
                break
            # Check graph road status if graph is provided
            if graph is not None and graph.graph.has_edge(u, v):
                if graph.graph[u][v].get("road_status") == TransportGraph.CLOSED:
                    is_affected = True
                    break

        if is_affected:
            affected.append(route)
        else:
            unaffected.append(route)

    return affected, unaffected


def selective_reroute(
    graph: TransportGraph,
    problem: VRPProblem,
    rm: RouteManager,
    incident_layer: IncidentLayer,
    qpso_config: QPSOConfig,
) -> RerouteResult:
    """
    Execute selective dynamic rerouting for affected vehicles only.

    Steps
    -----
    1. Apply active incidents to the transport graph.
    2. Detect which active vehicle routes are affected.
    3. If no routes are affected, return preserved routes immediately.
    4. For affected vehicles:
       - Run QPSO optimization on the full problem with the updated graph.
       - Extract newly planned routes exclusively for the affected vehicle IDs.
       - Validate paths against the updated graph (ensuring closed edges are avoided).
       - Atomically update RouteManager: remove old affected routes, register new valid routes.
    5. Preserved vehicles remain 100% untouched in node sequence and customer stops.
    6. Re-stamp travel time and metrics on all live routes.

    Parameters
    ----------
    graph          : TransportGraph – live road network.
    problem        : VRPProblem – underlying fleet and customer problem definition.
    rm             : RouteManager – active route manager.
    incident_layer : IncidentLayer – active incidents.
    qpso_config    : QPSOConfig – optimizer configuration.

    Returns
    -------
    RerouteResult
    """
    # 1. Ensure incidents are applied to the graph
    incident_layer.apply(graph)

    # 2. Detect affected and unaffected routes
    affected_routes, unaffected_routes = detect_affected_routes(rm, incident_layer, graph)
    affected_vids = [r.vehicle_id for r in affected_routes]
    unaffected_vids = [r.vehicle_id for r in unaffected_routes]

    # If no routes are affected, return without rerunning optimizer
    if not affected_vids:
        return RerouteResult(
            affected_vehicle_ids=[],
            unaffected_vehicle_ids=unaffected_vids,
            updated_routes=[],
            preserved_routes=list(unaffected_routes),
            all_active_routes=rm.list_active(),
            is_feasible=True,
            stopped_early=False,
            n_iterations_run=0,
        )

    # 3. Re-run QPSO optimizer with the updated graph
    optimizer = QPSOOptimizer(problem, qpso_config)
    result = optimizer.run()

    # 4. Selectively extract and register new routes for affected vehicles only
    updated_active_routes: list[ActiveRoute] = []

    for vr in result.best_solution.routes:
        if vr.vehicle_id not in affected_vids:
            continue

        existing_routes = rm.routes_for_vehicle(vr.vehicle_id)
        route_id = existing_routes[0].route_id if existing_routes else (
            str(vr.vehicle_id) if str(vr.vehicle_id).startswith("V") else f"V{vr.vehicle_id}"
        )
        seq = vr.node_sequence

        # Skip trivial empty routes
        if len(seq) < 2 or (len(seq) == 2 and seq[0] == seq[1]):
            continue

        # Validate that the new path is valid on the updated graph (no closed edges)
        try:
            validate_route(graph, seq)
        except ValueError as exc:
            logger.warning("Rerouted vehicle %s path validation failed: %s", vr.vehicle_id, exc)
            continue

        new_ar = ActiveRoute.from_vehicle_route(vr, route_id=route_id)
        # Atomically replace in RouteManager: remove all prior routes for this vehicle
        for old_r in existing_routes:
            try:
                rm.remove(old_r.route_id)
            except KeyError:
                pass

        try:
            registered_ar = rm.register(new_ar, graph)
            updated_active_routes.append(registered_ar)
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to register rerouted vehicle %s: %s", vr.vehicle_id, exc)
            continue

    # 5. Build combined solution for overall feasibility and fitness evaluation
    combined_solution_routes: list[VehicleRoute] = []
    for ar in rm.list_active():
        vr = VehicleRoute(
            vehicle_id=ar.vehicle_id,
            depot_node=ar.depot_node,
            visit_order=list(ar.visit_order),
            node_sequence=list(ar.node_sequence),
        )
        combined_solution_routes.append(vr)

    combined_solution = VRPSolution(routes=combined_solution_routes)
    feas_result = check_feasibility(combined_solution, problem)
    combined_solution.is_feasible = feas_result.is_feasible
    combined_solution.violations = feas_result.violations

    weights = qpso_config.fitness_weights or FitnessWeights()
    post_fitness = compute_fitness(combined_solution, problem, weights)

    return RerouteResult(
        affected_vehicle_ids=affected_vids,
        unaffected_vehicle_ids=unaffected_vids,
        updated_routes=updated_active_routes,
        preserved_routes=list(unaffected_routes),
        all_active_routes=rm.list_active(),
        is_feasible=combined_solution.is_feasible,
        stopped_early=result.stopped_early,
        n_iterations_run=result.n_iterations_run,
        post_incident_fitness=post_fitness,
    )
