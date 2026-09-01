"""
app/graph/demo_data.py – Real-World OpenStreetMap Demo Dataset & Helpers for Milestone 13.10.

Provides:
- REAL_WORLD_OSM_XML: High-fidelity OpenStreetMap XML representing the Bangalore Central
  Commercial & Logistics District (MG Road, Brigade Road, Residency Road, Richmond Road,
  Lavelle Road, Kasturba Road, Trinity Circle) with realistic urban road network topology,
  speed limits, oneway constraints, and road segment geometry.
- REAL_WORLD_FLEET_VEHICLES: Geographic fleet vehicle specifications.
- REAL_WORLD_CUSTOMERS: Geographic delivery order locations and demand units.
- Helper functions to load the demo network, fleet, and construct geographic VRPProblem.
"""

from __future__ import annotations

from typing import Any, Dict, List
from app.graph.model import TransportGraph
from app.graph.osm import osm_to_transport_graph
from app.vrp.models import VRPProblem
from app.vrp.generator import build_geographic_vrp_problem


# ---------------------------------------------------------------------------
# Real-World OSM XML Dataset (Bangalore Central Logistics Corridor)
# ---------------------------------------------------------------------------
REAL_WORLD_OSM_XML: str = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="QRouteRealWorldDemo">
  <!-- Core Network Nodes -->
  <node id="1001" lat="12.9716" lon="77.5946">
    <tag k="name" v="MG Road Central Hub"/>
  </node>
  <node id="1002" lat="12.9752" lon="77.5985">
    <tag k="name" v="Brigade Road Junction"/>
  </node>
  <node id="1003" lat="12.9810" lon="77.6045">
    <tag k="name" v="Commercial Street North"/>
  </node>
  <node id="1004" lat="12.9785" lon="77.6120">
    <tag k="name" v="Trinity Circle East"/>
  </node>
  <node id="1005" lat="12.9690" lon="77.6090">
    <tag k="name" v="Richmond Road South"/>
  </node>
  <node id="1006" lat="12.9655" lon="77.6010">
    <tag k="name" v="Langford Town Express"/>
  </node>
  <node id="1007" lat="12.9680" lon="77.5925">
    <tag k="name" v="Lavelle Road West"/>
  </node>
  <node id="1008" lat="12.9760" lon="77.5900">
    <tag k="name" v="Cubbon Park Outer"/>
  </node>
  <node id="1009" lat="12.9735" lon="77.6030">
    <tag k="name" v="Residency Road Connector"/>
  </node>

  <!-- Arterial & Secondary Road Segments (Ways) -->
  <!-- Way 2001: MG Road Primary Corridor (1001 <-> 1002 <-> 1004) -->
  <way id="2001">
    <nd ref="1001"/>
    <nd ref="1002"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Mahatma Gandhi Road"/>
    <tag k="maxspeed" v="50 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2002">
    <nd ref="1002"/>
    <nd ref="1004"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="MG Road East Extension"/>
    <tag k="maxspeed" v="50 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Way 2003: Brigade & Commercial Shopping Corridor (1002 <-> 1003 <-> 1004) -->
  <way id="2003">
    <nd ref="1002"/>
    <nd ref="1003"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Brigade Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2004">
    <nd ref="1003"/>
    <nd ref="1004"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Dickenson Road"/>
    <tag k="maxspeed" v="35 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Way 2005: Trinity to Richmond Bypass (1004 <-> 1005 <-> 1006) -->
  <way id="2005">
    <nd ref="1004"/>
    <nd ref="1005"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Victoria Road"/>
    <tag k="maxspeed" v="45 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2006">
    <nd ref="1005"/>
    <nd ref="1006"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Richmond Road"/>
    <tag k="maxspeed" v="45 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Way 2007: Southern Loop to Lavelle & MG (1006 <-> 1007 <-> 1001) -->
  <way id="2007">
    <nd ref="1006"/>
    <nd ref="1007"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Vittal Mallya Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2008">
    <nd ref="1007"/>
    <nd ref="1001"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Lavelle Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Way 2009: Western Bypass (1001 <-> 1008 <-> 1002) -->
  <way id="2009">
    <nd ref="1001"/>
    <nd ref="1008"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Kasturba Road"/>
    <tag k="maxspeed" v="45 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2010">
    <nd ref="1008"/>
    <nd ref="1002"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Cubbon Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="no"/>
  </way>

  <!-- Way 2011: Central Cross-Corridor (1002 <-> 1009 <-> 1005) -->
  <way id="2011">
    <nd ref="1002"/>
    <nd ref="1009"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Residency Road"/>
    <tag k="maxspeed" v="40 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
  <way id="2012">
    <nd ref="1009"/>
    <nd ref="1005"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Commissariat Road"/>
    <tag k="maxspeed" v="35 km/h"/>
    <tag k="oneway" v="no"/>
  </way>
</osm>
"""


# ---------------------------------------------------------------------------
# Real-World Geographic Fleet & Customer Preset
# ---------------------------------------------------------------------------
REAL_WORLD_FLEET_VEHICLES: List[Dict[str, Any]] = [
    {
        "vehicle_id": "V1",
        "capacity": 50.0,
        "depot_latitude": 12.9716,
        "depot_longitude": 77.5946,
    },
    {
        "vehicle_id": "V2",
        "capacity": 45.0,
        "depot_latitude": 12.9716,
        "depot_longitude": 77.5946,
    },
]

REAL_WORLD_CUSTOMERS: List[Dict[str, Any]] = [
    {
        "customer_id": "C101",
        "latitude": 12.9752,
        "longitude": 77.5985,
        "demand": 12.0,
    },
    {
        "customer_id": "C102",
        "latitude": 12.9810,
        "longitude": 77.6045,
        "demand": 10.0,
    },
    {
        "customer_id": "C103",
        "latitude": 12.9785,
        "longitude": 77.6120,
        "demand": 14.0,
    },
    {
        "customer_id": "C104",
        "latitude": 12.9690,
        "longitude": 77.6090,
        "demand": 8.0,
    },
    {
        "customer_id": "C105",
        "latitude": 12.9655,
        "longitude": 77.6010,
        "demand": 11.0,
    },
    {
        "customer_id": "C106",
        "latitude": 12.9680,
        "longitude": 77.5925,
        "demand": 9.0,
    },
]


def load_real_world_osm_graph() -> TransportGraph:
    """Parse the real-world Bangalore OSM XML into a validated TransportGraph."""
    return osm_to_transport_graph(REAL_WORLD_OSM_XML)


def load_real_world_vrp_problem(graph: TransportGraph | None = None) -> VRPProblem:
    """Build a canonical geographic VRPProblem for the real-world demo dataset."""
    if graph is None:
        graph = load_real_world_osm_graph()
    return build_geographic_vrp_problem(
        graph=graph,
        vehicles=REAL_WORLD_FLEET_VEHICLES,
        customers=REAL_WORLD_CUSTOMERS,
    )
