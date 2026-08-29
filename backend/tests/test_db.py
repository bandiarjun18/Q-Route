"""
tests/test_db.py – Database connectivity, schema, and ORM model tests for Phase 2.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.base import Base
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
from app.db.session import SessionLocal, engine


@pytest.fixture
def db_session() -> Session:
    """Provides an isolated database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_database_connection_and_tables():
    """Verify that PostgreSQL connection succeeds and all 8 domain tables exist."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "networks",
        "nodes",
        "edges",
        "fleet_vehicles",
        "customers",
        "optimization_runs",
        "routes",
        "incidents",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_network_and_graph_entities_crud(db_session: Session):
    """Test creating, querying, and deleting Network with Nodes and Edges."""
    net_id = str(uuid.uuid4())
    net = NetworkModel(
        id=net_id,
        name="Test Network",
        n_nodes=4,
        n_edges=4,
        n_depots=1,
        n_customers=2,
        n_intersections=1,
        seed=42,
        connect_radius_km=3.5,
        grid_size_km=10.0,
        closed_fraction=0.0,
        is_active=True,
    )
    db_session.add(net)

    # Add Nodes
    n1 = NodeModel(network_id=net_id, node_id="0", node_type="depot", x=0.0, y=0.0)
    n2 = NodeModel(network_id=net_id, node_id="1", node_type="customer", x=2.0, y=3.0)
    db_session.add_all([n1, n2])

    # Add Edges
    e1 = EdgeModel(
        network_id=net_id,
        u="0",
        v="1",
        distance=3.6,
        base_travel_time=5.0,
        congestion_factor=1.0,
        road_status="open",
    )
    db_session.add(e1)
    db_session.commit()

    # Query back
    saved_net = db_session.execute(
        select(NetworkModel).where(NetworkModel.id == net_id)
    ).scalar_one()
    assert saved_net.n_nodes == 4
    assert len(saved_net.nodes) == 2
    assert len(saved_net.edges) == 1
    assert saved_net.edges[0].distance == 3.6

    # Cleanup (tests cascade delete)
    db_session.delete(saved_net)
    db_session.commit()

    # Confirm cascade deleted nodes and edges
    remaining_nodes = db_session.execute(
        select(NodeModel).where(NodeModel.network_id == net_id)
    ).scalars().all()
    assert len(remaining_nodes) == 0


def test_fleet_and_optimization_models_crud(db_session: Session):
    """Test full pipeline persistence from fleet to optimization run and routes."""
    net_id = str(uuid.uuid4())
    net = NetworkModel(
        id=net_id,
        name="Opt Test Net",
        n_nodes=3,
        n_edges=2,
        n_depots=1,
        n_customers=2,
        n_intersections=0,
        seed=100,
        connect_radius_km=5.0,
        grid_size_km=10.0,
    )
    db_session.add(net)

    # Vehicles and Customers
    veh = FleetVehicleModel(network_id=net_id, vehicle_id="V1", capacity=15.0, depot_node="0")
    cust = CustomerModel(network_id=net_id, customer_id="C1", location_node="1", demand=5.0)
    db_session.add_all([veh, cust])
    db_session.commit()

    # Optimization Run
    opt_id = str(uuid.uuid4())
    opt_run = OptimizationRunModel(
        id=opt_id,
        network_id=net_id,
        seed=42,
        n_particles=10,
        max_iterations=20,
        w_time=1.0,
        w_distance=0.5,
        w_congestion=0.3,
        best_fitness=45.67,
        is_feasible=True,
        n_iterations_run=15,
        stopped_early=False,
        convergence_history={"0": 60.0, "5": 50.0, "15": 45.67},
    )
    db_session.add(opt_run)
    db_session.flush()

    # Route
    route = RouteModel(
        optimization_run_id=opt_id,
        route_id="V1-001",
        vehicle_id="V1",
        depot_node="0",
        visit_order=["C1"],
        node_sequence=["0", "1", "0"],
        total_distance=12.4,
        total_travel_time=18.5,
        estimated_arrival=18.5,
        status="active",
    )
    db_session.add(route)

    # Incident
    inc = IncidentModel(
        network_id=net_id,
        optimization_run_id=opt_id,
        edge_u="0",
        edge_v="1",
        incident_type="ACCIDENT",
        severity="HIGH",
        description="Collision on link 0->1",
        is_closure=False,
        is_active=True,
    )
    db_session.add(inc)
    db_session.commit()

    # Verify query
    saved_opt = db_session.execute(
        select(OptimizationRunModel).where(OptimizationRunModel.id == opt_id)
    ).scalar_one()
    assert saved_opt.best_fitness == 45.67
    assert saved_opt.is_feasible is True
    assert saved_opt.convergence_history["15"] == 45.67
    assert len(saved_opt.routes) == 1
    assert saved_opt.routes[0].node_sequence == ["0", "1", "0"]

    # Cleanup
    db_session.delete(net)
    db_session.commit()


def test_crud_helpers(db_session: Session):
    """Test higher-level CRUD helper functions from app.db.crud."""
    from app.db.crud import (
        get_active_network,
        get_latest_optimization_run,
        save_fleet,
        save_incident,
        save_network,
        save_optimization_run,
    )
    from app.graph.generator import generate_synthetic_network

    # 1. Save synthetic network
    net_data = generate_synthetic_network(n_nodes=6, n_depots=1, n_customers=2, seed=42)
    net_model = save_network(
        db=db_session,
        net_data=net_data,
        seed=42,
        connect_radius_km=4.0,
        grid_size_km=10.0,
        closed_fraction=0.0,
        name="CRUD Test Net",
    )
    assert net_model.id is not None
    assert net_model.is_active is True

    # 2. Get active network
    active_net = get_active_network(db_session)
    assert active_net is not None
    assert active_net.id == net_model.id

    # 3. Save fleet
    from app.vrp.models import Customer, Vehicle
    vehs = [Vehicle(vehicle_id="V1", capacity=10.0, depot_node="0")]
    custs = [Customer(customer_id="C1", location_node="1", demand=3.0)]
    veh_models, cust_models = save_fleet(db_session, net_model.id, vehs, custs)
    assert len(veh_models) == 1
    assert len(cust_models) == 1

    # 4. Save optimization run
    from app.routes.model import ActiveRoute
    from app.vrp.models import VRPSolution

    class DummyResult:
        best_fitness = 55.5
        best_solution = VRPSolution(is_feasible=True)
        n_iterations_run = 20
        stopped_early = False
        pre_repair_fitness = 60.0
        post_repair_fitness = 55.5
        convergence_history = {0: 70.0, 10: 60.0, 20: 55.5}

    active_route = ActiveRoute(
        route_id="V1-001",
        vehicle_id="V1",
        depot_node="0",
        visit_order=["C1"],
        node_sequence=["0", "1", "0"],
        total_distance=10.0,
        total_travel_time=15.0,
    )

    opt_model = save_optimization_run(
        db=db_session,
        network_id=net_model.id,
        config={"seed": 42, "n_particles": 10, "max_iterations": 20},
        result=DummyResult(),
        active_routes=[active_route],
    )
    assert opt_model.best_fitness == 55.5
    assert len(opt_model.routes) == 1

    # 5. Save incident
    inc_model = save_incident(
        db=db_session,
        network_id=net_model.id,
        optimization_run_id=opt_model.id,
        edge_u="0",
        edge_v="1",
        incident_type="ROAD_CLOSURE",
        severity="CRITICAL",
        description="Road blocked",
        is_closure=True,
    )
    assert inc_model.is_closure is True

    # 6. Query latest run
    latest = get_latest_optimization_run(db_session, net_model.id)
    assert latest is not None
    assert latest.id == opt_model.id

    # Cleanup
    db_session.delete(net_model)
    db_session.commit()

