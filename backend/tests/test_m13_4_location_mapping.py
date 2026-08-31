"""
tests/test_m13_4_location_mapping.py – Test suite for Real-World Location to Graph Node Mapping (Milestone 13.4).

Verifies:
1. test_nearest_node_exact_coordinate: Exact coordinate matches a graph node (0 km distance).
2. test_nearest_node_between_nodes: Nearest node selected among multiple candidates.
3. test_nearest_node_haversine_behavior: Validates great-circle Haversine calculation over Cartesian degree distortion.
4. test_invalid_latitude: Latitudes outside [-90, 90], NaN, or non-numeric types raise clear errors.
5. test_invalid_longitude: Longitudes outside [-180, 180], NaN, or non-numeric types raise clear errors.
6. test_graph_without_coordinates: Graphs without geographic coordinate attributes fail with OSMInvalidDataError.
7. test_malformed_node_coordinates: Malformed node coordinates are safely handled/skipped.
8. test_empty_graph: Empty graph raises OSMEmptyNetworkError.
9. test_deterministic_tie_break: Equidistant candidates produce 100% deterministic tie-breaking.
10. test_existing_osm_graph_compatibility: Real OSM-ingested TransportGraph integrates cleanly.
11. test_customer_depot_adapters: Adapters map single/batch coordinates to TransportGraph node IDs.
12. test_return_distance_option: return_distance=True accurately returns (node_id, distance_km).
"""

import math
import pytest

from app.graph import (
    TransportGraph,
    OSMInvalidDataError,
    OSMEmptyNetworkError,
    osm_to_transport_graph,
    nearest_graph_node,
    map_coordinate_to_node,
    map_coordinates_to_nodes,
)


# ---------------------------------------------------------------------------
# Synthetic Deterministic Fixtures
# ---------------------------------------------------------------------------

SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteMappingTest">
  <node id="101" lat="12.9715987" lon="77.5945627">
    <tag k="name" v="MG Road"/>
  </node>
  <node id="102" lat="12.9750000" lon="77.5980000">
    <tag k="name" v="Brigade Road"/>
  </node>
  <node id="103" lat="12.9800000" lon="77.6050000">
    <tag k="name" v="Commercial Street"/>
  </node>
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
</osm>
"""


def _create_simple_geo_graph() -> TransportGraph:
    """Helper to construct a simple 3-node geographic TransportGraph."""
    tg = TransportGraph()
    # Node A: (12.970, 77.590)
    tg.add_node("node_A", lat=12.970, lon=77.590, x=77.590, y=12.970)
    # Node B: (12.975, 77.595)
    tg.add_node("node_B", lat=12.975, lon=77.595, x=77.595, y=12.975)
    # Node C: (12.980, 77.600)
    tg.add_node("node_C", lat=12.980, lon=77.600, x=77.600, y=12.980)

    tg.add_edge("node_A", "node_B", distance=0.77, base_travel_time=1.0)
    tg.add_edge("node_B", "node_C", distance=0.77, base_travel_time=1.0)
    return tg


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_nearest_node_exact_coordinate():
    """1. Verify that a coordinate matching an exact graph node selects that node."""
    graph = _create_simple_geo_graph()

    # Query exact coordinate of node_B
    node_id = nearest_graph_node(graph, latitude=12.975, longitude=77.595)
    assert node_id == "node_B"

    # Query with return_distance
    node_id, dist_km = nearest_graph_node(graph, latitude=12.975, longitude=77.595, return_distance=True)
    assert node_id == "node_B"
    assert pytest.approx(dist_km, abs=1e-6) == 0.0


def test_nearest_node_between_nodes():
    """2. Verify that a coordinate falling between multiple nodes selects the closest one."""
    graph = _create_simple_geo_graph()

    # (12.9702, 77.5902) is very close to node_A (12.970, 77.590)
    assert nearest_graph_node(graph, latitude=12.9702, longitude=77.5902) == "node_A"

    # (12.9798, 77.5998) is very close to node_C (12.980, 77.600)
    assert nearest_graph_node(graph, latitude=12.9798, longitude=77.5998) == "node_C"


def test_nearest_node_haversine_behavior():
    """
    3. Verify that true geodesic Haversine distance is used rather than Cartesian degree arithmetic.

    At high latitudes (e.g. 60° N), 1 degree of longitude is ~55.66 km, whereas 1 degree
    of latitude is ~111.32 km.
    - Node Lat: (60.6°, 0.0°) -> delta_lat = 0.6°, delta_lon = 0.0°
      Degree Euclidean distance: sqrt(0.6^2) = 0.60°
      Haversine distance: ~66.7 km
    - Node Lon: (60.0°, 0.9°) -> delta_lat = 0.0°, delta_lon = 0.9°
      Degree Euclidean distance: sqrt(0.9^2) = 0.90° (Larger in Cartesian degrees!)
      Haversine distance: ~50.1 km (Smaller in true geodesic distance!)

    Query point: (60.0°, 0.0°)
    Cartesian degree metric would mistakenly pick 'node_lat' (0.60° < 0.90°).
    Haversine correctly picks 'node_lon' (50.1 km < 66.7 km).
    """
    tg = TransportGraph()
    tg.add_node("node_lat", lat=60.6, lon=0.0)
    tg.add_node("node_lon", lat=60.0, lon=0.9)

    selected = nearest_graph_node(tg, latitude=60.0, longitude=0.0)
    assert selected == "node_lon"

    node_id, dist_km = nearest_graph_node(tg, latitude=60.0, longitude=0.0, return_distance=True)
    assert node_id == "node_lon"
    assert 49.0 < dist_km < 52.0  # Approx 50.1 km


def test_invalid_latitude():
    """4. Verify that latitude outside [-90, 90], NaN, inf, or non-numeric types are rejected."""
    graph = _create_simple_geo_graph()

    with pytest.raises(OSMInvalidDataError, match="Latitude out of bounds"):
        nearest_graph_node(graph, latitude=90.001, longitude=77.0)

    with pytest.raises(OSMInvalidDataError, match="Latitude out of bounds"):
        nearest_graph_node(graph, latitude=-90.001, longitude=77.0)

    with pytest.raises(OSMInvalidDataError, match="Latitude out of bounds"):
        nearest_graph_node(graph, latitude=float("nan"), longitude=77.0)

    with pytest.raises(OSMInvalidDataError, match="Coordinates must be numeric"):
        nearest_graph_node(graph, latitude="invalid_lat", longitude=77.0)


def test_invalid_longitude():
    """5. Verify that longitude outside [-180, 180], NaN, inf, or non-numeric types are rejected."""
    graph = _create_simple_geo_graph()

    with pytest.raises(OSMInvalidDataError, match="Longitude out of bounds"):
        nearest_graph_node(graph, latitude=12.0, longitude=180.001)

    with pytest.raises(OSMInvalidDataError, match="Longitude out of bounds"):
        nearest_graph_node(graph, latitude=12.0, longitude=-180.001)

    with pytest.raises(OSMInvalidDataError, match="Longitude out of bounds"):
        nearest_graph_node(graph, latitude=12.0, longitude=float("inf"))

    with pytest.raises(OSMInvalidDataError, match="Coordinates must be numeric"):
        nearest_graph_node(graph, latitude=12.0, longitude=None)


def test_graph_without_coordinates():
    """6. Verify that a graph without coordinate-bearing nodes raises a clear error."""
    tg = TransportGraph()
    # Adding nodes without lat/lon attributes (e.g. synthetic default nodes)
    tg.add_node("node_1")
    tg.add_node("node_2")

    with pytest.raises(OSMInvalidDataError, match="no valid coordinate-bearing nodes"):
        nearest_graph_node(tg, latitude=12.97, longitude=77.59)


def test_malformed_node_coordinates():
    """7. Verify that malformed coordinate-bearing nodes are safely handled."""
    tg = TransportGraph()
    # Malformed node A (string lat) and malformed node B (out of bounds lon)
    tg.add_node("node_A", lat="bad_lat", lon=77.59)
    tg.add_node("node_B", lat=12.97, lon=200.0)
    # Valid node C
    tg.add_node("node_C", lat=12.975, lon=77.595)

    # Should safely skip malformed nodes A and B, returning valid node C
    selected = nearest_graph_node(tg, latitude=12.97, longitude=77.59)
    assert selected == "node_C"

    # If only malformed nodes exist, should raise OSMInvalidDataError
    tg_bad = TransportGraph()
    tg_bad.add_node("bad_1", lat="nan", lon=77.0)
    with pytest.raises(OSMInvalidDataError, match="no valid coordinate-bearing nodes"):
        nearest_graph_node(tg_bad, latitude=12.97, longitude=77.59)


def test_empty_graph():
    """8. Verify that an empty graph raises OSMEmptyNetworkError."""
    tg = TransportGraph()
    with pytest.raises(OSMEmptyNetworkError, match="contains no nodes"):
        nearest_graph_node(tg, latitude=12.97, longitude=77.59)


def test_deterministic_tie_break():
    """9. Verify deterministic tie-breaking for equidistant candidate nodes."""
    tg = TransportGraph()
    # Equidistant from origin (0.0, 0.0)
    tg.add_node("candidate_Z", lat=0.0, lon=1.0)
    tg.add_node("candidate_A", lat=0.0, lon=-1.0)
    tg.add_node("candidate_M", lat=1.0, lon=0.0)

    # All three are approx 111.195 km from (0.0, 0.0)
    # 'candidate_A' is lexicographically smallest string ID
    for _ in range(10):
        selected = nearest_graph_node(tg, latitude=0.0, longitude=0.0)
        assert selected == "candidate_A"


def test_existing_osm_graph_compatibility():
    """10. Verify that M13.3 OSM-generated TransportGraph works seamlessly with nearest_graph_node."""
    osm_graph = osm_to_transport_graph(SAMPLE_OSM_XML)

    # MG Road intersection: (12.9715987, 77.5945627) -> node 101
    node_id = nearest_graph_node(osm_graph, latitude=12.9716, longitude=77.5945)
    assert node_id == "101"

    # Commercial Street: (12.9800000, 77.6050000) -> node 103
    node_id = nearest_graph_node(osm_graph, latitude=12.9801, longitude=77.6051)
    assert node_id == "103"


def test_customer_depot_adapters():
    """11. Verify helper adapters for customer and depot coordinate mapping."""
    graph = _create_simple_geo_graph()

    # Single coordinate mapping
    depot_node = map_coordinate_to_node(graph, latitude=12.970, longitude=77.590)
    assert depot_node == "node_A"

    # Batch coordinate mapping
    customer_coords = [
        (12.9751, 77.5951),  # Near node_B
        (12.9799, 77.6001),  # Near node_C
        (12.9701, 77.5901),  # Near node_A
    ]
    customer_nodes = map_coordinates_to_nodes(graph, customer_coords)
    assert customer_nodes == ["node_B", "node_C", "node_A"]


def test_return_distance_option():
    """12. Verify return_distance=True option behavior and accuracy."""
    graph = _create_simple_geo_graph()

    node_id, dist_km = nearest_graph_node(graph, latitude=12.970, longitude=77.590, return_distance=True)
    assert node_id == "node_A"
    assert pytest.approx(dist_km, abs=1e-5) == 0.0

    # Approx 1 km away
    node_id, dist_km = nearest_graph_node(graph, latitude=12.979, longitude=77.590, return_distance=True)
    assert isinstance(dist_km, float)
    assert dist_km > 0.0
