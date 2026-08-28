"""
app/api/routes/optimize.py – POST /optimize endpoint.

Runs the existing QPSO + repair + 2-opt pipeline on the stored VRPProblem,
then registers the resulting routes into a RouteManager.

Design notes
------------
- Uses ``QPSOOptimizer.run()`` unchanged — no new optimizer is introduced.
- ``ActiveRoute.from_vehicle_route()`` is used to convert each VehicleRoute
  to an operational ActiveRoute.
- Trivial depot-only routes (node_sequence == [depot, depot]) are silently
  skipped — they fail ``validate_route()`` because there is no self-loop edge,
  and a vehicle with no customers assigned has nothing to deliver.
- The RouteManager is a fresh instance per /optimize call; it does not
  accumulate across calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_problem
from app.api.models import OptimizeRequest, OptimizeResponse, RouteOut
from app.api.state import AppState
from app.graph.model import TransportGraph
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.routes.manager import RouteManager
from app.routes.model import ActiveRoute
from app.routes.validation import validate_route
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights

router = APIRouter(prefix="/optimize", tags=["Optimize"])


def _build_route_out(ar: ActiveRoute) -> RouteOut:
    """Convert an ActiveRoute to the API response model."""
    return RouteOut(
        vehicle_id=ar.vehicle_id,
        depot_node=ar.depot_node,
        visit_order=list(ar.visit_order),
        node_sequence=list(ar.node_sequence),
        total_distance=ar.total_distance,
        total_travel_time=ar.total_travel_time,
        estimated_arrival=ar.estimated_arrival,
    )


def _build_route_manager(solution: VRPSolution, tg: TransportGraph) -> RouteManager:
    """
    Build a RouteManager from a VRPSolution.

    Skips vehicles with trivial (depot-only) routes that would fail
    ``validate_route()`` — these vehicles have no customers assigned.
    """
    rm = RouteManager()
    for vr in solution.routes:
        # Skip empty/trivial routes ([depot, depot] — no edge exists)
        seq = vr.node_sequence
        if len(seq) < 2:
            continue
        if len(seq) == 2 and seq[0] == seq[1]:
            continue
        try:
            ar = ActiveRoute.from_vehicle_route(vr, route_id=f"V{vr.vehicle_id}")
            rm.register(ar, tg)
        except (ValueError, KeyError):
            # validate_route rejected this path; skip gracefully
            continue
    return rm


@router.post(
    "",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run QPSO optimization",
    description=(
        "Runs the existing QPSO + capacity-repair + 2-opt pipeline on the "
        "current fleet and network.  Returns optimized routes with ETA and "
        "objective breakdown.  Requires POST /network and POST /fleet first."
    ),
)
def run_optimization(
    body: OptimizeRequest,
    state: AppState = Depends(require_problem),
) -> OptimizeResponse:
    """
    Execute the QPSO optimizer and register results in the RouteManager.

    The QPSO → repair → 2-opt evaluation pipeline is used unchanged.
    The FitnessWeights from the request body are forwarded to QPSOConfig.
    """
    problem = state.problem  # guaranteed non-None by require_problem
    assert problem is not None
    graph = state.graph
    assert graph is not None

    # ── Build QPSO configuration ─────────────────────────────────────────
    weights = FitnessWeights(
        wT=body.w_time,
        wD=body.w_distance,
        wC=body.w_congestion,
    )
    cfg = QPSOConfig(
        n_particles=body.n_particles,
        max_iterations=body.max_iterations,
        time_budget_seconds=body.time_budget_seconds,
        seed=body.seed,
        fitness_weights=weights,
    )

    # ── Run optimizer ────────────────────────────────────────────────────
    assert problem is not None
    result = QPSOOptimizer(problem, cfg).run()

    # ── Build RouteManager from best solution ────────────────────────────
    rm = _build_route_manager(result.best_solution, graph)

    # ── Store state ──────────────────────────────────────────────────────
    state.clear_from_optimize()
    state.qpso_result = result
    state.route_manager = rm
    state.last_qpso_config = {
        "n_particles": body.n_particles,
        "max_iterations": body.max_iterations,
        "time_budget_seconds": body.time_budget_seconds,
        "seed": body.seed,
        "w_time": body.w_time,
        "w_distance": body.w_distance,
        "w_congestion": body.w_congestion,
    }

    # ── Build response ───────────────────────────────────────────────────
    active_routes = rm.list_active()
    routes_out = [_build_route_out(ar) for ar in active_routes]

    return OptimizeResponse(
        best_fitness=result.best_fitness,
        is_feasible=bool(result.best_solution.is_feasible),
        n_iterations_run=result.n_iterations_run,
        stopped_early=result.stopped_early,
        pre_repair_fitness=result.pre_repair_fitness,
        post_repair_fitness=result.post_repair_fitness,
        n_routes=len(routes_out),
        routes=routes_out,
    )
