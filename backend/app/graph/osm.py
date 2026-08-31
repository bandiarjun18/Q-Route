"""
app/graph/osm.py – OpenStreetMap (OSM) Road-Network Ingestion for Q-Route (Milestone 13.1).

This module provides a robust, isolated, and deterministic parser for converting
OpenStreetMap geographic road network data into Q-Route's canonical `TransportGraph`
representation.

Design & Units Specification
----------------------------
1. Coordinate System:
   - x = longitude (in decimal degrees, East positive)
   - y = latitude  (in decimal degrees, North positive)
   - Stored in nodes as: ``x=lon, y=lat``, alongside explicit ``lat`` and ``lon`` attributes.

2. Distance Units:
   - Distances are computed using the great-circle Haversine formula (WGS-84 sphere).
   - Unit: Kilometers (km).

3. Speed Units:
   - Speeds are extracted from OSM ``maxspeed`` tags (with mph conversion if specified)
     or inferred deterministically from highway classifications.
   - Unit: Kilometers per hour (km/h).

4. Travel-Time Units:
   - Base travel times are derived as: ``(distance_km / speed_kmh) * 60.0``.
   - Unit: Minutes.
   - Consistent with Q-Route's project-wide ``WeightConfig`` and objective formulas.

5. Road Types & Directionality:
   - Drivable motor-vehicle highway types are imported (motorway, trunk, primary, secondary,
     tertiary, unclassified, residential, living_street, service, and link roads).
   - Purely non-motorized ways (footway, cycleway, pedestrian, steps, path, etc.) are excluded.
   - Directed edges match OSM ``oneway`` semantics (forward, reverse, or bidirectional).

6. TransportGraph Compatibility:
   - Produces a standard network dictionary: ``{"meta": ..., "nodes": [...], "edges": [...]}``
   - Directly loadable via ``TransportGraph.from_dict()`` or ``load_osm_network()``.
   - Newly ingested edges receive ``congestion_factor = 1.0`` and ``road_status = "open"``.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET

from .model import TransportGraph


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OSMIngestionError(Exception):
    """Base exception for all OSM road network ingestion errors."""
    pass


class OSMParseError(OSMIngestionError):
    """Raised when OSM data cannot be parsed as valid XML or JSON."""
    pass


class OSMInvalidDataError(OSMIngestionError):
    """Raised when OSM data contains invalid coordinates, missing nodes, or illegal values."""
    pass


class OSMEmptyNetworkError(OSMIngestionError):
    """Raised when no valid drivable road network is found in the OSM input."""
    pass


# ---------------------------------------------------------------------------
# Constants & Defaults
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM: float = 6371.0088

DEFAULT_SUPPORTED_HIGHWAYS: frozenset[str] = frozenset({
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
})

DEFAULT_EXCLUDED_HIGHWAYS: frozenset[str] = frozenset({
    "footway",
    "pedestrian",
    "steps",
    "cycleway",
    "path",
    "bridleway",
    "track",
    "corridor",
    "elevator",
    "proposed",
    "construction",
    "abandoned",
    "raceway",
    "escape",
    "bus_stop",
    "platform",
})

DEFAULT_SPEEDS_KMH: dict[str, float] = {
    "motorway": 100.0,
    "trunk": 80.0,
    "primary": 60.0,
    "secondary": 50.0,
    "tertiary": 40.0,
    "unclassified": 30.0,
    "residential": 30.0,
    "living_street": 15.0,
    "service": 20.0,
    "motorway_link": 50.0,
    "trunk_link": 40.0,
    "primary_link": 40.0,
    "secondary_link": 30.0,
    "tertiary_link": 25.0,
}

DEFAULT_FALLBACK_SPEED_KMH: float = 30.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OSMConfig:
    """
    Configuration options for OSM road-network ingestion.

    Parameters
    ----------
    supported_highways       : Set of highway tag values to include.
    excluded_highways        : Set of highway tag values to explicitly exclude.
    default_speeds_kmh       : Mapping from highway tag value to default speed in km/h.
    fallback_speed_kmh       : Deterministic fallback speed (km/h) for unspecified roads.
    roundabout_is_oneway     : Treat ``junction=roundabout`` as one-way unless specified.
    motorway_is_oneway       : Treat ``highway=motorway`` as one-way unless specified.
    default_node_type        : Default node type assigned to imported intersections.
    default_congestion_factor: Free-flow congestion multiplier (default 1.0).
    default_road_status      : Initial road status ("open").
    """

    supported_highways: frozenset[str] = DEFAULT_SUPPORTED_HIGHWAYS
    excluded_highways: frozenset[str] = DEFAULT_EXCLUDED_HIGHWAYS
    default_speeds_kmh: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SPEEDS_KMH))
    fallback_speed_kmh: float = DEFAULT_FALLBACK_SPEED_KMH
    roundabout_is_oneway: bool = True
    motorway_is_oneway: bool = True
    default_node_type: str = "intersection"
    default_congestion_factor: float = 1.0
    default_road_status: str = "open"


# ---------------------------------------------------------------------------
# Geodesic & Speed Utilities
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance between two geographic points in kilometers.

    Uses the standard Haversine formula on a spherical earth model (R = 6371.0088 km).

    Parameters
    ----------
    lat1, lon1 : Latitude and longitude of point 1 in decimal degrees.
    lat2, lon2 : Latitude and longitude of point 2 in decimal degrees.

    Returns
    -------
    float : Distance in kilometers (km). Always >= 0.0.
    """
    if not (-90.0 <= lat1 <= 90.0 and -90.0 <= lat2 <= 90.0):
        raise OSMInvalidDataError(f"Latitude out of bounds [-90, 90]: lat1={lat1}, lat2={lat2}")
    if not (-180.0 <= lon1 <= 180.0 and -180.0 <= lon2 <= 180.0):
        raise OSMInvalidDataError(f"Longitude out of bounds [-180, 180]: lon1={lon1}, lon2={lon2}")

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def parse_maxspeed(maxspeed_val: Optional[Any], default_speed: float = DEFAULT_FALLBACK_SPEED_KMH) -> float:
    """
    Parse an OSM ``maxspeed`` tag value into speed in km/h.

    Handles numeric values, 'km/h', 'kph', 'mph' (converted to km/h), and falls back
    deterministically to ``default_speed`` for unknown or non-numeric strings.

    Parameters
    ----------
    maxspeed_val  : Raw value from OSM maxspeed tag.
    default_speed : Fallback speed in km/h if tag is missing, empty, or unparseable.

    Returns
    -------
    float : Speed in km/h (> 0.0).
    """
    if maxspeed_val is None:
        return default_speed

    val_str = str(maxspeed_val).strip().lower()
    if not val_str:
        return default_speed

    # Check for mph
    mph_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:mph|miles/h)?$", val_str)
    if "mph" in val_str and mph_match:
        try:
            val_num = float(mph_match.group(1))
            if val_num > 0.0:
                return val_num * 1.609344
        except ValueError:
            pass

    # Check for numeric or km/h
    kmh_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:km/h|kmh|kph)?$", val_str)
    if kmh_match:
        try:
            val_num = float(kmh_match.group(1))
            if val_num > 0.0:
                return val_num
        except ValueError:
            pass

    # Special OSM tags
    if val_str in ("walk", "walking"):
        return 5.0

    return default_speed


def calculate_travel_time_minutes(distance_km: float, speed_kmh: float) -> float:
    """
    Derive base travel time in minutes from distance (km) and speed (km/h).

    Formula: ``(distance_km / speed_kmh) * 60.0``

    Parameters
    ----------
    distance_km : Road segment length in kilometers.
    speed_kmh   : Free-flow speed in kilometers per hour.

    Returns
    -------
    float : Travel time in minutes.
    """
    if speed_kmh <= 0.0:
        raise OSMInvalidDataError(f"Speed must be positive, got {speed_kmh} km/h")
    if distance_km < 0.0:
        raise OSMInvalidDataError(f"Distance cannot be negative, got {distance_km} km")

    return (distance_km / speed_kmh) * 60.0


# ---------------------------------------------------------------------------
# Road & Way Classification
# ---------------------------------------------------------------------------

def is_drivable_highway(tags: dict[str, str], config: OSMConfig) -> bool:
    """
    Determine whether an OSM way is a drivable road for motor vehicles.

    Excludes non-motorized ways (pedestrian, footway, cycleway, etc.) and
    checks access restriction tags.
    """
    highway = tags.get("highway")
    if not highway or highway not in config.supported_highways:
        return False

    if highway in config.excluded_highways:
        return False

    # Check access tags
    motor_vehicle = tags.get("motor_vehicle", "").lower()
    if motor_vehicle in ("no", "private", "agricultural", "forestry"):
        return False

    motorcar = tags.get("motorcar", "").lower()
    if motorcar in ("no", "private"):
        return False

    access = tags.get("access", "").lower()
    if access in ("no", "private") and not tags.get("motor_vehicle") and not tags.get("motorcar"):
        return False

    return True


def determine_oneway_direction(tags: dict[str, str], config: OSMConfig) -> str:
    """
    Determine the directional traversal rule for an OSM way.

    Returns
    -------
    str : "forward" (u -> v only), "reverse" (v -> u only), or "bidirectional" (both).
    """
    oneway_tag = tags.get("oneway", "").strip().lower()

    if oneway_tag in ("yes", "1", "true"):
        return "forward"
    if oneway_tag in ("-1", "reverse"):
        return "reverse"
    if oneway_tag in ("no", "0", "false"):
        return "bidirectional"

    # Infer from junction / highway type
    if tags.get("junction") == "roundabout" and config.roundabout_is_oneway:
        return "forward"

    highway = tags.get("highway", "")
    if highway == "motorway" and config.motorway_is_oneway:
        return "forward"

    return "bidirectional"


# ---------------------------------------------------------------------------
# Internal Parsers (XML & JSON)
# ---------------------------------------------------------------------------

@dataclass
class _RawNode:
    id: Any
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class _RawWay:
    id: Any
    node_refs: list[Any] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


def _parse_xml_elements(source: Union[str, bytes, Path]) -> Tuple[Dict[Any, _RawNode], List[_RawWay]]:
    """Parse raw XML into internal node and way collections."""
    try:
        if isinstance(source, (str, Path)) and os.path.exists(str(source)):
            tree = ET.parse(str(source))
            root = tree.getroot()
        elif isinstance(source, bytes):
            root = ET.fromstring(source)
        elif isinstance(source, str):
            # Check if it looks like an XML string
            source_stripped = source.strip()
            if source_stripped.startswith("<"):
                root = ET.fromstring(source)
            else:
                raise OSMParseError(f"Provided path or string is not valid OSM XML: {source[:100]}")
        else:
            raise OSMParseError(f"Unsupported XML source type: {type(source)}")
    except ET.ParseError as e:
        raise OSMParseError(f"Failed to parse OSM XML: {e}") from e

    nodes: dict[Any, _RawNode] = {}
    ways: list[_RawWay] = []

    for elem in root:
        if elem.tag == "node":
            node_id = elem.get("id")
            lat_str = elem.get("lat")
            lon_str = elem.get("lon")
            if node_id is None or lat_str is None or lon_str is None:
                continue
            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                continue
            tags = {tag.get("k"): tag.get("v", "") for tag in elem.findall("tag") if tag.get("k")}
            nodes[node_id] = _RawNode(id=node_id, lat=lat, lon=lon, tags=tags)

        elif elem.tag == "way":
            way_id = elem.get("id")
            if way_id is None:
                continue
            node_refs = [nd.get("ref") for nd in elem.findall("nd") if nd.get("ref")]
            tags = {tag.get("k"): tag.get("v", "") for tag in elem.findall("tag") if tag.get("k")}
            ways.append(_RawWay(id=way_id, node_refs=node_refs, tags=tags))

    return nodes, ways


def _parse_json_elements(source: Union[str, dict, Path]) -> Tuple[Dict[Any, _RawNode], List[_RawWay]]:
    """Parse Overpass/OSM JSON into internal node and way collections."""
    data: dict[str, Any]
    if isinstance(source, dict):
        data = source
    elif isinstance(source, (str, Path)):
        source_str = str(source)
        if os.path.exists(source_str):
            try:
                with open(source_str, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                raise OSMParseError(f"Failed to read OSM JSON file: {e}") from e
        else:
            try:
                data = json.loads(source_str)
            except Exception as e:
                raise OSMParseError(f"Failed to parse OSM JSON string: {e}") from e
    else:
        raise OSMParseError(f"Unsupported JSON source type: {type(source)}")

    elements = data.get("elements")
    if elements is None or not isinstance(elements, list):
        raise OSMParseError("OSM JSON must contain a top-level 'elements' list.")

    nodes: dict[Any, _RawNode] = {}
    ways: list[_RawWay] = []

    for elem in elements:
        elem_type = elem.get("type")
        if elem_type == "node":
            node_id = str(elem.get("id"))
            lat = elem.get("lat")
            lon = elem.get("lon")
            if node_id is None or lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue
            tags = {str(k): str(v) for k, v in elem.get("tags", {}).items()}
            nodes[node_id] = _RawNode(id=node_id, lat=lat_f, lon=lon_f, tags=tags)

        elif elem_type == "way":
            way_id = str(elem.get("id"))
            if way_id is None:
                continue
            node_refs = [str(ref) for ref in elem.get("nodes", [])]
            tags = {str(k): str(v) for k, v in elem.get("tags", {}).items()}
            ways.append(_RawWay(id=way_id, node_refs=node_refs, tags=tags))

    return nodes, ways


# ---------------------------------------------------------------------------
# Graph Builder from Raw Elements
# ---------------------------------------------------------------------------

def _build_network_dict_from_elements(
    nodes_map: Dict[Any, _RawNode],
    ways_list: List[_RawWay],
    config: OSMConfig,
) -> dict:
    """Construct a Q-Route network dictionary from extracted OSM nodes and ways."""
    used_node_ids: set[Any] = set()
    edges: list[dict[str, Any]] = []

    for way in ways_list:
        if not is_drivable_highway(way.tags, config):
            continue

        if len(way.node_refs) < 2:
            continue

        highway_type = way.tags.get("highway", "unclassified")
        default_speed = config.default_speeds_kmh.get(highway_type, config.fallback_speed_kmh)
        speed_kmh = parse_maxspeed(way.tags.get("maxspeed"), default_speed=default_speed)
        direction = determine_oneway_direction(way.tags, config)
        way_name = way.tags.get("name")

        # Iterate over consecutive node pairs along the way
        for i in range(len(way.node_refs) - 1):
            u_id = way.node_refs[i]
            v_id = way.node_refs[i + 1]

            if u_id not in nodes_map or v_id not in nodes_map:
                # Missing referenced node coordinate; skip segment
                continue

            u_node = nodes_map[u_id]
            v_node = nodes_map[v_id]

            dist_km = haversine_distance(u_node.lat, u_node.lon, v_node.lat, v_node.lon)
            if dist_km <= 0.0:
                # Coincident nodes (zero distance) – skip or treat as minimal non-zero epsilon
                dist_km = 0.001

            travel_time_min = calculate_travel_time_minutes(dist_km, speed_kmh)

            edge_base_attrs: dict[str, Any] = {
                "distance": round(dist_km, 6),
                "base_travel_time": round(travel_time_min, 6),
                "congestion_factor": config.default_congestion_factor,
                "road_status": config.default_road_status,
                "osm_way_id": way.id,
                "highway": highway_type,
                "speed_kmh": speed_kmh,
                "oneway": direction != "bidirectional",
            }
            if way_name:
                edge_base_attrs["name"] = way_name

            if direction in ("forward", "bidirectional"):
                edges.append({"u": u_id, "v": v_id, **edge_base_attrs})
                used_node_ids.add(u_id)
                used_node_ids.add(v_id)

            if direction in ("reverse", "bidirectional"):
                edges.append({"u": v_id, "v": u_id, **edge_base_attrs})
                used_node_ids.add(u_id)
                used_node_ids.add(v_id)

    if not used_node_ids or not edges:
        raise OSMEmptyNetworkError(
            "No valid drivable road network could be constructed from the provided OSM data. "
            "Ensure that input contains connected nodes with coordinates and supported highway ways."
        )

    # Build deterministic node list sorted by node ID
    nodes: list[dict[str, Any]] = []
    for nid in sorted(used_node_ids, key=lambda x: str(x)):
        n = nodes_map[nid]
        nodes.append({
            "id": nid,
            "node_type": config.default_node_type,
            "x": n.lon,  # x = longitude
            "y": n.lat,  # y = latitude
            "lat": n.lat,
            "lon": n.lon,
            "osm_id": n.id,
        })

    return {
        "meta": {
            "source": "OpenStreetMap",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "distance_unit": "km",
            "speed_unit": "km/h",
            "travel_time_unit": "minutes",
            "coordinate_convention": "x=longitude, y=latitude",
        },
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_osm_xml(
    source: Union[str, bytes, Path],
    config: Optional[OSMConfig] = None,
) -> dict:
    """
    Parse OSM XML data (file path, bytes, or XML string) into a Q-Route network dictionary.

    Parameters
    ----------
    source : File path, XML string, or raw bytes containing OSM XML.
    config : Ingestion configuration options (optional, uses default OSMConfig if None).

    Returns
    -------
    dict : Q-Route network dictionary with keys 'meta', 'nodes', 'edges'.
    """
    cfg = config or OSMConfig()
    nodes_map, ways_list = _parse_xml_elements(source)
    return _build_network_dict_from_elements(nodes_map, ways_list, cfg)


def parse_osm_json(
    source: Union[str, dict, Path],
    config: Optional[OSMConfig] = None,
) -> dict:
    """
    Parse OSM/Overpass JSON data (file path, JSON string, or dict) into a Q-Route network dictionary.

    Parameters
    ----------
    source : File path, JSON string, or dict containing OSM/Overpass JSON.
    config : Ingestion configuration options (optional, uses default OSMConfig if None).

    Returns
    -------
    dict : Q-Route network dictionary with keys 'meta', 'nodes', 'edges'.
    """
    cfg = config or OSMConfig()
    nodes_map, ways_list = _parse_json_elements(source)
    return _build_network_dict_from_elements(nodes_map, ways_list, cfg)


def osm_to_network_dict(
    osm_data: Union[str, bytes, dict, Path],
    config: Optional[OSMConfig] = None,
) -> dict:
    """
    Unified entry point to parse OSM data (XML or JSON) into a Q-Route network dictionary.

    Automatically detects whether the input is JSON or XML based on format/type.

    Parameters
    ----------
    osm_data : OSM data as a dictionary, XML/JSON string, bytes, or file path.
    config   : Ingestion configuration options.

    Returns
    -------
    dict : Q-Route network dictionary compatible with ``TransportGraph.from_dict()``.
    """
    cfg = config or OSMConfig()

    if isinstance(osm_data, dict):
        return parse_osm_json(osm_data, cfg)

    if isinstance(osm_data, (str, Path)):
        str_val = str(osm_data).strip()
        if os.path.exists(str_val):
            # Check file extension or contents
            ext = Path(str_val).suffix.lower()
            if ext in (".json", ".geojson"):
                return parse_osm_json(osm_data, cfg)
            return parse_osm_xml(osm_data, cfg)

        if str_val.startswith("{"):
            return parse_osm_json(str_val, cfg)
        return parse_osm_xml(str_val, cfg)

    if isinstance(osm_data, bytes):
        stripped = osm_data.strip()
        if stripped.startswith(b"{"):
            return parse_osm_json(stripped.decode("utf-8"), cfg)
        return parse_osm_xml(osm_data, cfg)

    raise OSMParseError(f"Unsupported OSM data input type: {type(osm_data)}")


def load_osm_network(
    osm_data: Union[str, bytes, dict, Path],
    config: Optional[OSMConfig] = None,
) -> TransportGraph:
    """
    Parse OSM data and return a fully initialized Q-Route ``TransportGraph`` instance.

    Parameters
    ----------
    osm_data : OSM data as a dictionary, XML/JSON string, bytes, or file path.
    config   : Ingestion configuration options.

    Returns
    -------
    TransportGraph : Directed weighted transport graph ready for pathfinding and VRP optimization.
    """
    net_dict = osm_to_network_dict(osm_data, config=config)
    return TransportGraph.from_dict(net_dict)
