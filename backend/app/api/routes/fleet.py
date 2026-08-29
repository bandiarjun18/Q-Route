"""
app/api/routes/fleet.py – POST /fleet endpoint.

Accepts vehicle and customer configuration, validates node IDs against the
currently loaded graph, builds a VRPProblem, and stores it in app state.

Requires POST /network to have been called first.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_graph
from app.api.models import CustomerIn, FleetRequest, FleetResponse, VehicleIn
from app.api.state import AppState
from app.db.crud import get_active_network, save_fleet
from app.db.session import get_db
from app.vrp.models import Customer, Vehicle, VRPProblem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fleet", tags=["Fleet"])


@router.post(
    "",
    response_model=FleetResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure fleet and customer demands",
    description=(
        "Sets up vehicles and customer delivery orders for the current network.  "
        "All node IDs are validated against the loaded graph.  "
        "Clears any existing optimization and incident state.  "
        "Requires POST /network first."
    ),
)
def configure_fleet(
    body: FleetRequest,
    state: AppState = Depends(require_graph),
    db: Session = Depends(get_db),
) -> FleetResponse:
    """
    Build and store a VRPProblem from the provided fleet and customer data.

    Validation
    ----------
    - All ``depot_node`` values must be nodes that exist in ``state.graph``.
    - All ``location_node`` values must be nodes that exist in ``state.graph``.
    - ``capacity`` > 0 is enforced by the Pydantic model (VehicleIn).
    - ``demand`` >= 0 is enforced by the Pydantic model (CustomerIn).

    Returns
    -------
    Echo of the accepted fleet and customer data with counts.
    """
    graph = state.graph  # guaranteed non-None by require_graph
    assert graph is not None
    g = graph.graph

    # ── Validate depot nodes ─────────────────────────────────────────────
    for v in body.vehicles:
        if not g.has_node(v.depot_node):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Vehicle {v.vehicle_id!r}: depot_node {v.depot_node!r} "
                    f"does not exist in the current network."
                ),
            )

    # ── Validate customer location nodes ─────────────────────────────────
    for c in body.customers:
        if not g.has_node(c.location_node):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Customer {c.customer_id!r}: location_node "
                    f"{c.location_node!r} does not exist in the current network."
                ),
            )

    # ── Build domain objects ─────────────────────────────────────────────
    vehicles = [
        Vehicle(
            vehicle_id=v.vehicle_id,
            capacity=v.capacity,
            depot_node=v.depot_node,
        )
        for v in body.vehicles
    ]
    customers = [
        Customer(
            customer_id=c.customer_id,
            location_node=c.location_node,
            demand=c.demand,
        )
        for c in body.customers
    ]

    # ── Store state (clears optimization + incident state) ───────────────
    state.clear_from_fleet()
    state.problem = VRPProblem(graph=graph, vehicles=vehicles, customers=customers)

    # ── Persist to PostgreSQL ────────────────────────────────────────────
    try:
        net_id = state.network_db_id
        if not net_id:
            active_net = get_active_network(db)
            if active_net:
                net_id = active_net.id
                state.network_db_id = net_id
        if net_id:
            save_fleet(db, net_id, vehicles, customers)
    except Exception as exc:
        logger.warning("Failed to persist fleet to PostgreSQL: %s", exc)

    return FleetResponse(
        n_vehicles=len(vehicles),
        n_customers=len(customers),
        vehicles=list(body.vehicles),
        customers=list(body.customers),
    )

