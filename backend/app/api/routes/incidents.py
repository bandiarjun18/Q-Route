"""
app/api/routes/incidents.py – POST /incidents endpoint.

Registers a road incident, applies it to the graph, identifies affected
routes, re-runs the QPSO optimizer with the updated graph, and returns
the updated routes for affected vehicles.

Design
------
- Incident registration uses the existing ``IncidentLayer`` / ``Incident``
  API (Milestone 7) unchanged.
- ``incident_layer.apply(graph)`` mutates ``state.graph`` in-place, so the
  updated congestion / road_status is automatically picked up by the re-run.
- Re-optimization runs the full QPSO pipeline on the complete problem with
  the updated graph.  Unaffected vehicles' routes are preserved in the
  RouteManager; only affected vehicles' route entries are replaced.
- ``affected_by_incident()`` is called on the pre-re-optimization routes to
  identify which vehicles are affected.  The final response reports these
  vehicles and their new routes.

Requires POST /optimize to have been called first.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_optimization
from app.api.models import IncidentRequest, IncidentResponse, RouteOut
from app.api.state import AppState
from app.db.crud import get_active_network, get_incidents_for_network, save_incident, save_optimization_run
from app.db.session import get_db
from app.graph.model import TransportGraph
from app.incidents.model import Incident, IncidentLayer, IncidentSeverity, IncidentType
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.routes.model import ActiveRoute, RouteStatus
from app.routes.validation import validate_route
from app.vrp.models import VRPProblem
from app.vrp.objective import FitnessWeights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Map API string → IncidentType enum
_INCIDENT_TYPE_MAP: dict[str, IncidentType] = {
    "ACCIDENT": IncidentType.ACCIDENT,
    "ROAD_CLOSURE": IncidentType.ROAD_CLOSURE,
    "CONSTRUCTION": IncidentType.CONSTRUCTION,
    "OBSTRUCTION": IncidentType.OBSTRUCTION,
}

# Map API string → IncidentSeverity enum
_SEVERITY_MAP: dict[str, IncidentSeverity] = {
    "NONE": IncidentSeverity.NONE,
    "LOW": IncidentSeverity.LOW,
    "MEDIUM": IncidentSeverity.MEDIUM,
    "HIGH": IncidentSeverity.HIGH,
    "CRITICAL": IncidentSeverity.CRITICAL,
}


def _build_route_out(ar: ActiveRoute) -> RouteOut:
    status_val = (ar.status.value if hasattr(ar.status, "value") else str(ar.status or "ACTIVE")).upper()
    return RouteOut(
        vehicle_id=ar.vehicle_id,
        depot_node=ar.depot_node,
        visit_order=list(ar.visit_order),
        node_sequence=list(ar.node_sequence),
        total_distance=ar.total_distance,
        total_travel_time=ar.total_travel_time,
        estimated_arrival=ar.estimated_arrival,
        status=status_val,
    )


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Register a road incident and re-optimize affected routes",
    description=(
        "Registers a road incident on a directed edge, applies it to the "
        "graph, identifies affected routes, and re-runs the QPSO optimizer "
        "with the updated graph.  Unaffected vehicle routes remain unchanged.  "
        "Requires POST /optimize first."
    ),
)
def register_incident(
    body: IncidentRequest,
    state: AppState = Depends(require_optimization),
    db: Session = Depends(get_db),
) -> IncidentResponse:

    """
    Register an incident, apply it to the graph, and re-optimize.

    Steps
    -----
    1. Validate edge (u, v) exists in the graph.
    2. Parse incident_type and severity strings to enum values.
    3. Build Incident object.
    4. Build or update IncidentLayer; apply to graph (mutates congestion
       and/or road_status on the affected edge).
    5. Identify routes affected by this incident (from current RouteManager).
    6. Re-run QPSO optimizer with the updated graph to find new routes.
    7. Update RouteManager: mark affected routes as AFFECTED or replace them
       with new optimized routes.
    8. Return affected vehicle IDs, updated routes, and incident metadata.
    """
    graph = state.graph
    assert graph is not None
    problem = state.problem
    assert problem is not None
    rm = state.route_manager
    assert rm is not None

    # ── 1. Validate edge ─────────────────────────────────────────────────
    u, v = body.edge_u, body.edge_v
    if not graph.graph.has_edge(u, v):
        if graph.graph.has_edge(str(u), str(v)):
            u, v = str(u), str(v)
        elif str(u).isdigit() and str(v).isdigit() and graph.graph.has_edge(int(u), int(v)):
            u, v = int(u), int(v)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Edge ({u!r} → {v!r}) does not exist in the current network. "
                    f"Incidents can only be placed on existing directed edges."
                ),
            )

    # ── 2. Parse enum strings (already validated by Pydantic field_validator) ──
    inc_type = _INCIDENT_TYPE_MAP[body.incident_type]
    severity = _SEVERITY_MAP[body.severity]

    # ── 3. Build Incident ────────────────────────────────────────────────
    try:
        incident = Incident(
            u=u, v=v,
            type=inc_type,
            severity=severity,
            description=body.description,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # ── 4. Build / update IncidentLayer ──────────────────────────────────
    if state.incident_layer is None:
        state.incident_layer = IncidentLayer()
    state.incident_layer.add_incident(incident)

    # ── 5. Build QPSO config for re-optimization ─────────────────────────
    cfg_params = state.last_qpso_config or {}
    weights = FitnessWeights(
        wT=cfg_params.get("w_time", 1.0),
        wD=cfg_params.get("w_distance", 0.5),
        wC=cfg_params.get("w_congestion", 0.3),
    )
    cfg = QPSOConfig(
        n_particles=cfg_params.get("n_particles", 20),
        max_iterations=cfg_params.get("max_iterations", 100),
        time_budget_seconds=cfg_params.get("time_budget_seconds"),
        seed=cfg_params.get("seed", 42),
        fitness_weights=weights,
    )

    # ── 6. Execute Selective Dynamic Rerouting ───────────────────────────
    from app.incidents.rerouting import selective_reroute
    reroute_res = selective_reroute(
        graph=graph,
        problem=problem,
        rm=rm,
        incident_layer=state.incident_layer,
        qpso_config=cfg,
    )

    # ── 7. Build updated routes for response ─────────────────────────────
    updated_routes_out = [_build_route_out(ar) for ar in reroute_res.updated_routes]
    unaffected_count = len(reroute_res.preserved_routes)

    # ── 8. Persist to PostgreSQL ─────────────────────────────────────────
    try:
        net_id = state.network_db_id
        if not net_id:
            active_net = get_active_network(db)
            if active_net:
                net_id = active_net.id
                state.network_db_id = net_id
        if net_id:
            opt_run_id = state.opt_run_db_id
            if reroute_res.affected_vehicle_ids:
                # Persist the new post-incident optimization run and updated active routes
                opt_model = save_optimization_run(
                    db=db,
                    network_id=net_id,
                    config=state.last_qpso_config or {},
                    result=reroute_res,
                    active_routes=rm.list_active(),
                )
                opt_run_id = opt_model.id
                state.opt_run_db_id = opt_run_id

            # Save incident record associated with the optimization run
            save_incident(
                db=db,
                network_id=net_id,
                optimization_run_id=opt_run_id,
                edge_u=str(u),
                edge_v=str(v),
                incident_type=inc_type.name,
                severity=severity.name,
                description=getattr(body, "description", ""),
                is_closure=bool(incident.is_closure),
            )
    except Exception as exc:
        logger.warning("Failed to persist incident to PostgreSQL: %s", exc)

    resp = IncidentResponse(
        edge_u=u,
        edge_v=v,
        incident_type=inc_type.name,
        severity=severity.name,
        is_closure=incident.is_closure,
        affected_vehicle_ids=reroute_res.affected_vehicle_ids,
        n_affected=len(reroute_res.affected_vehicle_ids),
        updated_routes=updated_routes_out,
        unaffected_route_count=unaffected_count,
    )
    state.last_incident_response = resp
    return resp


@router.get(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current incident and rerouting state",
    description="Returns the latest registered road incident and affected route updates.",
)
@router.get(
    "/current",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_current_incident(
    state: AppState = Depends(require_optimization),
    db: Session = Depends(get_db),
) -> IncidentResponse:
    """Return the most recent road incident and rerouted routes."""
    if state.last_incident_response is not None:
        return state.last_incident_response

    # Fallback to database if available
    net_id = state.network_db_id
    if not net_id:
        active_net = get_active_network(db)
        if active_net:
            net_id = active_net.id
    if net_id:
        db_incidents = get_incidents_for_network(db, net_id)
        if db_incidents and state.route_manager:
            last_inc = db_incidents[-1]
            active_routes = state.route_manager.list_active()
            affected_routes = [
                ar
                for ar in active_routes
                if (ar.status.value if hasattr(ar.status, "value") else str(ar.status)).upper() == "AFFECTED"
            ]
            aff_ids = [ar.vehicle_id for ar in affected_routes]
            updated_routes_out = [_build_route_out(ar) for ar in affected_routes]
            unaffected_count = len(active_routes) - len(affected_routes)
            resp = IncidentResponse(
                edge_u=last_inc.edge_u,
                edge_v=last_inc.edge_v,
                incident_type=last_inc.incident_type,
                severity=last_inc.severity,
                is_closure=last_inc.is_closure,
                affected_vehicle_ids=aff_ids,
                n_affected=len(aff_ids),
                updated_routes=updated_routes_out,
                unaffected_route_count=unaffected_count,
            )
            state.last_incident_response = resp
            return resp

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No road incidents currently registered.",
    )
