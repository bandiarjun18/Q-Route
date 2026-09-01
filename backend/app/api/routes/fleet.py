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

from app.api.dependencies import get_state, require_graph
from app.api.models import CustomerIn, FleetRequest, FleetResponse, VehicleIn
from app.api.state import AppState
from app.db.crud import get_active_network, get_fleet_for_network, save_fleet
from app.db.session import get_db
from app.vrp.models import Customer, Vehicle, VRPProblem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fleet", tags=["Fleet"])


@router.get(
    "",
    response_model=FleetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current fleet configuration",
    description="Retrieves the current fleet vehicles and customer orders stored in application state.",
)
@router.get(
    "/current",
    response_model=FleetResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_current_fleet(
    state: AppState = Depends(get_state),
    db: Session = Depends(get_db),
) -> FleetResponse:
    """Return active fleet vehicles and customer delivery orders."""
    # 1. In-memory problem available
    if state.problem is not None:
        problem = state.problem
        vehicles_out = [
            VehicleIn(
                vehicle_id=v.vehicle_id,
                capacity=v.capacity,
                depot_node=v.depot_node,
            )
            for v in problem.vehicles
        ]
        customers_out = [
            CustomerIn(
                customer_id=c.customer_id,
                location_node=c.location_node,
                demand=c.demand,
            )
            for c in problem.customers
        ]
        return FleetResponse(
            n_vehicles=len(problem.vehicles),
            n_customers=len(problem.customers),
            vehicles=vehicles_out,
            customers=customers_out,
        )

    # 2. Fallback to PostgreSQL database
    net_id = state.network_db_id
    if not net_id:
        active_net = get_active_network(db)
        if active_net:
            net_id = active_net.id
            state.network_db_id = net_id
    if net_id:
        db_vehs, db_custs = get_fleet_for_network(db, net_id)
        if db_vehs and db_custs:
            vehicles_out = []
            for v in db_vehs:
                depot = int(v.depot_node) if str(v.depot_node).isdigit() else str(v.depot_node)
                veh_id = int(v.vehicle_id) if str(v.vehicle_id).isdigit() else str(v.vehicle_id)
                vehicles_out.append(
                    VehicleIn(
                        vehicle_id=veh_id,
                        capacity=float(v.capacity),
                        depot_node=depot,
                    )
                )

            customers_out = []
            for c in db_custs:
                loc = int(c.location_node) if str(c.location_node).isdigit() else str(c.location_node)
                cust_id = int(c.customer_id) if str(c.customer_id).isdigit() else str(c.customer_id)
                customers_out.append(
                    CustomerIn(
                        customer_id=cust_id,
                        location_node=loc,
                        demand=float(c.demand),
                    )
                )

            if state.graph is not None:
                try:
                    vehs_obj = [Vehicle(vehicle_id=v.vehicle_id, capacity=v.capacity, depot_node=v.depot_node) for v in vehicles_out]
                    custs_obj = [Customer(customer_id=c.customer_id, location_node=c.location_node, demand=c.demand) for c in customers_out]
                    state.problem = VRPProblem(graph=state.graph, vehicles=vehs_obj, customers=custs_obj)
                except Exception:
                    pass

            return FleetResponse(
                n_vehicles=len(vehicles_out),
                n_customers=len(customers_out),
                vehicles=vehicles_out,
                customers=customers_out,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No fleet configured. Call POST /fleet first.",
    )


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

    # ── Validate & normalize depot nodes ─────────────────────────────────
    vehicles: list[Vehicle] = []
    for v in body.vehicles:
        depot = v.depot_node
        if not g.has_node(depot):
            if isinstance(depot, int) and g.has_node(str(depot)):
                depot = str(depot)
            elif isinstance(depot, str) and depot.isdigit() and g.has_node(int(depot)):
                depot = int(depot)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Vehicle {v.vehicle_id!r}: depot_node {v.depot_node!r} "
                        f"does not exist in the current network."
                    ),
                )
        vehicles.append(
            Vehicle(
                vehicle_id=v.vehicle_id,
                capacity=v.capacity,
                depot_node=depot,
            )
        )

    # ── Validate & normalize customer location nodes ─────────────────────
    customers: list[Customer] = []
    for c in body.customers:
        loc = c.location_node
        if not g.has_node(loc):
            if isinstance(loc, int) and g.has_node(str(loc)):
                loc = str(loc)
            elif isinstance(loc, str) and loc.isdigit() and g.has_node(int(loc)):
                loc = int(loc)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Customer {c.customer_id!r}: location_node "
                        f"{c.location_node!r} does not exist in the current network."
                    ),
                )
        customers.append(
            Customer(
                customer_id=c.customer_id,
                location_node=loc,
                demand=c.demand,
            )
        )

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


@router.post(
    "/geographic",
    response_model=FleetResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure geographic fleet with latitude and longitude coordinates",
    description=(
        "Configures vehicles and customer delivery orders using real-world "
        "latitude and longitude coordinates. Automatically snaps each location "
        "to the nearest road graph node on the loaded OSM network."
    ),
)
def configure_geographic_fleet(
    body: GeographicFleetRequest,
    state: AppState = Depends(require_graph),
    db: Session = Depends(get_db),
) -> FleetResponse:
    """
    Build and store a geographic VRPProblem with automatic coordinate-to-node snapping.
    """
    from app.vrp.generator import build_geographic_vrp_problem

    graph = state.graph
    assert graph is not None

    veh_dicts = [v.model_dump() for v in body.vehicles]
    cust_dicts = [c.model_dump() for c in body.customers]

    problem = build_geographic_vrp_problem(
        graph=graph,
        vehicles=veh_dicts,
        customers=cust_dicts,
    )

    state.clear_from_fleet()
    state.problem = problem

    # Persist to PostgreSQL
    try:
        net_id = state.network_db_id
        if not net_id:
            active_net = get_active_network(db)
            if active_net:
                net_id = active_net.id
                state.network_db_id = net_id
        if net_id:
            save_fleet(db, net_id, problem.vehicles, problem.customers)
    except Exception as exc:
        logger.warning("Failed to persist geographic fleet to PostgreSQL: %s", exc)

    vehicles_out = [
        VehicleIn(
            vehicle_id=v.vehicle_id,
            capacity=v.capacity,
            depot_node=v.depot_node,
        )
        for v in problem.vehicles
    ]
    customers_out = [
        CustomerIn(
            customer_id=c.customer_id,
            location_node=c.location_node,
            demand=c.demand,
        )
        for c in problem.customers
    ]

    return FleetResponse(
        n_vehicles=len(problem.vehicles),
        n_customers=len(problem.customers),
        vehicles=vehicles_out,
        customers=customers_out,
    )


@router.post(
    "/geographic-preset",
    response_model=FleetResponse,
    status_code=status.HTTP_200_OK,
    summary="Load pre-configured real-world geographic fleet and delivery orders",
    description=(
        "Loads the canonical Bangalore central logistics fleet (2 vehicles, 6 customer "
        "orders with real GPS coordinates) and snaps them to the active OSM network."
    ),
)
def load_geographic_fleet_preset(
    state: AppState = Depends(require_graph),
    db: Session = Depends(get_db),
) -> FleetResponse:
    """
    Load canonical real-world fleet preset into AppState and PostgreSQL.
    """
    from app.graph.demo_data import REAL_WORLD_CUSTOMERS, REAL_WORLD_FLEET_VEHICLES
    from app.vrp.generator import build_geographic_vrp_problem

    graph = state.graph
    assert graph is not None

    problem = build_geographic_vrp_problem(
        graph=graph,
        vehicles=REAL_WORLD_FLEET_VEHICLES,
        customers=REAL_WORLD_CUSTOMERS,
    )

    state.clear_from_fleet()
    state.problem = problem

    try:
        net_id = state.network_db_id
        if not net_id:
            active_net = get_active_network(db)
            if active_net:
                net_id = active_net.id
                state.network_db_id = net_id
        if net_id:
            save_fleet(db, net_id, problem.vehicles, problem.customers)
    except Exception as exc:
        logger.warning("Failed to persist geographic fleet preset to PostgreSQL: %s", exc)

    vehicles_out = [
        VehicleIn(
            vehicle_id=v.vehicle_id,
            capacity=v.capacity,
            depot_node=v.depot_node,
        )
        for v in problem.vehicles
    ]
    customers_out = [
        CustomerIn(
            customer_id=c.customer_id,
            location_node=c.location_node,
            demand=c.demand,
        )
        for c in problem.customers
    ]

    return FleetResponse(
        n_vehicles=len(problem.vehicles),
        n_customers=len(problem.customers),
        vehicles=vehicles_out,
        customers=customers_out,
    )

