"""
tests/test_m13_7_road_geometry.py – Tests for Milestone 13.7: OSM Road Geometry Preservation.

Verifies:
1. XML OSM input produces geometry on forward edge: [[lat_u, lon_u], [lat_v, lon_v]].
2. Reverse edge geometry is reversed for bidirectional roads: [[lat_v, lon_v], [lat_u, lon_u]].
3. One-way road only creates the allowed direction with correct geometry.
4. Geometry contains [latitude, longitude], not [longitude, latitude].
5. Missing referenced OSM nodes do not crash ingestion (skipped gracefully).
6. Existing distance calculation remains unchanged.
7. Existing edge metadata (distance, base_travel_time, speed_kmh, etc.) remains unchanged.
8. TransportGraph serialization (to_dict / from_dict) preserves geometry.
9. Synthetic graph generation remains unaffected.
"""

import json
import math
import pytest

from app.graph import (
    TransportGraph,
    OSMConfig,
    haversine_distance,
    parse_osm_xml,
    parse_osm_json,
    osm_to_transport_graph,
    generate_synthetic_network,
)


SAMPLE_XML_GEOMETRY = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteGeometryTest">
  <node id="1001" lat="12.9715987" lon="77.5945627"/>
  <node id="1002" lat="12.9750000" lon="77.5980000"/>
  <node id="1003" lat="12.9800000" lon="77.6050000"/>
  <node id="1004" lat="12.9850000" lon="77.6100000"/>

  <!-- Bidirectional road: 1001 <-> 1002 -->
  <way id="5001">
    <nd ref="1001"/>
    <nd ref="1002"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="MG Road"/>
    <tag k="maxspeed" v="50 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- One-way forward road: 1002 -> 1003 -->
  <way id="5002">
    <nd ref="1002"/>
    <nd ref="1003"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Brigade Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="yes"/>
  </way>

  <!-- Way with a missing referenced node (9999 is not declared) -->
  <way id="5003">
    <nd ref="1003"/>
    <nd ref="9999"/>
    <nd ref="1004"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Missing Node Link"/>
  </way>
</osm>
"""

SAMPLE_JSON_GEOMETRY = {
    "elements": [
        {"type": "node", "id": 2001, "lat": 37.7749, "lon": -122.4194},
        {"type": "node", "id": 2002, "lat": 37.7755, "lon": -122.4180},
        {"type": "node", "id": 2003, "lat": 37.7760, "lon": -122.4170},
        {
            "type": "way",
            "id": 6001,
            "nodes": [2001, 2002],
            "tags": {
                "highway": "residential",
                "name": "Market St",
                "oneway": "no",
            },
        },
        {
            "type": "way",
            "id": 6002,
            "nodes": [2002, 2003],
            "tags": {
                "highway": "primary",
                "name": "Mission St",
                "oneway": "-1",  # reverse one-way: 2003 -> 2002
            },
        },
    ]
}


class TestOSMRoadGeometryPreservation:
    """Test suite for Milestone 13.7 OSM road geometry preservation."""

    def test_xml_osm_produces_forward_and_reverse_geometry(self):
        """XML OSM input produces geometry on forward and reverse edges of bidirectional roads."""
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)

        # Find 1001 -> 1002 and 1002 -> 1001
        edge_fwd = next(e for e in net["edges"] if e["u"] == "1001" and e["v"] == "1002")
        edge_rev = next(e for e in net["edges"] if e["u"] == "1002" and e["v"] == "1001")

        assert "geometry" in edge_fwd
        assert "geometry" in edge_rev

        # Forward edge: [[lat_u, lon_u], [lat_v, lon_v]]
        assert edge_fwd["geometry"] == [
            [12.9715987, 77.5945627],
            [12.9750000, 77.5980000],
        ]

        # Reverse edge: [[lat_v, lon_v], [lat_u, lon_u]]
        assert edge_rev["geometry"] == [
            [12.9750000, 77.5980000],
            [12.9715987, 77.5945627],
        ]

    def test_oneway_road_geometry(self):
        """One-way road creates only the allowed direction with correct geometry."""
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)

        # Way 5002 is oneway=yes from 1002 to 1003
        fwd_matches = [e for e in net["edges"] if e["u"] == "1002" and e["v"] == "1003"]
        rev_matches = [e for e in net["edges"] if e["u"] == "1003" and e["v"] == "1002"]

        assert len(fwd_matches) == 1
        assert len(rev_matches) == 0

        edge_oneway = fwd_matches[0]
        assert edge_oneway["geometry"] == [
            [12.9750000, 77.5980000],
            [12.9800000, 77.6050000],
        ]
        assert edge_oneway["oneway"] is True

    def test_reverse_oneway_road_geometry_json(self):
        """JSON OSM with oneway=-1 creates only reverse direction with correct geometry."""
        net = parse_osm_json(SAMPLE_JSON_GEOMETRY)

        # Way 6002 is oneway=-1 from 2002 to 2003 (so directed edge is 2003 -> 2002)
        fwd_matches = [e for e in net["edges"] if e["u"] == "2002" and e["v"] == "2003"]
        rev_matches = [e for e in net["edges"] if e["u"] == "2003" and e["v"] == "2002"]

        assert len(fwd_matches) == 0
        assert len(rev_matches) == 1

        edge_rev_oneway = rev_matches[0]
        # Since directed edge is 2003 -> 2002, geometry should start at 2003 and end at 2002
        assert edge_rev_oneway["geometry"] == [
            [37.7760, -122.4170],
            [37.7755, -122.4180],
        ]

    def test_geometry_is_lat_lon_convention(self):
        """Geometry coordinate order is [latitude, longitude], not [longitude, latitude]."""
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)
        edge = next(e for e in net["edges"] if e["u"] == "1001" and e["v"] == "1002")

        u_pt, v_pt = edge["geometry"]

        # Bangalore latitude ~ 12.97, longitude ~ 77.59
        # Check that index 0 is latitude (~12.97) and index 1 is longitude (~77.59)
        assert abs(u_pt[0] - 12.9715987) < 1e-6
        assert abs(u_pt[1] - 77.5945627) < 1e-6
        assert abs(v_pt[0] - 12.9750000) < 1e-6
        assert abs(v_pt[1] - 77.5980000) < 1e-6

    def test_missing_referenced_osm_nodes_do_not_crash(self):
        """Ways referencing non-existent nodes skip invalid segments gracefully."""
        # Way 5003 references 1003 -> 9999 -> 1004, where 9999 is missing
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)

        # Neither segment 1003-9999 nor 9999-1004 should exist in edges
        for e in net["edges"]:
            assert e["u"] != "9999"
            assert e["v"] != "9999"

    def test_distance_and_travel_time_calculation_unchanged(self):
        """Distance and travel time formulas remain exact and unaffected."""
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)
        edge = next(e for e in net["edges"] if e["u"] == "1001" and e["v"] == "1002")

        expected_dist = round(haversine_distance(12.9715987, 77.5945627, 12.9750000, 77.5980000), 6)
        assert edge["distance"] == expected_dist

        speed_kmh = edge["speed_kmh"]
        expected_tt = round((expected_dist / speed_kmh) * 60.0, 6)
        assert edge["base_travel_time"] == expected_tt

    def test_existing_edge_metadata_unchanged(self):
        """Existing metadata keys (distance, base_travel_time, congestion_factor, road_status, osm_way_id, highway, speed_kmh, oneway, name) are preserved."""
        net = parse_osm_xml(SAMPLE_XML_GEOMETRY)
        edge = next(e for e in net["edges"] if e["u"] == "1001" and e["v"] == "1002")

        assert edge["osm_way_id"] == "5001"
        assert edge["highway"] == "primary"
        assert edge["speed_kmh"] == 50.0
        assert edge["congestion_factor"] == 1.0
        assert edge["road_status"] == "open"
        assert edge["oneway"] is False
        assert edge["name"] == "MG Road"

    def test_transport_graph_serialization_preserves_geometry(self):
        """TransportGraph.from_dict() and to_dict() roundtrip preserves geometry."""
        tg = osm_to_transport_graph(SAMPLE_XML_GEOMETRY)

        # Direct edge query on TransportGraph NetworkX DiGraph
        edge_data = tg.graph["1001"]["1002"]
        assert "geometry" in edge_data
        assert edge_data["geometry"] == [
            [12.9715987, 77.5945627],
            [12.9750000, 77.5980000],
        ]

        # Roundtrip to_dict and from_dict
        serialized = tg.to_dict()
        edge_dict = next(e for e in serialized["edges"] if e["u"] == "1001" and e["v"] == "1002")
        assert edge_dict["geometry"] == [
            [12.9715987, 77.5945627],
            [12.9750000, 77.5980000],
        ]

        restored_tg = TransportGraph.from_dict(serialized)
        restored_edge_data = restored_tg.graph["1001"]["1002"]
        assert restored_edge_data["geometry"] == [
            [12.9715987, 77.5945627],
            [12.9750000, 77.5980000],
        ]

    def test_synthetic_graph_generation_unaffected(self):
        """Synthetic graph generation produces graphs without geometry unless explicitly set."""
        synthetic_dict = generate_synthetic_network(n_nodes=10, grid_size_km=10.0, seed=42)
        tg = TransportGraph.from_dict(synthetic_dict)

        assert tg.node_count() == 10
        assert tg.edge_count() > 0

        # Synthetic edges do not have geometry by default
        for u, v, data in tg.graph.edges(data=True):
            assert "distance" in data
            assert "base_travel_time" in data
            # geometry is not present on purely synthetic edges
            assert "geometry" not in data

        # Roundtrip synthetic graph
        roundtrip_dict = tg.to_dict()
        assert len(roundtrip_dict["nodes"]) == 10
        for edge in roundtrip_dict["edges"]:
            assert "geometry" not in edge
