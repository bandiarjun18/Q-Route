"""
app/graph/osm_client.py – Live OpenStreetMap Network Acquisition for Q-Route (Milestone 13.2).

Provides an isolated, reliable HTTP acquisition client for fetching geographic road-network
data via the public Overpass API for a user-specified bounding box, and passing the raw
OSM response into the existing M13.1 parser (`app.graph.osm`).

Architecture:
    BoundingBox(south, west, north, east)
             ↓
    OSMClient.fetch_raw(...)  [Overpass QL / JSON over HTTP]
             ↓
    app.graph.osm.osm_to_network_dict(...)  [M13.1 Parser]
             ↓
    TransportGraph.from_dict(...)  [Q-Route Graph Engine]

Protected Constraints:
- Strict coordinate validation (south < north, west < east, latitude in [-90, 90], longitude in [-180, 180]).
- Explicit configurable timeout and endpoint URL.
- Comprehensive error handling (timeout, HTTP status errors, network failures, empty/malformed responses).
- Clean reuse of the existing M13.1 parser without duplicating parsing logic.
- Purely deterministic; no random modifications, no caching, and no external GIS dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import httpx

from .model import TransportGraph
from .osm import (
    OSMConfig,
    OSMEmptyNetworkError,
    OSMIngestionError,
    OSMInvalidDataError,
    OSMParseError,
    load_osm_network,
    osm_to_network_dict,
)

logger = logging.getLogger(__name__)

# Default Overpass API public endpoint
DEFAULT_OVERPASS_ENDPOINT: str = "https://overpass-api.de/api/interpreter"
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_USER_AGENT: str = "Q-Route-OSM-Ingestion/1.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OSMClientError(OSMIngestionError):
    """Base exception for all OSM client acquisition errors."""
    pass


class OSMInvalidBoundingBoxError(OSMClientError):
    """Raised when a bounding box fails geographic coordinate constraints."""
    pass


class OSMNetworkError(OSMClientError):
    """Raised when a network/transport error occurs connecting to the OSM API."""
    pass


class OSMTimeoutError(OSMClientError):
    """Raised when a request to the OSM API times out."""
    pass


class OSMHTTPError(OSMClientError):
    """Raised when the OSM API returns a non-200 HTTP status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class OSMResponseError(OSMClientError):
    """Raised when the OSM response body is empty, not valid JSON, or missing elements."""
    pass


# ---------------------------------------------------------------------------
# Bounding Box
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundingBox:
    """
    Geographic bounding box defined by cardinal coordinates in decimal degrees.

    Parameters
    ----------
    south : float – Southernmost latitude  [-90.0, 90.0]
    west  : float – Westernmost longitude  [-180.0, 180.0]
    north : float – Northernmost latitude  [-90.0, 90.0]
    east  : float – Easternmost longitude  [-180.0, 180.0]
    """

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate bounds and coordinate limits, raising OSMInvalidBoundingBoxError if violated."""
        # Latitude range checks
        if not isinstance(self.south, (int, float)) or not (-90.0 <= self.south <= 90.0):
            raise OSMInvalidBoundingBoxError(
                f"Invalid south latitude: {self.south!r}. Must be between -90.0 and 90.0."
            )
        if not isinstance(self.north, (int, float)) or not (-90.0 <= self.north <= 90.0):
            raise OSMInvalidBoundingBoxError(
                f"Invalid north latitude: {self.north!r}. Must be between -90.0 and 90.0."
            )

        # Longitude range checks
        if not isinstance(self.west, (int, float)) or not (-180.0 <= self.west <= 180.0):
            raise OSMInvalidBoundingBoxError(
                f"Invalid west longitude: {self.west!r}. Must be between -180.0 and 180.0."
            )
        if not isinstance(self.east, (int, float)) or not (-180.0 <= self.east <= 180.0):
            raise OSMInvalidBoundingBoxError(
                f"Invalid east longitude: {self.east!r}. Must be between -180.0 and 180.0."
            )

        # Relational constraints
        if self.south >= self.north:
            raise OSMInvalidBoundingBoxError(
                f"South latitude ({self.south}) must be strictly less than north latitude ({self.north})."
            )
        if self.west >= self.east:
            raise OSMInvalidBoundingBoxError(
                f"West longitude ({self.west}) must be strictly less than east longitude ({self.east})."
            )

    def to_overpass_bbox(self) -> str:
        """Return the bounding box formatted for Overpass QL (south,west,north,east)."""
        return f"{self.south:.6f},{self.west:.6f},{self.north:.6f},{self.east:.6f}"


# ---------------------------------------------------------------------------
# Client Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OSMClientConfig:
    """
    Configuration options for the OSM acquisition client.

    Parameters
    ----------
    endpoint_url    : Base URL of the Overpass interpreter API.
    timeout_seconds : Network timeout in seconds for HTTP requests.
    user_agent      : HTTP User-Agent header sent with requests.
    """

    endpoint_url: str = DEFAULT_OVERPASS_ENDPOINT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    user_agent: str = DEFAULT_USER_AGENT


# ---------------------------------------------------------------------------
# Overpass Query Builder
# ---------------------------------------------------------------------------

def build_overpass_query(bbox: BoundingBox, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """
    Construct a deterministic Overpass QL query string requesting drivable highway ways and nodes.

    Parameters
    ----------
    bbox            : Validated BoundingBox instance.
    timeout_seconds : Server-side query execution timeout.

    Returns
    -------
    str : Overpass QL query text.
    """
    bbox_str = bbox.to_overpass_bbox()
    timeout_int = max(5, int(timeout_seconds))
    return (
        f"[out:json][timeout:{timeout_int}];\n"
        f"(\n"
        f"  way[\"highway\"]({bbox_str});\n"
        f");\n"
        f"out body;\n"
        f">;\n"
        f"out skel qt;\n"
    )


# ---------------------------------------------------------------------------
# OSM Client
# ---------------------------------------------------------------------------

class OSMClient:
    """
    HTTP client for acquiring OpenStreetMap road networks via Overpass API.

    Parameters
    ----------
    config      : Optional OSMClientConfig specifying endpoint and timeout.
    http_client : Optional httpx.Client instance for testing or custom transports.
    """

    def __init__(
        self,
        config: Optional[OSMClientConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or OSMClientConfig()
        self._http_client = http_client

    def fetch_raw_osm(self, bbox: BoundingBox) -> dict:
        """
        Execute an Overpass QL query for the specified bounding box and return raw JSON elements.

        Parameters
        ----------
        bbox : Validated geographic bounding box.

        Returns
        -------
        dict : Parsed JSON response containing an 'elements' list.

        Raises
        ------
        OSMTimeoutError : If the network or server timeout expires.
        OSMNetworkError : If a network connection error occurs.
        OSMHTTPError    : If the server returns a non-200 status code.
        OSMResponseError: If the response is empty or malformed.
        """
        query = build_overpass_query(bbox, timeout_seconds=self.config.timeout_seconds)
        headers = {
            "User-Agent": self.config.user_agent,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        logger.debug(
            "Fetching OSM network from %s for bbox (%s)",
            self.config.endpoint_url,
            bbox.to_overpass_bbox(),
        )

        try:
            if self._http_client is not None:
                resp = self._http_client.post(
                    self.config.endpoint_url,
                    data={"data": query},
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    resp = client.post(
                        self.config.endpoint_url,
                        data={"data": query},
                        headers=headers,
                    )
        except httpx.TimeoutException as e:
            raise OSMTimeoutError(
                f"OSM request timed out after {self.config.timeout_seconds}s for bbox {bbox.to_overpass_bbox()}: {e}"
            ) from e
        except httpx.RequestError as e:
            raise OSMNetworkError(
                f"Failed to connect to OSM Overpass API at {self.config.endpoint_url}: {e}"
            ) from e

        if resp.status_code != 200:
            raise OSMHTTPError(
                status_code=resp.status_code,
                message=f"Overpass API returned status {resp.status_code}: {resp.text[:200]}",
            )

        if not resp.text or not resp.text.strip():
            raise OSMResponseError("Received empty response from OSM Overpass API.")

        try:
            data = resp.json()
        except Exception as e:
            raise OSMResponseError(f"Failed to parse Overpass response as JSON: {e}") from e

        if not isinstance(data, dict) or "elements" not in data:
            raise OSMResponseError("Overpass JSON response missing required 'elements' key.")

        return data

    def fetch_network_dict(
        self,
        bbox: BoundingBox,
        osm_config: Optional[OSMConfig] = None,
    ) -> dict:
        """
        Fetch OSM data and parse it into a Q-Route network dictionary using the M13.1 parser.

        Parameters
        ----------
        bbox       : Geographic bounding box.
        osm_config : Optional ingestion configuration options.

        Returns
        -------
        dict : Q-Route network dictionary with 'meta', 'nodes', 'edges'.
        """
        raw_data = self.fetch_raw_osm(bbox)
        return osm_to_network_dict(raw_data, config=osm_config)

    def load_network(
        self,
        bbox: BoundingBox,
        osm_config: Optional[OSMConfig] = None,
    ) -> TransportGraph:
        """
        Fetch OSM data and convert directly into a canonical Q-Route ``TransportGraph``.

        Parameters
        ----------
        bbox       : Geographic bounding box.
        osm_config : Optional ingestion configuration options.

        Returns
        -------
        TransportGraph : Directed weighted graph ready for routing and optimization.
        """
        net_dict = self.fetch_network_dict(bbox, osm_config=osm_config)
        return TransportGraph.from_dict(net_dict)


# ---------------------------------------------------------------------------
# Public Helper Functions
# ---------------------------------------------------------------------------

def fetch_osm_from_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    client_config: Optional[OSMClientConfig] = None,
    osm_config: Optional[OSMConfig] = None,
) -> dict:
    """
    Fetch and parse real OSM road-network data for the specified bounding box coordinates.

    Parameters
    ----------
    south, west, north, east : Bounding box coordinates in decimal degrees.
    client_config            : Optional HTTP acquisition settings.
    osm_config               : Optional M13.1 parsing/speed/filtering settings.

    Returns
    -------
    dict : Q-Route network dictionary compatible with ``TransportGraph.from_dict()``.
    """
    bbox = BoundingBox(south=south, west=west, north=north, east=east)
    client = OSMClient(config=client_config)
    return client.fetch_network_dict(bbox, osm_config=osm_config)


def load_osm_from_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    client_config: Optional[OSMClientConfig] = None,
    osm_config: Optional[OSMConfig] = None,
) -> TransportGraph:
    """
    Fetch real OSM road-network data and return a fully initialized Q-Route ``TransportGraph``.

    Parameters
    ----------
    south, west, north, east : Bounding box coordinates in decimal degrees.
    client_config            : Optional HTTP acquisition settings.
    osm_config               : Optional M13.1 parsing/speed/filtering settings.

    Returns
    -------
    TransportGraph : Canonical directed weighted graph ready for pathfinding and VRP.
    """
    bbox = BoundingBox(south=south, west=west, north=north, east=east)
    client = OSMClient(config=client_config)
    return client.load_network(bbox, osm_config=osm_config)
