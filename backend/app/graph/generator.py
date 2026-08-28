"""
app/graph/generator.py – Synthetic road-network generator for Q-Route.

Generates reproducible transport graphs that can be saved to JSON and
loaded back — so experiments start from identical conditions every run.

Generation strategy
-------------------
1. Place ``n_nodes`` nodes at random (x, y) positions in a
   ``grid_size_km`` × ``grid_size_km`` square.
2. Connect any pair of nodes within ``connect_radius_km`` (bidirectional).
3. Build the Euclidean Minimum Spanning Tree over all nodes and add its
   edges, guaranteeing full weak connectivity even for sparse graphs.
4. Assign road attributes (distance, speed → travel time, congestion,
   status) to every undirected edge; both directions share attributes.
5. Close a ``closed_fraction`` of non-MST edges so connectivity is
   preserved while still exercising closed-road logic.

CLI usage (from backend/ directory)
------------------------------------
    python -m app.graph.generator                      # defaults
    python -m app.graph.generator --nodes 30 --seed 7  # custom
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from .model import TransportGraph

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _euclidean(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_synthetic_network(
    n_nodes: int = 20,
    n_depots: int = 1,
    n_customers: int = 6,
    connect_radius_km: float = 3.5,
    grid_size_km: float = 10.0,
    closed_fraction: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Generate a reproducible synthetic transport network.

    Parameters
    ----------
    n_nodes          : total number of nodes (intersections + depots + customers)
    n_depots         : first ``n_depots`` nodes are labelled "depot"
    n_customers      : nodes randomly selected as "customer" (rest = "intersection")
    connect_radius_km: pairs within this distance receive a direct edge
    grid_size_km     : side length of the bounding box for node positions
    closed_fraction  : fraction of non-MST edges marked closed (0–1)
    seed             : NumPy random seed for reproducibility

    Returns
    -------
    dict with keys: "meta", "nodes", "edges"
    Compatible with ``TransportGraph.from_dict()`` and ``build_transport_graph()``.
    """
    rng = np.random.default_rng(seed)

    # ── 1. Node positions ─────────────────────────────────────────────
    positions: dict[int, tuple[float, float]] = {
        i: (float(rng.uniform(0, grid_size_km)), float(rng.uniform(0, grid_size_km)))
        for i in range(n_nodes)
    }

    # ── 2. Node types ─────────────────────────────────────────────────
    node_types: dict[int, str] = {i: "intersection" for i in range(n_nodes)}
    depot_ids = list(range(min(n_depots, n_nodes)))
    for d in depot_ids:
        node_types[d] = "depot"

    non_depot = [i for i in range(n_nodes) if i not in depot_ids]
    actual_customers = min(n_customers, len(non_depot))
    customer_ids = rng.choice(non_depot, size=actual_customers, replace=False).tolist()
    for c in customer_ids:
        node_types[c] = "customer"

    # ── 3. Candidate edges (radius-based) ─────────────────────────────
    candidate_pairs: set[tuple[int, int]] = set()
    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            if _euclidean(positions[i], positions[j]) <= connect_radius_km:
                candidate_pairs.add((i, j))

    # ── 4. MST edges (guarantee connectivity) ─────────────────────────
    complete = nx.Graph()
    complete.add_nodes_from(range(n_nodes))
    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            complete.add_edge(i, j, weight=_euclidean(positions[i], positions[j]))

    mst_pairs: set[tuple[int, int]] = {
        (min(u, v), max(u, v))
        for u, v in nx.minimum_spanning_tree(complete, weight="weight").edges()
    }

    all_undirected: set[tuple[int, int]] = candidate_pairs | mst_pairs

    # ── 5. Choose edges to close (never MST edges) ────────────────────
    closeable = list(all_undirected - mst_pairs)
    n_close = max(0, round(len(closeable) * closed_fraction))
    if closeable and n_close > 0:
        close_idx = rng.choice(len(closeable), size=min(n_close, len(closeable)), replace=False)
        closed_pairs: set[tuple[int, int]] = {closeable[int(i)] for i in close_idx}
    else:
        closed_pairs = set()

    # ── 6. Build edge list (both directions per undirected edge) ───────
    edge_list: list[dict] = []
    for (i, j) in all_undirected:
        dist = round(_euclidean(positions[i], positions[j]), 6)
        speed_kmh = float(rng.uniform(30.0, 80.0))          # random speed
        base_time = round((dist / speed_kmh) * 60.0, 6)     # minutes
        congestion = round(float(rng.uniform(1.0, 2.5)), 4)
        status = "closed" if (i, j) in closed_pairs else "open"

        for u, v in [(i, j), (j, i)]:
            edge_list.append({
                "u": u,
                "v": v,
                "distance": dist,
                "base_travel_time": base_time,
                "congestion_factor": congestion,
                "road_status": status,
            })

    # ── 7. Build node list ────────────────────────────────────────────
    node_list: list[dict] = [
        {
            "id": i,
            "node_type": node_types[i],
            "x": round(positions[i][0], 6),
            "y": round(positions[i][1], 6),
        }
        for i in range(n_nodes)
    ]

    return {
        "meta": {
            "n_nodes": n_nodes,
            "n_depots": n_depots,
            "n_customers": actual_customers,
            "grid_size_km": grid_size_km,
            "connect_radius_km": connect_radius_km,
            "closed_fraction": closed_fraction,
            "seed": seed,
        },
        "nodes": node_list,
        "edges": edge_list,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_network_json(data: dict, path: str | Path) -> Path:
    """Persist a network dict to a JSON file; creates parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


def load_network_json(path: str | Path) -> dict:
    """Load a network dict from a JSON file produced by ``save_network_json``."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_transport_graph(data: dict) -> TransportGraph:
    """
    Construct a ``TransportGraph`` from a network dict.

    Accepts dicts produced by ``generate_synthetic_network()``,
    ``load_network_json()``, or ``TransportGraph.to_dict()``.
    """
    return TransportGraph.from_dict(data)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic Q-Route transport network and save it to JSON."
    )
    parser.add_argument("--nodes", type=int, default=20, help="Number of nodes (default 20)")
    parser.add_argument("--depots", type=int, default=1, help="Number of depot nodes (default 1)")
    parser.add_argument("--customers", type=int, default=6, help="Number of customer nodes (default 6)")
    parser.add_argument("--radius", type=float, default=3.5, help="Connection radius km (default 3.5)")
    parser.add_argument("--grid", type=float, default=10.0, help="Grid side length km (default 10.0)")
    parser.add_argument("--closed", type=float, default=0.05, help="Fraction of edges to close (default 0.05)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument(
        "--out",
        type=str,
        default="../data/synthetic_network_default.json",
        help="Output JSON path (default ../data/synthetic_network_default.json)",
    )
    args = parser.parse_args()

    data = generate_synthetic_network(
        n_nodes=args.nodes,
        n_depots=args.depots,
        n_customers=args.customers,
        connect_radius_km=args.radius,
        grid_size_km=args.grid,
        closed_fraction=args.closed,
        seed=args.seed,
    )

    out_path = save_network_json(data, args.out)
    meta = data["meta"]
    n_edges = len(data["edges"]) // 2  # undirected count
    n_closed = sum(1 for e in data["edges"] if e["road_status"] == "closed" and e["u"] < e["v"])

    print(f"Generated synthetic network:")
    print(f"  Nodes    : {meta['n_nodes']}  (depots={meta['n_depots']}, customers={meta['n_customers']})")
    print(f"  Edges    : {n_edges} undirected ({len(data['edges'])} directed)")
    print(f"  Closed   : {n_closed} edge(s)")
    print(f"  Seed     : {meta['seed']}")
    print(f"  Saved to : {out_path.resolve()}")


if __name__ == "__main__":
    _cli()
