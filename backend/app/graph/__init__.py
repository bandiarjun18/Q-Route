"""
app/graph/__init__.py – Public API for the Q-Route graph engine.

Import from here rather than from sub-modules directly:

    from app.graph import TransportGraph, WeightConfig, shortest_path
    from app.graph import generate_synthetic_network, build_transport_graph
"""

from .model import TransportGraph, WeightConfig
from .generator import (
    generate_synthetic_network,
    save_network_json,
    load_network_json,
    build_transport_graph,
)
from .pathfinding import shortest_path, path_cost
from .osm import (
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
    osm_to_transport_graph,
    load_osm_network,
    nearest_graph_node,
    map_coordinate_to_node,
    map_coordinates_to_nodes,
)
from .osm_client import (
    BoundingBox,
    OSMClientConfig,
    OSMClient,
    OSMClientError,
    OSMInvalidBoundingBoxError,
    OSMNetworkError,
    OSMTimeoutError,
    OSMHTTPError,
    OSMResponseError,
    build_overpass_query,
    fetch_osm_from_bbox,
    load_osm_from_bbox,
)

__all__ = [
    # Model
    "TransportGraph",
    "WeightConfig",
    # Generator
    "generate_synthetic_network",
    "save_network_json",
    "load_network_json",
    "build_transport_graph",
    # Pathfinding
    "shortest_path",
    "path_cost",
    # OSM Ingestion (M13.1 & M13.3)
    "OSMConfig",
    "OSMIngestionError",
    "OSMParseError",
    "OSMInvalidDataError",
    "OSMEmptyNetworkError",
    "haversine_distance",
    "parse_maxspeed",
    "calculate_travel_time_minutes",
    "parse_osm_xml",
    "parse_osm_json",
    "osm_to_network_dict",
    "osm_to_transport_graph",
    "load_osm_network",
    # Location Mapping (M13.4)
    "nearest_graph_node",
    "map_coordinate_to_node",
    "map_coordinates_to_nodes",
    # OSM Acquisition Client (M13.2)
    "BoundingBox",
    "OSMClientConfig",
    "OSMClient",
    "OSMClientError",
    "OSMInvalidBoundingBoxError",
    "OSMNetworkError",
    "OSMTimeoutError",
    "OSMHTTPError",
    "OSMResponseError",
    "build_overpass_query",
    "fetch_osm_from_bbox",
    "load_osm_from_bbox",
]
