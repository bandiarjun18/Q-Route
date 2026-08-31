"""
tests/test_m13_osm_ingestion.py – Test suite for OpenStreetMap (OSM) Road-Network Ingestion (M13.1).

Verifies:
1. Basic OSM XML & JSON parsing (nodes & roads imported).
2. Geographic coordinate preservation (x=longitude, y=latitude).
3. Directed road modeling (oneway forward, reverse, and bidirectional).
4. Geodesic distance calculation via Haversine formula (km).
5. Travel time derivation ((distance / speed) * 60 minutes).
6. Road filtering (exclusion of footways, cycleways, non-motorized infrastructure, access restrictions).
7. Metadata preservation (osm_id, osm_way_id, highway type, name, maxspeed, oneway).
8. TransportGraph & pathfinding compatibility (Dijkstra shortest path over OSM graph).
9. Robust error handling (malformed data, empty networks, invalid coordinates).
10. Determinism across repeated parses.
"""

import json
import math
import tempfile
from pathlib import Path
import pytest

from app.graph import (
    TransportGraph,
    WeightConfig,
    shortest_path,
    OSMConfig,
    OSMIngestionError,
    OSMParseError,
    OSMInvalidDataError,
    OSMEmptyNetworkError,
    haversine_distance,
    parse_maxspeed,
    calculate_travel_time_minutes,
    parse_osm_xml,
    parse_osm_json,
    osm_to_network_dict,
    load_osm_network,
)


# ---------------------------------------------------------------------------
# Synthetic OSM Fixtures (Offline / No External Network)
# ---------------------------------------------------------------------------

SAMPLE_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteTest">
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
    <tag k="name" v="Park Walkway Point"/>
  </node>

  <!-- Drivable bidirectional primary road (101 <-> 102) -->
  <way id="201">
    <nd ref="101"/>
    <nd ref="102"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="MG Road"/>
    <tag k="maxspeed" v="60 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Drivable one-way tertiary road (102 -> 103) -->
  <way id="202">
    <nd ref="102"/>
    <nd ref="103"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Residency Road"/>
    <tag k="maxspeed" v="40"/>
    <tag k="oneway" v="yes"/>
  </way>

  <!-- Excluded pedestrian footway (103 -> 104) -->
  <way id="203">
    <nd ref="103"/>
    <nd ref="104"/>
    <tag k="highway" v="footway"/>
    <tag k="name" v="Cubbon Walk"/>
  </way>

  <!-- Excluded private cycleway -->
  <way id="204">
    <nd ref="101"/>
    <nd ref="104"/>
    <tag k="highway" v="cycleway"/>
    <tag k="access" v="private"/>
  </way>
</osm>
"""

SAMPLE_OSM_JSON = {
    "elements": [
        {"type": "node", "id": 1, "lat": 48.8566, "lon": 2.3522, "tags": {"name": "Paris Center"}},
        {"type": "node", "id": 2, "lat": 48.8600, "lon": 2.3600, "tags": {"name": "Republique"}},
        {"type": "node", "id": 3, "lat": 48.8650, "lon": 2.3700, "tags": {"name": "Bastille"}},
        {"type": "node", "id": 4, "lat": 48.8700, "lon": 2.3800, "tags": {"name": "Pedestrian Path Node"}},
        {
            "type": "way",
            "id": 10,
            "nodes": [1, 2],
            "tags": {"highway": "secondary", "name": "Boulevard Voltaire", "maxspeed": "50", "oneway": "no"},
        },
        {
            "type": "way",
            "id": 20,
            "nodes": [2, 3],
            "tags": {"highway": "primary", "name": "Avenue de Paris", "maxspeed": "30 mph", "oneway": "yes"},
        },
        {
            "type": "way",
            "id": 30,
            "nodes": [3, 4],
            "tags": {"highway": "pedestrian", "name": "Rue Pietonne"},
        },
    ]
}


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_haversine_distance_accuracy():
    """Verify Haversine formula calculation against known geodesic distance."""
    # Paris (48.8566, 2.3522) to London (51.5074, -0.1278) ~ 343 km
    dist = haversine_distance(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340.0 < dist < 346.0

    # Distance to same point must be 0
    assert haversine_distance(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    # Out of bounds coordinates must raise OSMInvalidDataError
    with pytest.raises(OSMInvalidDataError):
        haversine_distance(95.0, 0.0, 0.0, 0.0)
    with pytest.raises(OSMInvalidDataError):
        haversine_distance(0.0, 185.0, 0.0, 0.0)


def test_parse_maxspeed():
    """Verify maxspeed tag parsing for km/h, mph, and fallbacks."""
    assert parse_maxspeed("50", default_speed=30.0) == 50.0
    assert parse_maxspeed("60 km/h", default_speed=30.0) == 60.0
    assert parse_maxspeed("80 kph", default_speed=30.0) == 80.0
    assert pytest.approx(parse_maxspeed("30 mph", default_speed=30.0), rel=1e-3) == 48.28032
    assert parse_maxspeed("walk", default_speed=30.0) == 5.0
    assert parse_maxspeed(None, default_speed=45.0) == 45.0
    assert parse_maxspeed("unknown_string", default_speed=35.0) == 35.0


def test_travel_time_calculation():
    """Verify travel time derived as (distance / speed) * 60 in minutes."""
    # 60 km at 60 km/h = 60 minutes
    assert calculate_travel_time_minutes(60.0, 60.0) == 60.0
    # 10 km at 100 km/h = 6 minutes
    assert calculate_travel_time_minutes(10.0, 100.0) == 6.0

    with pytest.raises(OSMInvalidDataError):
        calculate_travel_time_minutes(10.0, 0.0)
    with pytest.raises(OSMInvalidDataError):
        calculate_travel_time_minutes(-5.0, 50.0)


def test_basic_osm_xml_parsing():
    """Verify OSM XML parsing extracts valid nodes, edges, and metadata."""
    net_dict = parse_osm_xml(SAMPLE_OSM_XML)

    assert "nodes" in net_dict
    assert "edges" in net_dict
    assert "meta" in net_dict

    # Node 104 is only in footway/cycleway and should be excluded
    node_ids = {n["id"] for n in net_dict["nodes"]}
    assert "101" in node_ids
    assert "102" in node_ids
    assert "103" in node_ids
    assert "104" not in node_ids  # Non-motorized node excluded

    # Coordinate mapping: x = longitude, y = latitude
    node_101 = next(n for n in net_dict["nodes"] if n["id"] == "101")
    assert pytest.approx(node_101["x"], rel=1e-5) == 77.5945627
    assert pytest.approx(node_101["y"], rel=1e-5) == 12.9715987
    assert node_101["node_type"] == "intersection"


def test_osm_directionality_xml():
    """Verify bidirectional vs one-way edge generation from XML."""
    net_dict = parse_osm_xml(SAMPLE_OSM_XML)
    edges = net_dict["edges"]

    # Way 201 (101 <-> 102) is bidirectional: must have both (101->102) and (102->101)
    edge_101_102 = [e for e in edges if e["u"] == "101" and e["v"] == "102"]
    edge_102_101 = [e for e in edges if e["u"] == "102" and e["v"] == "101"]
    assert len(edge_101_102) == 1
    assert len(edge_102_101) == 1
    assert edge_101_102[0]["oneway"] is False

    # Way 202 (102 -> 103) is oneway: must have (102->103) but NOT (103->102)
    edge_102_103 = [e for e in edges if e["u"] == "102" and e["v"] == "103"]
    edge_103_102 = [e for e in edges if e["u"] == "103" and e["v"] == "102"]
    assert len(edge_102_103) == 1
    assert len(edge_103_102) == 0
    assert edge_102_103[0]["oneway"] is True


def test_road_filtering_and_metadata():
    """Verify non-drivable roads are excluded and valid road metadata is preserved."""
    net_dict = parse_osm_xml(SAMPLE_OSM_XML)
    edges = net_dict["edges"]

    # Check that footway (way 203) and cycleway (way 204) are excluded
    way_ids = {e.get("osm_way_id") for e in edges}
    assert "201" in way_ids
    assert "202" in way_ids
    assert "203" not in way_ids
    assert "204" not in way_ids

    # Check edge attributes
    e1 = next(e for e in edges if e["osm_way_id"] == "201")
    assert e1["distance"] > 0.0
    assert e1["base_travel_time"] > 0.0
    assert e1["congestion_factor"] == 1.0
    assert e1["road_status"] == "open"
    assert e1["highway"] == "primary"
    assert e1["name"] == "MG Road"
    assert e1["speed_kmh"] == 60.0


def test_osm_json_parsing():
    """Verify Overpass/OSM JSON parsing works identically."""
    net_dict = parse_osm_json(SAMPLE_OSM_JSON)
    assert len(net_dict["nodes"]) == 3  # nodes 1, 2, 3 (4 is pedestrian only)
    assert len(net_dict["edges"]) == 3  # (1->2), (2->1), (2->3)

    node_1 = next(n for n in net_dict["nodes"] if n["id"] == "1")
    assert pytest.approx(node_1["x"], rel=1e-5) == 2.3522  # longitude
    assert pytest.approx(node_1["y"], rel=1e-5) == 48.8566  # latitude

    # Check 30 mph conversion to km/h (~48.28 km/h)
    e_2_3 = next(e for e in net_dict["edges"] if e["u"] == "2" and e["v"] == "3")
    assert pytest.approx(e_2_3["speed_kmh"], rel=1e-2) == 48.28


def test_transport_graph_compatibility_and_pathfinding():
    """Verify that loaded OSM network functions seamlessly with TransportGraph and shortest_path."""
    graph = load_osm_network(SAMPLE_OSM_XML)

    assert isinstance(graph, TransportGraph)
    assert graph.node_count() == 3
    assert graph.edge_count() == 3

    # Check Dijkstra pathfinding from 101 to 103 (101 -> 102 -> 103)
    wc = WeightConfig(w_time=1.0, w_distance=0.5, w_congestion=0.3)
    path, cost = shortest_path(graph, "101", "103", wc)
    assert path == ["101", "102", "103"]
    assert cost > 0.0
    assert not math.isinf(cost)

    # One-way restriction: Path from 103 to 101 cannot traverse 103 -> 102
    import networkx as nx
    with pytest.raises(nx.NetworkXNoPath):
        shortest_path(graph, "103", "101", wc)


def test_file_based_ingestion():
    """Verify loading OSM data directly from temporary XML and JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "test_city.osm"
        xml_file.write_text(SAMPLE_OSM_XML, encoding="utf-8")

        graph_xml = load_osm_network(xml_file)
        assert graph_xml.node_count() == 3

        json_file = Path(tmpdir) / "test_city.json"
        json_file.write_text(json.dumps(SAMPLE_OSM_JSON), encoding="utf-8")

        graph_json = load_osm_network(json_file)
        assert graph_json.node_count() == 3


def test_custom_osm_config():
    """Verify that custom OSMConfig settings override defaults properly."""
    custom_cfg = OSMConfig(
        fallback_speed_kmh=25.0,
        default_speeds_kmh={"primary": 80.0, "tertiary": 30.0},
        default_node_type="intersection",
    )
    net_dict = osm_to_network_dict(SAMPLE_OSM_XML, config=custom_cfg)
    edge_101_102 = next(e for e in net_dict["edges"] if e["u"] == "101" and e["v"] == "102")
    # Tag has maxspeed 60 km/h, which takes precedence
    assert edge_101_102["speed_kmh"] == 60.0


def test_error_handling_malformed_xml():
    """Verify OSMParseError on invalid XML."""
    with pytest.raises(OSMParseError):
        parse_osm_xml("<osm><unclosed_tag></osm>")


def test_error_handling_malformed_json():
    """Verify OSMParseError on invalid JSON."""
    with pytest.raises(OSMParseError):
        parse_osm_json("{not_valid_json}")
    with pytest.raises(OSMParseError):
        parse_osm_json({"wrong_key": []})


def test_error_handling_empty_network():
    """Verify OSMEmptyNetworkError when no drivable roads exist."""
    empty_osm = """<?xml version="1.0" encoding="UTF-8"?>
    <osm version="0.6">
      <node id="1" lat="10.0" lon="10.0"/>
      <node id="2" lat="10.1" lon="10.1"/>
      <way id="100">
        <nd ref="1"/>
        <nd ref="2"/>
        <tag k="highway" v="footway"/>
      </way>
    </osm>
    """
    with pytest.raises(OSMEmptyNetworkError):
        parse_osm_xml(empty_osm)


def test_determinism():
    """Verify identical repeated parsing produces byte-identical dictionary structures."""
    dict1 = osm_to_network_dict(SAMPLE_OSM_XML)
    dict2 = osm_to_network_dict(SAMPLE_OSM_XML)
    assert dict1 == dict2

    dict_json1 = osm_to_network_dict(SAMPLE_OSM_JSON)
    dict_json2 = osm_to_network_dict(SAMPLE_OSM_JSON)
    assert dict_json1 == dict_json2
