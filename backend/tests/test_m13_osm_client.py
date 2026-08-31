"""
tests/test_m13_osm_client.py – Test suite for Live OpenStreetMap Network Acquisition (M13.2).

Verifies:
1. Valid bounding box query generation.
2. Invalid latitude rejection (south/north out of [-90, 90]).
3. Invalid longitude rejection (west/east out of [-180, 180]).
4. Relational rejection when south >= north.
5. Relational rejection when west >= east.
6. Successful Overpass response forwarding to M13.1 parser and valid TransportGraph output.
7. HTTP error handling (400, 429, 500, 504) raising OSMHTTPError.
8. Transport / network connection failure raising OSMNetworkError.
9. Network timeout raising OSMTimeoutError.
10. Empty response raising OSMResponseError.
11. Malformed JSON response or missing 'elements' key raising OSMResponseError.
12. Configurable Overpass endpoint URL.
13. Configurable request timeout.
14. Seamless M13.1 parser reuse and integration.
15. Deterministic query generation for identical bounding boxes.
"""

import json
import pytest
import httpx

from app.graph import (
    TransportGraph,
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


# ---------------------------------------------------------------------------
# Synthetic Mock Overpass Response Fixture
# ---------------------------------------------------------------------------

MOCK_OVERPASS_JSON = {
    "version": 0.6,
    "generator": "Overpass API Mock",
    "elements": [
        {"type": "node", "id": 1001, "lat": 17.385044, "lon": 78.486671, "tags": {"name": "Charminar Junction"}},
        {"type": "node", "id": 1002, "lat": 17.390000, "lon": 78.490000, "tags": {"name": "Madina Crossing"}},
        {"type": "node", "id": 1003, "lat": 17.395000, "lon": 78.495000, "tags": {"name": "Afzal Gunj"}},
        {
            "type": "way",
            "id": 5001,
            "nodes": [1001, 1002],
            "tags": {"highway": "primary", "name": "Charminar Road", "maxspeed": "50", "oneway": "no"},
        },
        {
            "type": "way",
            "id": 5002,
            "nodes": [1002, 1003],
            "tags": {"highway": "secondary", "name": "High Court Road", "maxspeed": "40", "oneway": "yes"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_valid_bounding_box_and_query_generation():
    """Test 1 & 15: Valid bounding box generates deterministic Overpass QL query."""
    bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)
    assert bbox.south == 17.38
    assert bbox.west == 78.48
    assert bbox.north == 17.40
    assert bbox.east == 78.50
    assert bbox.to_overpass_bbox() == "17.380000,78.480000,17.400000,78.500000"

    query1 = build_overpass_query(bbox, timeout_seconds=30)
    query2 = build_overpass_query(bbox, timeout_seconds=30)

    assert "way[\"highway\"](17.380000,78.480000,17.400000,78.500000);" in query1
    assert "[timeout:30];" in query1
    assert query1 == query2  # Determinism


def test_invalid_latitude_rejection():
    """Test 2: Latitude out of [-90, 90] bounds raises OSMInvalidBoundingBoxError."""
    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=-95.0, west=78.48, north=17.40, east=78.50)

    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.38, west=78.48, north=95.0, east=78.50)


def test_invalid_longitude_rejection():
    """Test 3: Longitude out of [-180, 180] bounds raises OSMInvalidBoundingBoxError."""
    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.38, west=-185.0, north=17.40, east=78.50)

    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.38, west=78.48, north=17.40, east=185.0)


def test_south_greater_equal_north_rejection():
    """Test 4: south >= north raises OSMInvalidBoundingBoxError."""
    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.40, west=78.48, north=17.40, east=78.50)

    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.45, west=78.48, north=17.40, east=78.50)


def test_west_greater_equal_east_rejection():
    """Test 5: west >= east raises OSMInvalidBoundingBoxError."""
    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.38, west=78.50, north=17.40, east=78.50)

    with pytest.raises(OSMInvalidBoundingBoxError):
        BoundingBox(south=17.38, west=78.55, north=17.40, east=78.50)


def test_successful_osm_response_and_transport_graph():
    """Test 6 & 14: Successful Overpass response is parsed into a valid TransportGraph."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_OVERPASS_JSON)

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        client = OSMClient(http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        graph = client.load_network(bbox)
        assert isinstance(graph, TransportGraph)
        assert graph.node_count() == 3
        # Edges: 5001 is bidirectional (2), 5002 is oneway (1) => 3 total edges
        assert graph.edge_count() == 3


def test_http_error_handling():
    """Test 7: Non-200 HTTP status code raises OSMHTTPError with correct status."""
    for status_code in [400, 429, 500, 504]:
        def handler(request: httpx.Request, sc=status_code) -> httpx.Response:
            return httpx.Response(sc, text=f"Overpass Error {sc}")

        mock_transport = httpx.MockTransport(handler)
        with httpx.Client(transport=mock_transport) as mock_client:
            client = OSMClient(http_client=mock_client)
            bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

            with pytest.raises(OSMHTTPError) as exc_info:
                client.fetch_raw_osm(bbox)
            assert exc_info.value.status_code == status_code


def test_network_connection_failure():
    """Test 8: Transport connection failure raises OSMNetworkError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect to host", request=request)

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        client = OSMClient(http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        with pytest.raises(OSMNetworkError):
            client.fetch_raw_osm(bbox)


def test_timeout_handling():
    """Test 9: Request timeout raises OSMTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out", request=request)

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        client = OSMClient(http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        with pytest.raises(OSMTimeoutError):
            client.fetch_raw_osm(bbox)


def test_empty_response_handling():
    """Test 10: Empty HTTP response body raises OSMResponseError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="")

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        client = OSMClient(http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        with pytest.raises(OSMResponseError):
            client.fetch_raw_osm(bbox)


def test_malformed_json_response():
    """Test 11: Non-JSON or missing 'elements' raises OSMResponseError."""
    # Invalid JSON syntax
    def handler_invalid_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>Error</body></html>")

    mock_transport = httpx.MockTransport(handler_invalid_json)
    with httpx.Client(transport=mock_transport) as mock_client:
        client = OSMClient(http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        with pytest.raises(OSMResponseError):
            client.fetch_raw_osm(bbox)

    # Valid JSON but missing 'elements'
    def handler_missing_elements(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": 0.6, "remark": "No elements"})

    mock_transport2 = httpx.MockTransport(handler_missing_elements)
    with httpx.Client(transport=mock_transport2) as mock_client:
        client2 = OSMClient(http_client=mock_client)
        with pytest.raises(OSMResponseError):
            client2.fetch_raw_osm(bbox)


def test_configurable_endpoint():
    """Test 12: Custom Overpass endpoint URL is passed in request."""
    requested_url = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_url.append(str(request.url))
        return httpx.Response(200, json=MOCK_OVERPASS_JSON)

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        cfg = OSMClientConfig(endpoint_url="https://custom-overpass.local/api/interpreter")
        client = OSMClient(config=cfg, http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        client.fetch_raw_osm(bbox)
        assert requested_url == ["https://custom-overpass.local/api/interpreter"]


def test_configurable_timeout():
    """Test 13: Custom timeout is embedded in query and configured in client."""
    captured_data = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_data.append(request.content.decode("utf-8"))
        return httpx.Response(200, json=MOCK_OVERPASS_JSON)

    mock_transport = httpx.MockTransport(handler)
    with httpx.Client(transport=mock_transport) as mock_client:
        cfg = OSMClientConfig(timeout_seconds=45.0)
        client = OSMClient(config=cfg, http_client=mock_client)
        bbox = BoundingBox(south=17.38, west=78.48, north=17.40, east=78.50)

        client.fetch_raw_osm(bbox)
        assert len(captured_data) == 1
        assert "timeout%3A45" in captured_data[0] or "timeout:45" in captured_data[0]


def test_convenience_functions(monkeypatch):
    """Test 14b: fetch_osm_from_bbox and load_osm_from_bbox functions."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_OVERPASS_JSON)

    mock_transport = httpx.MockTransport(handler)

    # Patch httpx.Client to use mock_transport
    real_client_init = httpx.Client.__init__
    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = mock_transport
        real_client_init(self, *args, **kwargs)
    monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    net_dict = fetch_osm_from_bbox(south=17.38, west=78.48, north=17.40, east=78.50)
    assert "nodes" in net_dict
    assert "edges" in net_dict
    assert len(net_dict["nodes"]) == 3

    graph = load_osm_from_bbox(south=17.38, west=78.48, north=17.40, east=78.50)
    assert isinstance(graph, TransportGraph)
    assert graph.node_count() == 3
