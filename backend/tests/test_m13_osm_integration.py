"""
tests/test_m13_osm_integration.py – Test suite for OSM → TransportGraph Integration (Milestone 13.3).

Verifies:
1. test_osm_to_transport_graph: Normalized OSM input converts cleanly into TransportGraph.
2. test_osm_node_mapping: Expected OSM nodes exist with correct IDs and attributes.
3. test_osm_directed_edges: Directed edges and oneway semantics are accurately preserved.
4. test_osm_edge_weights: Converted edges contain valid routing weights (distance, travel time, congestion, status).
5. test_osm_coordinates_preserved: Geographic coordinates (x=lon, y=lat) are accurately stored.
6. test_osm_deterministic_conversion: Repeated conversions yield identical graph structures and weights.
7. test_osm_graph_is_routeable: Dijkstra shortest_path operates seamlessly across the OSM graph.
8. test_existing_synthetic_graph_regression: Synthetic network generation remains completely unaffected.
9. test_osm_vrp_problem_integration: End-to-end integration proving OSM-derived TransportGraph constructs valid VRPProblem.
"""

import math
import pytest
import networkx as nx

from app.graph import (
    TransportGraph,
    WeightConfig,
    shortest_path,
    path_cost,
    generate_synthetic_network,
    build_transport_graph,
    OSMConfig,
    osm_to_network_dict,
    osm_to_transport_graph,
    load_osm_network,
)
from app.vrp.models import Customer, Vehicle, VRPProblem
from app.vrp.generator import generate_vrp_instance, vrp_problem_to_dict, vrp_problem_from_dict
from app.vrp.feasibility import check_feasibility
from app.vrp.objective import compute_fitness


# ---------------------------------------------------------------------------
# Synthetic Deterministic OSM Fixtures
# ---------------------------------------------------------------------------

SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteIntegrationTest">
  <node id="101" lat="12.9715987" lon="77.5945627">
    <tag k="name" v="MG Road Intersection"/>
  </node>
  <node id="102" lat="12.9750000" lon="77.5980000">
    <tag k="name" v="Brigade Road Crossing"/>
  </node>
  <node id="103" lat="12.9800000" lon="77.6050000">
    <tag k="name" v="Commercial Street Junction"/>
  </node>
  <node id="104" lat="12.9850000" lon="77.6100000">
    <tag k="name" v="Non-motorized Node"/>
  </node>

  <!-- Bidirectional primary road: 101 <-> 102 -->
  <way id="201">
    <nd ref="101"/>
    <nd ref="102"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="MG Road"/>
    <tag k="maxspeed" v="60 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Oneway tertiary road: 102 -> 103 -->
  <way id="202">
    <nd ref="102"/>
    <nd ref="103"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Residency Road"/>
    <tag k="maxspeed" v="40"/>
    <tag k="oneway" v="yes"/>
  </way>

  <!-- Non-motorized pedestrian path (filtered out) -->
  <way id="203">
    <nd ref="103"/>
    <nd ref="104"/>
    <tag k="highway" v="footway"/>
  </way>
</osm>
"""

SAMPLE_NORMALIZED_NETWORK_DICT = {
    "meta": {
        "source": "OpenStreetMap",
        "node_count": 3,
        "edge_count": 3,
    },
    "nodes": [
        {"id": "101", "node_type": "intersection", "x": 77.5945627, "y": 12.9715987, "lat": 12.9715987, "lon": 77.5945627},
        {"id": "102", "node_type": "intersection", "x": 77.5980000, "y": 12.9750000, "lat": 12.9750000, "lon": 77.5980000},
        {"id": "103", "node_type": "intersection", "x": 77.6050000, "y": 12.9800000, "lat": 12.9800000, "lon": 77.6050000},
    ],
    "edges": [
        {
            "u": "101",
            "v": "102",
            "distance": 0.525,
            "base_travel_time": 0.525,
            "congestion_factor": 1.0,
            "road_status": "open",
            "osm_way_id": "201",
            "highway": "primary",
            "speed_kmh": 60.0,
            "oneway": False,
        },
        {
            "u": "102",
            "v": "101",
            "distance": 0.525,
            "base_travel_time": 0.525,
            "congestion_factor": 1.0,
            "road_status": "open",
            "osm_way_id": "201",
            "highway": "primary",
            "speed_kmh": 60.0,
            "oneway": False,
        },
        {
            "u": "102",
            "v": "103",
            "distance": 0.950,
            "base_travel_time": 1.425,
            "congestion_factor": 1.0,
            "road_status": "open",
            "osm_way_id": "202",
            "highway": "tertiary",
            "speed_kmh": 40.0,
            "oneway": True,
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_osm_to_transport_graph():
    """1. Verify that normalized OSM input converts into a valid TransportGraph."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    assert isinstance(graph, TransportGraph)
    assert graph.node_count() == 3
    assert graph.edge_count() == 3

    # Also test passing raw XML
    graph_xml = osm_to_transport_graph(SAMPLE_OSM_XML)
    assert isinstance(graph_xml, TransportGraph)
    assert graph_xml.node_count() == 3
    assert graph_xml.edge_count() == 3


def test_osm_node_mapping():
    """2. Verify that OSM nodes are mapped to Q-Route graph nodes with correct attributes."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    raw_g = graph.graph

    assert "101" in raw_g.nodes
    assert "102" in raw_g.nodes
    assert "103" in raw_g.nodes

    n101 = raw_g.nodes["101"]
    assert n101["node_type"] == "intersection"
    assert pytest.approx(n101["x"], rel=1e-5) == 77.5945627
    assert pytest.approx(n101["y"], rel=1e-5) == 12.9715987


def test_osm_directed_edges():
    """3. Verify that directed road relationships and oneway constraints are preserved."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    raw_g = graph.graph

    # Bidirectional edges for Way 201
    assert raw_g.has_edge("101", "102")
    assert raw_g.has_edge("102", "101")

    # One-way edge for Way 202 (102 -> 103 only)
    assert raw_g.has_edge("102", "103")
    assert not raw_g.has_edge("103", "102")


def test_osm_edge_weights():
    """4. Verify that converted edges contain all required Q-Route routing weights."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    raw_g = graph.graph

    edge_data = raw_g["101"]["102"]
    assert edge_data["distance"] == 0.525
    assert edge_data["base_travel_time"] == 0.525
    assert edge_data["congestion_factor"] == 1.0
    assert edge_data["road_status"] == "open"
    assert edge_data["highway"] == "primary"
    assert edge_data["speed_kmh"] == 60.0


def test_osm_coordinates_preserved():
    """5. Verify geographic coordinate preservation (x=longitude, y=latitude)."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    raw_g = graph.graph

    for nid in ["101", "102", "103"]:
        node = raw_g.nodes[nid]
        assert "x" in node
        assert "y" in node
        assert "lat" in node
        assert "lon" in node
        assert node["x"] == node["lon"]
        assert node["y"] == node["lat"]


def test_osm_deterministic_conversion():
    """6. Verify that repeated conversion of identical input produces identical graphs."""
    graph1 = osm_to_transport_graph(SAMPLE_OSM_XML)
    graph2 = osm_to_transport_graph(SAMPLE_OSM_XML)

    assert graph1.to_dict() == graph2.to_dict()
    assert graph1.node_count() == graph2.node_count()
    assert graph1.edge_count() == graph2.edge_count()


def test_osm_graph_is_routeable():
    """7. Verify that Dijkstra pathfinding operates seamlessly on the OSM graph."""
    graph = osm_to_transport_graph(SAMPLE_NORMALIZED_NETWORK_DICT)
    wc = WeightConfig(w_time=1.0, w_distance=0.5, w_congestion=0.3)

    path, cost = shortest_path(graph, "101", "103", wc)
    assert path == ["101", "102", "103"]
    assert cost > 0.0
    assert not math.isinf(cost)

    # Against one-way: 103 -> 101 must raise NetworkXNoPath
    with pytest.raises(nx.NetworkXNoPath):
        shortest_path(graph, "103", "101", wc)


def test_existing_synthetic_graph_regression():
    """8. Verify that synthetic network generation remains completely intact."""
    synth_dict = generate_synthetic_network(n_nodes=10, seed=42)
    synth_graph = build_transport_graph(synth_dict)

    assert isinstance(synth_graph, TransportGraph)
    assert synth_graph.node_count() == 10
    assert synth_graph.edge_count() > 0


def test_osm_vrp_problem_integration():
    """9. End-to-End: Convert OSM TransportGraph into a VRPProblem instance."""
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

    # Configure one node as depot and two as customers
    osm_graph.graph.nodes["101"]["node_type"] = "depot"
    osm_graph.graph.nodes["102"]["node_type"] = "customer"
    osm_graph.graph.nodes["103"]["node_type"] = "customer"

    problem = generate_vrp_instance(
        n_vehicles=1,
        n_customers=2,
        graph=osm_graph,
        seed=42,
    )

    assert isinstance(problem, VRPProblem)
    assert problem.graph.node_count() == 3
    assert len(problem.vehicles) == 1
    assert len(problem.customers) == 2
    assert problem.vehicles[0].depot_node == "101"

    # Verify problem serialisation and deserialisation
    serialized = vrp_problem_to_dict(problem)
    deserialized = vrp_problem_from_dict(serialized)
    assert deserialized.graph.node_count() == 3
    assert len(deserialized.vehicles) == 1
    assert len(deserialized.customers) == 2
