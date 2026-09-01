"""
app/db/crud.py – Database CRUD operations for Q-Route API boundary.

Provides data access helpers for:
- Creating / querying Networks, Nodes, and Edges
- Saving Fleet configurations (Vehicles & Customers)
- Recording Optimization Runs, Convergence Histories, and Route records
- Registering Road Incidents and updating Edge statuses
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import (
    CustomerModel,
    EdgeModel,
    FleetVehicleModel,
    IncidentModel,
    NetworkModel,
    NodeModel,
    OptimizationRunModel,
    RouteModel,
)


def get_active_network(db: Session) -> Optional[NetworkModel]:
    """Retrieve the currently active network record."""
    stmt = (
        select(NetworkModel)
        .where(NetworkModel.is_active == True)
        .order_by(NetworkModel.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def save_network(
    db: Session,
    net_data: dict[str, Any],
    seed: int,
    connect_radius_km: float,
    grid_size_km: float,
    closed_fraction: float,
    name: str = "Synthetic Network",
) -> NetworkModel:
    """
    Deactivates any previous networks, creates a new Network record,
    and bulk-inserts associated nodes and edges.
    """
    # Deactivate existing networks
    db.execute(
        update(NetworkModel)
        .where(NetworkModel.is_active == True)
        .values(is_active=False)
    )

    nodes_raw = net_data.get("nodes", [])
    edges_raw = net_data.get("edges", [])

    # Normalize nodes to list of dicts
    if isinstance(nodes_raw, dict):
        nodes_list = [{"id": k, **v} for k, v in nodes_raw.items()]
    else:
        nodes_list = list(nodes_raw)

    edges_list = list(edges_raw)

    n_nodes = len(nodes_list)
    n_edges = len(edges_list)
    n_depots = sum(1 for d in nodes_list if d.get("node_type") == "depot")
    n_customers = sum(1 for d in nodes_list if d.get("node_type") == "customer")
    n_intersections = sum(
        1 for d in nodes_list if d.get("node_type") == "intersection"
    )

    net_id = str(uuid.uuid4())
    network = NetworkModel(
        id=net_id,
        name=name,
        n_nodes=n_nodes,
        n_edges=n_edges,
        n_depots=n_depots,
        n_customers=n_customers,
        n_intersections=n_intersections,
        seed=seed,
        connect_radius_km=connect_radius_km,
        grid_size_km=grid_size_km,
        closed_fraction=closed_fraction,
        is_active=True,
    )
    db.add(network)

    # Bulk create Node records
    node_models = [
        NodeModel(
            network_id=net_id,
            node_id=str(ndata.get("id")),
            node_type=ndata.get("node_type", "intersection"),
            x=float(ndata.get("x", 0.0)),
            y=float(ndata.get("y", 0.0)),
        )
        for ndata in nodes_list
    ]
    db.add_all(node_models)

    # Bulk create Edge records
    edge_models = [
        EdgeModel(
            network_id=net_id,
            u=str(edata.get("u")),
            v=str(edata.get("v")),
            distance=float(edata.get("distance", 0.0)),
            base_travel_time=float(edata.get("base_travel_time", 0.0)),
            congestion_factor=float(edata.get("congestion_factor", 1.0)),
            road_status=str(edata.get("road_status", "open")),
        )
        for edata in edges_list
    ]
    db.add_all(edge_models)

    db.commit()
    db.refresh(network)
    return network


def save_fleet(
    db: Session,
    network_id: str,
    vehicles: list[Any],
    customers: list[Any],
) -> tuple[list[FleetVehicleModel], list[CustomerModel]]:
    """Save fleet vehicles and customer delivery orders for a network."""
    # Remove any existing fleet/customers for this network to avoid duplicates
    db.query(FleetVehicleModel).filter(FleetVehicleModel.network_id == network_id).delete()
    db.query(CustomerModel).filter(CustomerModel.network_id == network_id).delete()

    veh_models = [
        FleetVehicleModel(
            network_id=network_id,
            vehicle_id=str(v.vehicle_id),
            capacity=float(v.capacity),
            depot_node=str(v.depot_node),
        )
        for v in vehicles
    ]
    db.add_all(veh_models)

    cust_models = [
        CustomerModel(
            network_id=network_id,
            customer_id=str(c.customer_id),
            location_node=str(c.location_node),
            demand=float(c.demand),
        )
        for c in customers
    ]
    db.add_all(cust_models)

    db.commit()
    return veh_models, cust_models


def save_optimization_run(
    db: Session,
    network_id: str,
    config: dict[str, Any],
    result: Any,
    active_routes: list[Any],
) -> OptimizationRunModel:
    """Save optimization run metadata, convergence history, and active routes."""
    opt_id = str(uuid.uuid4())

    conv_hist_raw = getattr(result, "convergence_history", {}) or {}
    if isinstance(conv_hist_raw, dict):
        conv_hist = {str(k): float(v) for k, v in conv_hist_raw.items()}
    else:
        conv_hist = {}

    best_fitness = getattr(result, "best_fitness", None)
    if best_fitness is None:
        best_fitness = getattr(result, "post_incident_fitness", 0.0)

    is_feasible = getattr(result, "is_feasible", None)
    if is_feasible is None and hasattr(result, "best_solution"):
        is_feasible = getattr(result.best_solution, "is_feasible", True)
    if is_feasible is None:
        is_feasible = True

    opt_run = OptimizationRunModel(
        id=opt_id,
        network_id=network_id,
        seed=int(config.get("seed", 42)),
        n_particles=int(config.get("n_particles", 20)),
        max_iterations=int(config.get("max_iterations", 100)),
        w_time=float(config.get("w_time", 1.0)),
        w_distance=float(config.get("w_distance", 0.5)),
        w_congestion=float(config.get("w_congestion", 0.3)),
        best_fitness=float(best_fitness or 0.0),
        is_feasible=bool(is_feasible),
        n_iterations_run=int(getattr(result, "n_iterations_run", 0)),
        stopped_early=bool(getattr(result, "stopped_early", False)),
        pre_repair_fitness=(
            float(result.pre_repair_fitness)
            if getattr(result, "pre_repair_fitness", None) is not None
            else None
        ),
        post_repair_fitness=(
            float(result.post_repair_fitness)
            if getattr(result, "post_repair_fitness", None) is not None
            else None
        ),
        convergence_history=conv_hist,
    )
    db.add(opt_run)
    db.flush()

    route_models = [
        RouteModel(
            optimization_run_id=opt_id,
            route_id=str(ar.route_id),
            vehicle_id=str(ar.vehicle_id),
            depot_node=str(ar.depot_node),
            visit_order=list(ar.visit_order),
            node_sequence=list(ar.node_sequence),
            total_distance=float(ar.total_distance),
            total_travel_time=float(ar.total_travel_time),
            estimated_arrival=(
                float(ar.estimated_arrival)
                if ar.estimated_arrival is not None
                else None
            ),
            status=str(ar.status.value if hasattr(ar.status, "value") else ar.status),
        )
        for ar in active_routes
    ]
    db.add_all(route_models)

    db.commit()
    db.refresh(opt_run)
    return opt_run


def save_incident(
    db: Session,
    network_id: str,
    optimization_run_id: Optional[str],
    edge_u: str,
    edge_v: str,
    incident_type: str,
    severity: str,
    description: str,
    is_closure: bool,
) -> IncidentModel:
    """Record an incident event in the database."""
    inc = IncidentModel(
        network_id=network_id,
        optimization_run_id=optimization_run_id,
        edge_u=str(edge_u),
        edge_v=str(edge_v),
        incident_type=str(incident_type),
        severity=str(severity),
        description=str(description),
        is_closure=bool(is_closure),
        is_active=True,
    )
    db.add(inc)

    # Also update edge road_status or congestion in the edges table if needed
    if is_closure:
        db.execute(
            update(EdgeModel)
            .where(
                EdgeModel.network_id == network_id,
                EdgeModel.u == str(edge_u),
                EdgeModel.v == str(edge_v),
            )
            .values(road_status="closed")
        )

    db.commit()
    db.refresh(inc)
    return inc


def get_latest_optimization_run(
    db: Session, network_id: Optional[str] = None
) -> Optional[OptimizationRunModel]:
    """Retrieve the most recent optimization run."""
    stmt = select(OptimizationRunModel).order_by(
        OptimizationRunModel.created_at.desc()
    )
    if network_id:
        stmt = stmt.where(OptimizationRunModel.network_id == network_id)
    return db.execute(stmt).scalars().first()


def get_network_by_id(db: Session, network_id: str) -> Optional[NetworkModel]:
    """Retrieve a network record by ID."""
    stmt = select(NetworkModel).where(NetworkModel.id == network_id)
    return db.execute(stmt).scalars().first()


def get_routes_for_optimization(
    db: Session, optimization_run_id: str
) -> list[RouteModel]:
    """Retrieve all routes associated with an optimization run."""
    stmt = select(RouteModel).where(
        RouteModel.optimization_run_id == optimization_run_id
    )
    return list(db.execute(stmt).scalars().all())


def get_incidents_for_network(
    db: Session, network_id: str, active_only: bool = True
) -> list[IncidentModel]:
    """Retrieve incidents recorded for a given network."""
    stmt = select(IncidentModel).where(IncidentModel.network_id == network_id)
    if active_only:
        stmt = stmt.where(IncidentModel.is_active == True)
    return list(db.execute(stmt).scalars().all())


def delete_network(db: Session, network_id: str) -> bool:
    """Delete a network record and cascade-delete associated entities."""
    net = get_network_by_id(db, network_id)
    if not net:
        return False
    db.delete(net)
    db.commit()
    return True


def get_fleet_for_network(
    db: Session, network_id: str
) -> tuple[list[FleetVehicleModel], list[CustomerModel]]:
    """Retrieve fleet vehicles and customer orders saved for a network."""
    veh_stmt = select(FleetVehicleModel).where(
        FleetVehicleModel.network_id == network_id
    )
    cust_stmt = select(CustomerModel).where(
        CustomerModel.network_id == network_id
    )
    vehs = list(db.execute(veh_stmt).scalars().all())
    custs = list(db.execute(cust_stmt).scalars().all())
    return vehs, custs


def get_network_nodes_and_edges(
    db: Session, network_id: str
) -> tuple[list[NodeModel], list[EdgeModel]]:
    """Retrieve nodes and edges for a given network."""
    node_stmt = select(NodeModel).where(NodeModel.network_id == network_id)
    edge_stmt = select(EdgeModel).where(EdgeModel.network_id == network_id)
    nodes = list(db.execute(node_stmt).scalars().all())
    edges = list(db.execute(edge_stmt).scalars().all())
    return nodes, edges
