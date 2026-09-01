"""
app/api/routes/network.py – POST /network endpoint.

Creates a synthetic transport network using the existing graph generator
(Milestone 2) and stores it in application state.

Calling this endpoint resets all downstream state (fleet, optimization,
incidents, routes) to ensure consistency.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_state, require_graph
from app.api.models import EdgeOut, NetworkRequest, NetworkResponse, NodeOut, OSMNetworkPresetRequest
from app.api.state import AppState
from app.db.crud import get_active_network, get_network_nodes_and_edges, save_network
from app.db.session import get_db
from app.graph.generator import generate_synthetic_network
from app.graph.model import TransportGraph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/network", tags=["Network"])


@router.get(
    "",
    response_model=NetworkResponse,
    status_code=status.HTTP_200_OK,
    summary="Get currently active transport network",
    description="Retrieves the currently loaded transport network nodes, edges, and topology.",
)
@router.get(
    "/current",
    response_model=NetworkResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_current_network(
    state: AppState = Depends(get_state),
    db: Session = Depends(get_db),
) -> NetworkResponse:
    """Return active transport network topology and metadata."""
    # 1. In-memory graph available
    if state.graph is not None:
        tg = state.graph
        g = tg.graph

        node_types = {n: d.get("node_type", "intersection") for n, d in g.nodes(data=True)}
        n_depots_actual = sum(1 for t in node_types.values() if t == "depot")
        n_customers_actual = sum(1 for t in node_types.values() if t == "customer")
        n_intersections = sum(1 for t in node_types.values() if t == "intersection")

        nodes_out = [
            NodeOut(
                id=n,
                node_type=d.get("node_type", "intersection"),
                x=float(d.get("x", 0.0)),
                y=float(d.get("y", 0.0)),
                lat=float(d["lat"]) if "lat" in d and d["lat"] is not None else None,
                lon=float(d["lon"]) if "lon" in d and d["lon"] is not None else None,
            )
            for n, d in g.nodes(data=True)
        ]

        edges_out = [
            EdgeOut(
                u=u,
                v=v,
                distance=float(data.get("distance", 0.0)),
                base_travel_time=float(data.get("base_travel_time", 0.0)),
                congestion_factor=float(data.get("congestion_factor", 1.0)),
                road_status=str(data.get("road_status", "open")),
            )
            for u, v, data in g.edges(data=True)
        ]

        meta = state.network_meta or {}
        return NetworkResponse(
            n_nodes=tg.node_count(),
            n_edges=tg.edge_count(),
            n_depots=n_depots_actual,
            n_customers=n_customers_actual,
            n_intersections=n_intersections,
            seed=meta.get("seed", 42),
            nodes=nodes_out,
            edges=edges_out,
        )

    # 2. Database fallback if in-memory graph is None
    active_net = get_active_network(db)
    if active_net:
        db_nodes, db_edges = get_network_nodes_and_edges(db, active_net.id)
        if db_nodes:
            tg = TransportGraph()
            is_osm = any(k in active_net.name.lower() for k in ("osm", "real-world", "bangalore"))
            nodes_out = []
            for nd in db_nodes:
                lat = float(nd.y) if is_osm else None
                lon = float(nd.x) if is_osm else None
                tg.add_node(
                    node_id=nd.node_id,
                    x=float(nd.x),
                    y=float(nd.y),
                    node_type=nd.node_type,
                    lat=lat,
                    lon=lon,
                )
                nodes_out.append(
                    NodeOut(
                        id=nd.node_id,
                        node_type=nd.node_type,
                        x=float(nd.x),
                        y=float(nd.y),
                        lat=lat,
                        lon=lon,
                    )
                )

            edges_out = []
            for ed in db_edges:
                tg.add_edge(
                    u=ed.u,
                    v=ed.v,
                    distance=float(ed.distance),
                    base_travel_time=float(ed.base_travel_time),
                    congestion_factor=float(ed.congestion_factor),
                    road_status=str(ed.road_status),
                )
                edges_out.append(
                    EdgeOut(
                        u=ed.u,
                        v=ed.v,
                        distance=float(ed.distance),
                        base_travel_time=float(ed.base_travel_time),
                        congestion_factor=float(ed.congestion_factor),
                        road_status=str(ed.road_status),
                    )
                )

            state.graph = tg
            state.network_db_id = active_net.id
            state.network_meta = {
                "source": "PostgreSQL",
                "name": active_net.name,
                "n_nodes": active_net.n_nodes,
                "n_edges": active_net.n_edges,
                "seed": active_net.seed,
            }

            return NetworkResponse(
                n_nodes=active_net.n_nodes,
                n_edges=active_net.n_edges,
                n_depots=active_net.n_depots,
                n_customers=active_net.n_customers,
                n_intersections=active_net.n_intersections,
                seed=active_net.seed,
                nodes=nodes_out,
                edges=edges_out,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No active network loaded. Call POST /network or POST /network/osm-preset first.",
    )


@router.post(
    "",
    response_model=NetworkResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a synthetic transport network",
    description=(
        "Generates a reproducible synthetic road network using the M2 graph "
        "generator.  Replaces any previously loaded network and clears all "
        "downstream state (fleet, optimization, incidents)."
    ),
)
def create_network(
    body: NetworkRequest,
    state: AppState = Depends(get_state),
    db: Session = Depends(get_db),
) -> NetworkResponse:
    """
    Generate and store a synthetic transport network.

    The generated graph is stored in ``app.state.qroute.graph`` and is
    available to subsequent ``POST /fleet`` calls for node-id validation.

    All prior fleet / optimization / incident state is cleared because a new
    network invalidates all node references from the previous one.
    """
    # ── 1. Generate the network ─────────────────────────────────────────
    net_data = generate_synthetic_network(
        n_nodes=body.n_nodes,
        n_depots=body.n_depots,
        n_customers=body.n_customers,
        connect_radius_km=body.connect_radius_km,
        grid_size_km=body.grid_size_km,
        closed_fraction=body.closed_fraction,
        seed=body.seed,
    )
    tg = TransportGraph.from_dict(net_data)

    # ── 2. Count node types for the response ────────────────────────────
    g = tg.graph
    node_types = {n: d.get("node_type", "intersection") for n, d in g.nodes(data=True)}
    n_depots_actual = sum(1 for t in node_types.values() if t == "depot")
    n_customers_actual = sum(1 for t in node_types.values() if t == "customer")
    n_intersections = sum(1 for t in node_types.values() if t == "intersection")

    # ── 3. Store state (clears all downstream state) ────────────────────
    state.clear_from_network()
    state.graph = tg
    state.network_meta = {
        "n_nodes": tg.node_count(),
        "n_edges": tg.edge_count(),
        "n_depots": n_depots_actual,
        "n_customers": n_customers_actual,
        "n_intersections": n_intersections,
        "seed": body.seed,
    }

    # ── 4. Persist to PostgreSQL ────────────────────────────────────────
    try:
        net_model = save_network(
            db=db,
            net_data=net_data,
            seed=body.seed,
            connect_radius_km=body.connect_radius_km,
            grid_size_km=body.grid_size_km,
            closed_fraction=body.closed_fraction,
            name=f"Network-{body.seed}-{body.n_nodes}N",
        )
        state.network_db_id = net_model.id
    except Exception as exc:
        logger.warning("Failed to persist network to PostgreSQL: %s", exc)


    # ── 4. Build response ────────────────────────────────────────────────
    nodes_out = [
        NodeOut(
            id=n,
            node_type=d.get("node_type", "intersection"),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            lat=float(d["lat"]) if "lat" in d and d["lat"] is not None else None,
            lon=float(d["lon"]) if "lon" in d and d["lon"] is not None else None,
        )
        for n, d in g.nodes(data=True)
    ]

    edges_out = [
        EdgeOut(
            u=u,
            v=v,
            distance=float(data.get("distance", 0.0)),
            base_travel_time=float(data.get("base_travel_time", 0.0)),
            congestion_factor=float(data.get("congestion_factor", 1.0)),
            road_status=str(data.get("road_status", "open")),
        )
        for u, v, data in g.edges(data=True)
    ]

    return NetworkResponse(
        n_nodes=tg.node_count(),
        n_edges=tg.edge_count(),
        n_depots=n_depots_actual,
        n_customers=n_customers_actual,
        n_intersections=n_intersections,
        seed=body.seed,
        nodes=nodes_out,
        edges=edges_out,
    )


@router.post(
    "/osm-preset",
    response_model=NetworkResponse,
    status_code=status.HTTP_200_OK,
    summary="Load a real-world OpenStreetMap road network",
    description=(
        "Loads and validates a high-fidelity real-world OpenStreetMap urban "
        "road network (Bangalore Logistics Corridor) with true geographic coordinates, "
        "road segment curve geometries, speed limits, and oneway routing rules. "
        "Persists the network to PostgreSQL and initializes state."
    ),
)
def load_osm_preset_network(
    body: Optional[OSMNetworkPresetRequest] = None,
    state: AppState = Depends(get_state),
    db: Session = Depends(get_db),
) -> NetworkResponse:
    """
    Ingest a real-world OSM network into AppState and PostgreSQL.
    """
    from app.graph.demo_data import REAL_WORLD_OSM_XML
    from app.graph.osm import osm_to_network_dict, osm_to_transport_graph

    xml_content = (body.osm_xml if body and body.osm_xml else REAL_WORLD_OSM_XML)
    tg = osm_to_transport_graph(xml_content)
    net_data = osm_to_network_dict(xml_content)

    # Count node types
    g = tg.graph
    node_types = {n: d.get("node_type", "intersection") for n, d in g.nodes(data=True)}
    n_depots_actual = sum(1 for t in node_types.values() if t == "depot")
    n_customers_actual = sum(1 for t in node_types.values() if t == "customer")
    n_intersections = sum(1 for t in node_types.values() if t == "intersection")

    # Store state
    state.clear_from_network()
    state.graph = tg
    state.network_meta = {
        "source": "OpenStreetMap",
        "preset": getattr(body, "preset_name", "bangalore_urban") if body else "bangalore_urban",
        "n_nodes": tg.node_count(),
        "n_edges": tg.edge_count(),
        "n_depots": n_depots_actual,
        "n_customers": n_customers_actual,
        "n_intersections": n_intersections,
        "seed": 42,
    }

    # Persist to PostgreSQL
    try:
        net_model = save_network(
            db=db,
            net_data=net_data,
            seed=42,
            connect_radius_km=0.0,
            grid_size_km=0.0,
            closed_fraction=0.0,
            name="Real-World OSM Network (Bangalore Central)",
        )
        state.network_db_id = net_model.id
    except Exception as exc:
        logger.warning("Failed to persist OSM network to PostgreSQL: %s", exc)

    nodes_out = [
        NodeOut(
            id=n,
            node_type=d.get("node_type", "intersection"),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            lat=float(d["lat"]) if "lat" in d and d["lat"] is not None else None,
            lon=float(d["lon"]) if "lon" in d and d["lon"] is not None else None,
        )
        for n, d in g.nodes(data=True)
    ]

    edges_out = [
        EdgeOut(
            u=u,
            v=v,
            distance=float(data.get("distance", 0.0)),
            base_travel_time=float(data.get("base_travel_time", 0.0)),
            congestion_factor=float(data.get("congestion_factor", 1.0)),
            road_status=str(data.get("road_status", "open")),
        )
        for u, v, data in g.edges(data=True)
    ]

    return NetworkResponse(
        n_nodes=tg.node_count(),
        n_edges=tg.edge_count(),
        n_depots=n_depots_actual,
        n_customers=n_customers_actual,
        n_intersections=n_intersections,
        seed=42,
        nodes=nodes_out,
        edges=edges_out,
    )
