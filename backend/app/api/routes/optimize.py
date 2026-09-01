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

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_state, require_problem
from app.api.models import OptimizeRequest, OptimizeResponse, RouteOut
from app.api.state import AppState
from app.api.routes.current import _build_route_out, _extract_node_geo_coordinate
from app.db.crud import (
    get_active_network,
    get_latest_optimization_run,
    get_routes_for_optimization,
    save_optimization_run,
)
from app.db.session import get_db
from app.graph.model import TransportGraph
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.routes.manager import RouteManager
from app.routes.model import ActiveRoute
from app.routes.validation import validate_route
from app.vrp.models import VRPProblem, VRPSolution
from app.vrp.objective import FitnessWeights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optimize", tags=["Optimize"])


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
    db: Session = Depends(get_db),
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
    routes_out = [_build_route_out(ar, graph) for ar in active_routes]


    # ── Persist to PostgreSQL ────────────────────────────────────────────
    try:
        net_id = state.network_db_id
        if not net_id:
            active_net = get_active_network(db)
            if active_net:
                net_id = active_net.id
                state.network_db_id = net_id
        if net_id:
            opt_model = save_optimization_run(
                db=db,
                network_id=net_id,
                config=state.last_qpso_config,
                result=result,
                active_routes=active_routes,
            )
            state.opt_run_db_id = opt_model.id
    except Exception as exc:
        logger.warning("Failed to persist optimization run to PostgreSQL: %s", exc)


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


@router.get(
    "",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current optimization result",
    description="Returns the latest optimization result and active routes.",
)
@router.get(
    "/current",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_current_optimization(
    state: AppState = Depends(get_state),
    db: Session = Depends(get_db),
) -> OptimizeResponse:
    """Return the most recent optimization result stored in application state or PostgreSQL."""
    # 1. Check in-memory AppState first
    if state.qpso_result is not None and state.route_manager is not None:
        result = state.qpso_result
        rm = state.route_manager
        active_routes = rm.list_active()
        routes_out = [_build_route_out(ar, state.graph) for ar in active_routes]
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

    # 2. Fallback to PostgreSQL database persistence
    net_id = state.network_db_id
    if not net_id:
        active_net = get_active_network(db)
        if active_net:
            net_id = active_net.id
    if net_id:
        opt_run = get_latest_optimization_run(db, net_id)
        if opt_run:
            db_routes = get_routes_for_optimization(db, opt_run.id)
            routes_out = []
            for r in db_routes:
                node_seq = list(r.node_sequence) if r.node_sequence else []
                geometry = None
                if state.graph is not None and node_seq:
                    coords = []
                    is_geo = True
                    for nid in node_seq:
                        pt = _extract_node_geo_coordinate(state.graph, nid)
                        if pt is None:
                            is_geo = False
                            break
                        coords.append(pt)
                    if is_geo and len(coords) == len(node_seq) and len(coords) > 0:
                        geometry = coords

                routes_out.append(
                    RouteOut(
                        vehicle_id=r.vehicle_id,
                        depot_node=r.depot_node,
                        visit_order=list(r.visit_order) if r.visit_order else [],
                        node_sequence=node_seq,
                        total_distance=float(r.total_distance or 0.0),
                        total_travel_time=float(r.total_travel_time or 0.0),
                        estimated_arrival=float(r.estimated_arrival) if r.estimated_arrival is not None else None,
                        geometry=geometry,
                        status=str(r.status or "ACTIVE").upper(),
                    )
                )

            return OptimizeResponse(
                best_fitness=float(opt_run.best_fitness or 0.0),
                is_feasible=bool(opt_run.is_feasible),
                n_iterations_run=int(opt_run.n_iterations_run or 0),
                stopped_early=bool(opt_run.stopped_early),
                pre_repair_fitness=float(opt_run.pre_repair_fitness) if opt_run.pre_repair_fitness is not None else None,
                post_repair_fitness=float(opt_run.post_repair_fitness) if opt_run.post_repair_fitness is not None else None,
                n_routes=len(routes_out),
                routes=routes_out,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No optimization run yet. Call POST /optimize first.",
    )
