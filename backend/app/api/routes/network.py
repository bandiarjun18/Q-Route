"""
app/api/routes/network.py – POST /network endpoint.

Creates a synthetic transport network using the existing graph generator
(Milestone 2) and stores it in application state.

Calling this endpoint resets all downstream state (fleet, optimization,
incidents, routes) to ensure consistency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_state
from app.api.models import EdgeOut, NetworkRequest, NetworkResponse, NodeOut
from app.api.state import AppState
from app.graph.generator import generate_synthetic_network
from app.graph.model import TransportGraph

router = APIRouter(prefix="/network", tags=["Network"])


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

    # ── 4. Build response ────────────────────────────────────────────────
    nodes_out = [
        NodeOut(
            id=n,
            node_type=d.get("node_type", "intersection"),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
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
