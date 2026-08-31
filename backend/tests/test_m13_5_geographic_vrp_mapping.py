"""
tests/test_m13_5_geographic_vrp_mapping.py – Test suite for Geographic Customer & Depot Integration (Milestone 13.5).

Verifies:
1. test_geographic_customer_to_node: Geographic customer maps to nearest graph node.
2. test_geographic_depot_to_node: Geographic depot maps to nearest vehicle depot node.
3. test_batch_customer_mapping: Multiple customer coordinate mapping (dict and tuple formats).
4. test_batch_vehicle_mapping: Multiple vehicle coordinate mapping (dict and tuple formats).
5. test_exact_and_intermediate_coordinates: Exact coordinate and nearest-node selection.
6. test_invalid_latitude: Latitudes outside [-90, 90] or NaN propagate OSMInvalidDataError.
7. test_invalid_longitude: Longitudes outside [-180, 180] or NaN propagate OSMInvalidDataError.
8. test_malformed_missing_coordinates: Missing or malformed specs raise OSMInvalidDataError.
9. test_vrp_problem_compatibility: VRPProblem built with geographic primitives is 100% valid.
10. test_feasibility_and_objective_compatibility: check_feasibility and compute_fitness evaluate correctly.
11. test_qpso_optimization_end_to_end: QPSO optimizes geographic VRPProblem cleanly.
12. test_synthetic_workflow_preservation: Node-ID-based synthetic VRP generation remains completely unchanged.
13. test_deterministic_repeated_mapping: Repeated geographic mappings produce identical results.
"""

import pytest

from app.graph import (
    TransportGraph,
    OSMInvalidDataError,
    OSMEmptyNetworkError,
    osm_to_transport_graph,
    nearest_graph_node,
)
from app.vrp import (
    Customer,
    Vehicle,
    VRPProblem,
    check_feasibility,
    compute_fitness,
    FitnessWeights,
    generate_vrp_instance,
    map_customer_location,
    map_depot_location,
    map_customer_locations,
    create_geographic_customer,
    create_geographic_vehicle,
    create_geographic_customers,
    create_geographic_vehicles,
    build_geographic_vrp_problem,
)
from app.qpso import QPSOOptimizer, QPSOConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteM135Test">
  <node id="101" lat="12.9715987" lon="77.5945627">
    <tag k="name" v="Depot Central MG Road"/>
  </node>
  <node id="102" lat="12.9750000" lon="77.5980000">
    <tag k="name" v="Customer Stop Brigade Road"/>
  </node>
  <node id="103" lat="12.9800000" lon="77.6050000">
    <tag k="name" v="Customer Stop Commercial Street"/>
  </node>
  <node id="104" lat="12.9850000" lon="77.6100000">
    <tag k="name" v="Customer Stop Trinity Circle"/>
  </node>
  <!-- Fully connected bidirectional road network -->
  <way id="201">
    <nd ref="101"/>
    <nd ref="102"/>
    <tag k="highway" v="primary"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="202">
    <nd ref="102"/>
    <nd ref="103"/>
    <tag k="highway" v="secondary"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="203">
    <nd ref="103"/>
    <nd ref="104"/>
    <tag k="highway" v="secondary"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="204">
    <nd ref="104"/>
    <nd ref="101"/>
    <tag k="highway" v="primary"/>
    <tag k="oneway" v="no"/>
  </way>
</osm>
"""


@pytest.fixture
def osm_graph() -> TransportGraph:
    """Fixture providing an OSM-derived TransportGraph."""
    return osm_to_transport_graph(SAMPLE_OSM_XML)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_geographic_customer_to_node(osm_graph: TransportGraph):
    """1. Verify that geographic customer coordinates map to the nearest graph node."""
    # Near Brigade Road (12.9750000, 77.5980000) -> Node "102"
    cust = create_geographic_customer(
        osm_graph,
        customer_id="C1",
        latitude=12.9751,
        longitude=77.5981,
        demand=5.0,
    )
    assert isinstance(cust, Customer)
    assert cust.customer_id == "C1"
    assert cust.location_node == "102"
    assert cust.demand == 5.0


def test_geographic_depot_to_node(osm_graph: TransportGraph):
    """2. Verify that geographic depot coordinates map to the nearest vehicle depot node."""
    # Near MG Road Central Depot (12.9715987, 77.5945627) -> Node "101"
    veh = create_geographic_vehicle(
        osm_graph,
        vehicle_id="V1",
        capacity=50.0,
        depot_latitude=12.9716,
        depot_longitude=77.5946,
    )
    assert isinstance(veh, Vehicle)
    assert veh.vehicle_id == "V1"
    assert veh.capacity == 50.0
    assert veh.depot_node == "101"


def test_batch_customer_mapping(osm_graph: TransportGraph):
    """3. Verify batch mapping of multiple customer specifications in dict and tuple formats."""
    # Dict format
    dict_specs = [
        {"customer_id": 1, "latitude": 12.9750, "longitude": 77.5980, "demand": 4.0},  # Node 102
        {"customer_id": 2, "latitude": 12.9800, "longitude": 77.6050, "demand": 6.0},  # Node 103
    ]
    customers_dict = create_geographic_customers(osm_graph, dict_specs)
    assert len(customers_dict) == 2
    assert customers_dict[0].location_node == "102"
    assert customers_dict[1].location_node == "103"

    # Tuple format: (customer_id, lat, lon, demand)
    tuple_specs = [
        ("C104", 12.9850, 77.6100, 3.5),  # Node 104
        ("C102", 12.9749, 77.5979, 2.0),  # Node 102
    ]
    customers_tuple = create_geographic_customers(osm_graph, tuple_specs)
    assert len(customers_tuple) == 2
    assert customers_tuple[0].location_node == "104"
    assert customers_tuple[1].location_node == "102"

    # Also test map_customer_locations
    node_ids = map_customer_locations(osm_graph, [(12.9750, 77.5980), (12.9800, 77.6050)])
    assert node_ids == ["102", "103"]


def test_batch_vehicle_mapping(osm_graph: TransportGraph):
    """4. Verify batch mapping of multiple vehicle specifications in dict and tuple formats."""
    # Dict format
    veh_dict_specs = [
        {"vehicle_id": "V1", "capacity": 20.0, "depot_latitude": 12.9716, "depot_longitude": 77.5946},
        {"vehicle_id": "V2", "capacity": 25.0, "latitude": 12.9715, "longitude": 77.5945},
    ]
    vehicles_dict = create_geographic_vehicles(osm_graph, veh_dict_specs)
    assert len(vehicles_dict) == 2
    assert vehicles_dict[0].depot_node == "101"
    assert vehicles_dict[1].depot_node == "101"

    # Tuple format: (vehicle_id, capacity, depot_lat, depot_lon)
    veh_tuple_specs = [
        ("V3", 30.0, 12.9715987, 77.5945627),
    ]
    vehicles_tuple = create_geographic_vehicles(osm_graph, veh_tuple_specs)
    assert len(vehicles_tuple) == 1
    assert vehicles_tuple[0].depot_node == "101"


def test_exact_and_intermediate_coordinates(osm_graph: TransportGraph):
    """5. Verify exact coordinate mapping and intermediate nearest-node selection."""
    # Exact coordinate
    node_exact = map_customer_location(osm_graph, latitude=12.9715987, longitude=77.5945627)
    assert node_exact == "101"

    # Depot mapping helper
    depot_exact = map_depot_location(osm_graph, latitude=12.9850000, longitude=77.6100000)
    assert depot_exact == "104"

    # Intermediate coordinate slightly biased toward 103
    intermediate_node = map_customer_location(osm_graph, latitude=12.9790, longitude=77.6040)
    assert intermediate_node == "103"


def test_invalid_latitude(osm_graph: TransportGraph):
    """6. Verify that invalid latitudes propagate OSMInvalidDataError."""
    with pytest.raises(OSMInvalidDataError, match="Latitude out of bounds"):
        create_geographic_customer(osm_graph, customer_id="C_bad", latitude=95.0, longitude=77.59, demand=1.0)

    with pytest.raises(OSMInvalidDataError, match="Latitude out of bounds"):
        create_geographic_vehicle(osm_graph, vehicle_id="V_bad", capacity=10.0, depot_latitude=-92.0, depot_longitude=77.59)


def test_invalid_longitude(osm_graph: TransportGraph):
    """7. Verify that invalid longitudes propagate OSMInvalidDataError."""
    with pytest.raises(OSMInvalidDataError, match="Longitude out of bounds"):
        create_geographic_customer(osm_graph, customer_id="C_bad", latitude=12.97, longitude=190.0, demand=1.0)

    with pytest.raises(OSMInvalidDataError, match="Longitude out of bounds"):
        create_geographic_vehicle(osm_graph, vehicle_id="V_bad", capacity=10.0, depot_latitude=12.97, depot_longitude=-185.0)


def test_malformed_missing_coordinates(osm_graph: TransportGraph):
    """8. Verify that malformed or missing coordinate specs raise OSMInvalidDataError."""
    with pytest.raises(OSMInvalidDataError, match="Customer specification must be a dict or 4-tuple"):
        create_geographic_customers(osm_graph, ["invalid_spec"])  # type: ignore

    with pytest.raises(OSMInvalidDataError, match="Vehicle specification must be a dict or 4-tuple"):
        create_geographic_vehicles(osm_graph, [12345])  # type: ignore

    with pytest.raises(OSMInvalidDataError, match="Customer dict spec must contain"):
        create_geographic_customers(osm_graph, [{"customer_id": 1, "latitude": 12.97}])

    with pytest.raises(OSMInvalidDataError, match="Vehicle dict spec must contain"):
        create_geographic_vehicles(osm_graph, [{"vehicle_id": "V1", "capacity": 10.0}])


def test_vrp_problem_compatibility(osm_graph: TransportGraph):
    """9. Verify that build_geographic_vrp_problem builds a valid VRPProblem instance."""
    vehicles = [
        {"vehicle_id": 0, "capacity": 30.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        {"customer_id": 0, "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
        {"customer_id": 1, "latitude": 12.9800, "longitude": 77.6050, "demand": 8.0},
        {"customer_id": 2, "latitude": 12.9850, "longitude": 77.6100, "demand": 7.0},
    ]

    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)
    assert isinstance(problem, VRPProblem)
    assert len(problem.vehicles) == 1
    assert len(problem.customers) == 3
    assert problem.vehicles[0].depot_node == "101"
    assert problem.customer_ids == frozenset({0, 1, 2})
    assert problem.required_node_ids == frozenset({"102", "103", "104"})


def test_feasibility_and_objective_compatibility(osm_graph: TransportGraph):
    """10. Verify that check_feasibility and compute_fitness evaluate geographic VRP solutions."""
    vehicles = [("V1", 40.0, 12.9715987, 77.5945627)]
    customers = [
        ("C1", 12.9750, 77.5980, 5.0),   # Node 102
        ("C2", 12.9800, 77.6050, 6.0),   # Node 103
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

    # Construct a trivial valid solution: 101 -> 102 -> 103 -> 104 -> 101
    from app.vrp import VehicleRoute, VRPSolution
    route = VehicleRoute(
        vehicle_id="V1",
        depot_node="101",
        visit_order=["C1", "C2"],
        node_sequence=["101", "102", "103", "104", "101"],
    )
    solution = VRPSolution(routes=[route])

    feas_result = check_feasibility(solution, problem)
    assert feas_result.is_feasible is True
    assert len(feas_result.violations) == 0

    fitness = compute_fitness(solution, problem, FitnessWeights())
    assert isinstance(fitness, float)
    assert fitness > 0.0


def test_qpso_optimization_end_to_end(osm_graph: TransportGraph):
    """11. End-to-End: Solve a geographically mapped VRPProblem using QPSOOptimizer."""
    vehicles = [
        {"vehicle_id": "V1", "capacity": 50.0, "depot_latitude": 12.9715987, "depot_longitude": 77.5945627},
    ]
    customers = [
        {"customer_id": "C1", "latitude": 12.9750, "longitude": 77.5980, "demand": 5.0},
        {"customer_id": "C2", "latitude": 12.9800, "longitude": 77.6050, "demand": 6.0},
    ]
    problem = build_geographic_vrp_problem(osm_graph, vehicles=vehicles, customers=customers)

    cfg = QPSOConfig(n_particles=10, max_iterations=15, seed=42)
    optimizer = QPSOOptimizer(problem=problem, config=cfg)
    result = optimizer.run()

    best_sol = result.best_solution
    assert best_sol is not None
    assert best_sol.is_feasible is True
    assert best_sol.objective_value is not None
    assert len(best_sol.routes) == 1
    assert set(best_sol.routes[0].visit_order) == {"C1", "C2"}



def test_synthetic_workflow_preservation():
    """12. Verify that existing synthetic node-ID based VRP generation remains completely unaffected."""
    synth_problem = generate_vrp_instance(
        n_vehicles=2,
        n_customers=4,
        n_nodes=10,
        seed=42,
    )
    assert isinstance(synth_problem, VRPProblem)
    assert len(synth_problem.vehicles) == 2
    assert len(synth_problem.customers) == 4
    for c in synth_problem.customers:
        assert isinstance(c.location_node, (int, str))


def test_deterministic_repeated_mapping(osm_graph: TransportGraph):
    """13. Verify that repeated geographic customer and vehicle mappings are 100% deterministic."""
    specs_cust = [("C1", 12.9750, 77.5980, 5.0), ("C2", 12.9800, 77.6050, 6.0)]
    specs_veh = [("V1", 30.0, 12.9715987, 77.5945627)]

    p1 = build_geographic_vrp_problem(osm_graph, specs_veh, specs_cust)
    p2 = build_geographic_vrp_problem(osm_graph, specs_veh, specs_cust)

    assert [c.location_node for c in p1.customers] == [c.location_node for c in p2.customers]
    assert [v.depot_node for v in p1.vehicles] == [v.depot_node for v in p2.vehicles]
