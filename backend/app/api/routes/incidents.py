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

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_optimization
from app.api.models import IncidentRequest, IncidentResponse, RouteOut
from app.api.state import AppState
from app.graph.model import TransportGraph
from app.incidents.model import Incident, IncidentLayer, IncidentSeverity, IncidentType
from app.qpso.config import QPSOConfig
from app.qpso.optimizer import QPSOOptimizer
from app.routes.model import ActiveRoute, RouteStatus
from app.routes.validation import validate_route
from app.vrp.models import VRPProblem
from app.vrp.objective import FitnessWeights

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
    return RouteOut(
        vehicle_id=ar.vehicle_id,
        depot_node=ar.depot_node,
        visit_order=list(ar.visit_order),
        node_sequence=list(ar.node_sequence),
        total_distance=ar.total_distance,
        total_travel_time=ar.total_travel_time,
        estimated_arrival=ar.estimated_arrival,
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

    # ── 4. Build / update IncidentLayer and apply to graph ───────────────
    if state.incident_layer is None:
        state.incident_layer = IncidentLayer()
    state.incident_layer.add_incident(incident)
    state.incident_layer.apply(graph)

    # ── 5. Identify affected routes in current RouteManager ───────────────
    affected_routes_before = rm.affected_by_incident(state.incident_layer, mark=True)
    affected_vehicle_ids = [ar.vehicle_id for ar in affected_routes_before]

    # ── 6. Re-run QPSO with updated graph ────────────────────────────────
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
    new_result = QPSOOptimizer(problem, cfg).run()
    state.qpso_result = new_result  # update convergence history

    # ── 7. Update RouteManager with re-optimized routes ──────────────────
    for vr in new_result.best_solution.routes:
        route_id = f"V{vr.vehicle_id}"
        seq = vr.node_sequence
        # Skip trivial routes
        if len(seq) < 2 or (len(seq) == 2 and seq[0] == seq[1]):
            continue
        # Only update routes that were affected
        if vr.vehicle_id not in affected_vehicle_ids:
            continue
        try:
            validate_route(graph, seq)
        except ValueError:
            continue

        new_ar = ActiveRoute.from_vehicle_route(vr, route_id=route_id)
        # Remove old entry if it exists, then re-register with updated path
        try:
            rm.remove(route_id)
        except KeyError:
            pass
        try:
            rm.register(new_ar, graph)
        except (ValueError, KeyError):
            continue

    # ── 8. Build response ────────────────────────────────────────────────
    # Collect current state of affected routes from manager
    updated_routes_out: list[RouteOut] = []
    for vid in affected_vehicle_ids:
        route_id = f"V{vid}"
        try:
            ar = rm.get(route_id)
            updated_routes_out.append(_build_route_out(ar))
        except KeyError:
            pass

    unaffected_count = len(rm.list_active()) - len(updated_routes_out)
    unaffected_count = max(0, unaffected_count)

    return IncidentResponse(
        edge_u=u,
        edge_v=v,
        incident_type=inc_type.name,
        severity=severity.name,
        is_closure=incident.is_closure,
        affected_vehicle_ids=affected_vehicle_ids,
        n_affected=len(affected_vehicle_ids),
        updated_routes=updated_routes_out,
        unaffected_route_count=unaffected_count,
    )
