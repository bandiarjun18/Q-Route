"""
app/api/routes/current.py – GET /routes/current endpoint.

Returns the currently active vehicle routes from the RouteManager.
Requires POST /optimize to have been called first.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_optimization
from app.api.models import RouteOut, RoutesResponse
from app.api.state import AppState
from app.routes.model import ActiveRoute

router = APIRouter(prefix="/routes", tags=["Routes"])


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


@router.get(
    "/current",
    response_model=RoutesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get currently active vehicle routes",
    description=(
        "Returns all active vehicle routes from the RouteManager (status "
        "ACTIVE or AFFECTED).  Routes are populated by POST /optimize and "
        "updated by POST /incidents.  Requires POST /optimize first."
    ),
)
def get_current_routes(
    state: AppState = Depends(require_optimization),
) -> RoutesResponse:
    """
    Return all live routes from the RouteManager.

    Routes with status ACTIVE or AFFECTED are included.
    Routes with terminal status (COMPLETED, CANCELLED) are excluded.
    """
    rm = state.route_manager
    assert rm is not None
    active_routes = rm.list_active()
    routes_out = [_build_route_out(ar) for ar in active_routes]
    return RoutesResponse(
        total_active=len(routes_out),
        routes=routes_out,
    )
