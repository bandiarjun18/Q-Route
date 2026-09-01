"""
app/api/routes/current.py – GET /routes/current endpoint.

Returns the currently active vehicle routes from the RouteManager.
Requires POST /optimize to have been called first.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_optimization
from app.api.models import (
    GeographicCustomerOut,
    GeographicDepotOut,
    GeographicRouteOut,
    GeographicVisualizationResponse,
    RouteOut,
    RoutesResponse,
)
from app.api.state import AppState
from app.graph.model import TransportGraph
from app.routes.model import ActiveRoute

router = APIRouter(prefix="/routes", tags=["Routes"])


def _extract_node_geo_coordinate(tg: Optional[TransportGraph], nid: Any) -> Optional[list[float]]:
    """Extract [latitude, longitude] from a graph node if valid geographic coordinates exist."""
    if tg is None or nid not in tg.graph.nodes:
        return None
    data = tg.graph.nodes[nid]
    lat: Optional[float] = None
    lon: Optional[float] = None

    if "lat" in data and "lon" in data:
        try:
            lat = float(data["lat"])
            lon = float(data["lon"])
        except (ValueError, TypeError):
            return None
    elif "latitude" in data and "longitude" in data:
        try:
            lat = float(data["latitude"])
            lon = float(data["longitude"])
        except (ValueError, TypeError):
            return None
    elif "y" in data and "x" in data and ("osm_id" in data or "lat" in data):
        try:
            lat = float(data["y"])
            lon = float(data["x"])
        except (ValueError, TypeError):
            return None

    if lat is not None and lon is not None:
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return [lat, lon]
    return None


def _build_route_out(ar: ActiveRoute, tg: Optional[TransportGraph] = None) -> RouteOut:
    geometry: Optional[list[list[float]]] = None
    if tg is not None:
        coords: list[list[float]] = []
        is_geo = True
        for nid in ar.node_sequence:
            pt = _extract_node_geo_coordinate(tg, nid)
            if pt is None:
                is_geo = False
                break
            coords.append(pt)
        if is_geo and len(coords) == len(ar.node_sequence) and len(coords) > 0:
            geometry = coords

    status_val = (ar.status.value if hasattr(ar.status, "value") else str(ar.status or "ACTIVE")).upper()

    return RouteOut(
        vehicle_id=ar.vehicle_id,
        depot_node=ar.depot_node,
        visit_order=list(ar.visit_order),
        node_sequence=list(ar.node_sequence),
        total_distance=ar.total_distance,
        total_travel_time=ar.total_travel_time,
        estimated_arrival=ar.estimated_arrival,
        geometry=geometry,
        status=status_val,
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
    routes_out = [_build_route_out(ar, state.graph) for ar in active_routes]
    return RoutesResponse(
        total_active=len(routes_out),
        routes=routes_out,
    )


@router.get(
    "/geographic",
    response_model=GeographicVisualizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get geographic route visualization geometry and markers",
    description=(
        "Returns ordered geographic [latitude, longitude] route geometries, "
        "depot locations, and customer delivery points for interactive OpenStreetMap display."
    ),
)
def get_geographic_routes(
    state: AppState = Depends(require_optimization),
) -> GeographicVisualizationResponse:
    """
    Return geographic visualization model containing customer/depot markers and route paths.
    """
    rm = state.route_manager
    assert rm is not None
    tg = state.graph
    problem = state.problem

    active_routes = rm.list_active()
    geo_routes: list[GeographicRouteOut] = []
    all_latitudes: list[float] = []
    all_longitudes: list[float] = []

    for ar in active_routes:
        coords: list[list[float]] = []
        for nid in ar.node_sequence:
            pt = _extract_node_geo_coordinate(tg, nid)
            if pt is not None:
                coords.append(pt)
                all_latitudes.append(pt[0])
                all_longitudes.append(pt[1])

        status_val = (ar.status.value if hasattr(ar.status, "value") else str(ar.status or "ACTIVE")).upper()

        geo_routes.append(
            GeographicRouteOut(
                vehicle_id=ar.vehicle_id,
                depot_node=ar.depot_node,
                visit_order=list(ar.visit_order),
                node_sequence=list(ar.node_sequence),
                total_distance=ar.total_distance,
                total_travel_time=ar.total_travel_time,
                estimated_arrival=ar.estimated_arrival,
                coordinates=coords,
                status=status_val,
            )
        )

    # Collect depots
    geo_depots: list[GeographicDepotOut] = []
    seen_depots: set[Any] = set()
    if problem is not None:
        for v in problem.vehicles:
            if v.depot_node not in seen_depots:
                seen_depots.add(v.depot_node)
                pt = _extract_node_geo_coordinate(tg, v.depot_node)
                if pt is not None:
                    geo_depots.append(
                        GeographicDepotOut(id=v.depot_node, latitude=pt[0], longitude=pt[1])
                    )
                    all_latitudes.append(pt[0])
                    all_longitudes.append(pt[1])

    # Collect customers
    geo_customers: list[GeographicCustomerOut] = []
    if problem is not None:
        for c in problem.customers:
            pt = _extract_node_geo_coordinate(tg, c.location_node)
            if pt is not None:
                geo_customers.append(
                    GeographicCustomerOut(
                        id=c.customer_id,
                        location_node=c.location_node,
                        latitude=pt[0],
                        longitude=pt[1],
                        demand=c.demand,
                    )
                )
                all_latitudes.append(pt[0])
                all_longitudes.append(pt[1])

    is_geo = len(all_latitudes) > 0 and len(all_longitudes) > 0
    center: Optional[list[float]] = None
    if is_geo:
        center = [
            sum(all_latitudes) / len(all_latitudes),
            sum(all_longitudes) / len(all_longitudes),
        ]

    return GeographicVisualizationResponse(
        is_geographic=is_geo,
        center=center,
        depots=geo_depots,
        customers=geo_customers,
        routes=geo_routes,
    )
