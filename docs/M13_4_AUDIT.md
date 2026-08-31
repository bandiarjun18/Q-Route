# Milestone 13.4 Audit Report: Real-World Location → OSM TransportGraph Node Mapping

**Project**: Q-Route Fleet Logistics Platform
**Milestone**: M13.4 (Real-World Location → OSM TransportGraph Node Mapping)
**Status**: Completed and Verified
**Date**: August 31, 2026

---

## 1. Objective

The objective of Milestone 13.4 is to implement a robust, deterministic, and lightweight geographic mapping utility in the Q-Route graph layer that maps real-world geographic coordinates $(\text{latitude}, \text{longitude})$ to the nearest node in an OpenStreetMap-derived canonical `TransportGraph`.

This capability allows future customers, depots, delivery stops, and vehicles to be specified using real-world decimal-degree coordinates, seamlessly resolving them into canonical graph nodes without requiring changes to downstream VRP modeling, feasibility checking, or QPSO optimization.

---

## 2. Architecture Inspection Findings

Prior to implementation, the existing codebase was inspected:

1. **Coordinate Representation in `TransportGraph` (`backend/app/graph/model.py`, `osm.py`)**:
   - In OSM-derived networks, nodes store geographic coordinates in `node["lat"]` and `node["lon"]` (in decimal degrees), alongside canonical `node["x"] = lon` and `node["y"] = lat`.
   - In synthetic graphs, `node["x"]` and `node["y"]` represent Cartesian grid distances (in kilometers) and omit explicit `lat`/`lon` attributes.
2. **Node ID Conventions**:
   - OSM graphs use unique OSM node IDs (e.g. `"101"`, `101`, string or integer hashable identifiers).
3. **Existing Nearest-Node Logic**:
   - No nearest-node or spatial mapping logic existed prior to M13.4.
4. **Downstream VRP & QPSO Decoupling**:
   - `Customer.location_node` and `Vehicle.depot_node` directly consume node IDs.
   - Mapping $(\text{latitude}, \text{longitude}) \to \text{node\_id}$ integrates completely upstream without requiring any modifications to `Customer`, `Vehicle`, `VRPProblem`, `objective.py`, `feasibility.py`, or `QPSO`.

---

## 3. Nearest-Node Algorithm & Implementation

The mapping engine is implemented in `backend/app/graph/osm.py` and exported through `backend/app/graph/__init__.py`.

### Primary Function: `nearest_graph_node`

```python
def nearest_graph_node(
    graph: TransportGraph,
    latitude: float,
    longitude: float,
    *,
    return_distance: bool = False,
) -> Union[Any, Tuple[Any, float]]:
```

#### Algorithm Steps:
1. **Input Validation**:
   - Ensures `graph` is a valid, non-empty `TransportGraph`.
   - Validates that `latitude` $\in [-90.0, 90.0]$ and `longitude` $\in [-180.0, 180.0]$. Rejects non-numeric types, `NaN`, and `inf`.
2. **Node Coordinate Extraction**:
   - Safely extracts `(lat, lon)` from candidate node attributes (`lat`/`lon` or `latitude`/`longitude`).
   - Safely ignores malformed or non-geographic nodes.
   - If no valid coordinate-bearing nodes exist in the graph, raises `OSMInvalidDataError`.
3. **Geodesic Distance Calculation**:
   - Uses the great-circle Haversine formula (`haversine_distance`) on a spherical Earth model ($R = 6371.0088\text{ km}$).
   - Accurately accounts for meridional convergence at higher latitudes (where 1° longitude $\ll$ 1° latitude), preventing distortion inherent to Cartesian degree arithmetic.
4. **Deterministic Tie-Breaking**:
   - Candidate nodes are evaluated as `(distance_km, str(node_id), node_id)`.
   - If multiple candidates share an identical minimal distance, the candidate with the lexicographically smallest string node ID is deterministically selected.
5. **Return Value**:
   - Returns the nearest `node_id` (or `(node_id, distance_km)` if `return_distance=True`).

### Customer & Depot Mapping Adapters

Convenience helpers are provided for clean upstream customer/depot assignment:
- `map_coordinate_to_node(graph, latitude, longitude) -> Any`: Maps a single real-world point to its nearest graph node ID.
- `map_coordinates_to_nodes(graph, coordinates) -> list[Any]`: Batch maps multiple `(latitude, longitude)` tuples to their corresponding nearest node IDs.

---

## 4. Verification Results

### A. Focused M13.4 Tests (`backend/tests/test_m13_4_location_mapping.py`)

All 12 focused tests passed cleanly:
1. `test_nearest_node_exact_coordinate`: Exact coordinate match selects target node ($0.0\text{ km}$ distance).
2. `test_nearest_node_between_nodes`: Closest node selected among multiple candidates.
3. `test_nearest_node_haversine_behavior`: High-latitude test ($60^\circ\text{ N}$) proves great-circle Haversine selection over Cartesian degree distortion.
4. `test_invalid_latitude`: Out-of-bounds, `NaN`, and non-numeric latitudes rejected.
5. `test_invalid_longitude`: Out-of-bounds, `NaN`, and non-numeric longitudes rejected.
6. `test_graph_without_coordinates`: Non-geographic graphs fail cleanly with `OSMInvalidDataError`.
7. `test_malformed_node_coordinates`: Malformed node attributes safely skipped without crashing.
8. `test_empty_graph`: Empty graphs raise `OSMEmptyNetworkError`.
9. `test_deterministic_tie_break`: Equidistant candidates produce identical selection across repeated evaluations.
10. `test_existing_osm_graph_compatibility`: M13.3 OSM-generated `TransportGraph` resolves coordinates accurately.
11. `test_customer_depot_adapters`: Single and batch mapping adapters verify clean customer/depot assignment.
12. `test_return_distance_option`: `return_distance=True` accurately returns `(node_id, distance_km)`.

### B. Full Backend Regression

Full backend pytest suite passed: **440/440 passed**.

### C. Frontend Production Build

Frontend production build succeeded with **0 errors**.

---

## 5. Protected Components Integrity

The following protected components were verified to be **completely unmodified**:
- `backend/app/qpso/*`
- `backend/app/vrp/objective.py`
- `backend/app/vrp/feasibility.py`
- `backend/app/incidents/rerouting.py`
- `backend/app/incidents/model.py`
- `backend/app/graph/generator.py`
- `backend/app/db/*`
- `frontend/*`
- `README.md`
- `requirements.txt` (Zero new dependencies added)
