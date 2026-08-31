# Milestone 13.3 Audit Report: OSM → TransportGraph Integration

**Project**: Q-Route Fleet Logistics Platform
**Milestone**: M13.3 (OpenStreetMap → Canonical TransportGraph Integration)
**Status**: Completed and Verified
**Date**: August 31, 2026

---

## 1. Objective

The objective of Milestone 13.3 is to seamlessly integrate OpenStreetMap (OSM) road network data (ingested via M13.1 parser or acquired live via M13.2 Overpass client) into Q-Route's canonical `TransportGraph` abstraction, enabling real-world geographic road networks to enter the standard pathfinding, VRP modeling, and optimization pipeline without altering core optimization or objective logic.

---

## 2. Existing Architecture Inspected

Prior to implementation, the existing Q-Route architecture across graph modeling, pathfinding, VRP formulation, and optimization was inspected:

1. **`TransportGraph` (`backend/app/graph/model.py`)**:
   - Directed graph wrapping `networkx.DiGraph`.
   - Canonical node structure: `node_type` (`"intersection"`, `"depot"`, `"customer"`), spatial coordinates `x` and `y`, plus arbitrary keyword attributes.
   - Canonical edge structure: `distance` (km), `base_travel_time` (minutes), `congestion_factor` ($\ge 1.0$), `road_status` (`"open"` or `"closed"`).
   - Serialisation / Deserialisation: `to_dict()` and `from_dict()` methods.

2. **Graph Pathfinding (`backend/app/graph/pathfinding.py`)**:
   - `shortest_path(tg, source, target, weight_config)` computes weighted Dijkstra shortest paths over open subgraphs using the canonical scalar cost formula:
     $$\text{cost} = w_T \cdot (\text{base\_travel\_time} \cdot \text{congestion\_factor}) + w_D \cdot \text{distance} + w_C \cdot (\text{congestion\_factor} - 1.0)$$

3. **VRP Problem Formulation (`backend/app/vrp/models.py`, `backend/app/vrp/generator.py`)**:
   - `VRPProblem` encapsulates `graph: TransportGraph`, `vehicles: list[Vehicle]`, and `customers: list[Customer]`.
   - `generate_vrp_instance(graph=tg, ...)` accepts pre-built `TransportGraph` instances directly, allowing OSM road graphs to effortlessly generate valid VRP problems.

4. **Optimization Pipeline (`backend/app/qpso/*`, `backend/app/vrp/objective.py`, `backend/app/vrp/feasibility.py`)**:
   - QPSO, feasibility checking, and fitness evaluation depend exclusively on `VRPProblem.graph` and the `TransportGraph` interface without coupling to graph generation sources.

---

## 3. OSM → TransportGraph Mapping Specification

The integration adapter (`osm_to_transport_graph`) provides the canonical translation layer:

| OSM Element / Tag | Q-Route TransportGraph Attribute | Format / Units | Description |
|---|---|---|---|
| **OSM Node ID** | `node.id` / `node["osm_id"]` | `str` / `int` | Unique node identifier |
| **Node Role** | `node["node_type"]` | `"intersection"` / `"depot"` / `"customer"` | Role in VRP graph (defaults to `"intersection"`) |
| **Node Longitude** | `node["x"]`, `node["lon"]` | `float` (degrees) | East-West spatial coordinate ($x = \text{longitude}$) |
| **Node Latitude** | `node["y"]`, `node["lat"]` | `float` (degrees) | North-South spatial coordinate ($y = \text{latitude}$) |
| **Road Segment** | Directed Edge `(u, v)` | `tuple[Any, Any]` | Directed road connection from node $u$ to node $v$ |
| **Segment Length** | `edge["distance"]` | `float` (km) | Geodesic distance calculated via Haversine formula |
| **Free-Flow Time** | `edge["base_travel_time"]` | `float` (minutes) | Derived as $(\text{distance\_km} / \text{speed\_kmh}) \times 60.0$ |
| **Congestion Multiplier** | `edge["congestion_factor"]` | `float` | Initialized to `1.0` (uncongested free flow) |
| **Road Availability** | `edge["road_status"]` | `"open"` / `"closed"` | Initialized to `"open"` for valid drivable roads |
| **OSM Metadata** | `osm_way_id`, `highway`, `name`, `speed_kmh`, `oneway` | Various | Retained on edges for telemetry without coupling solver |

### Directionality Handling
- **Bidirectional Roads** (`oneway=no`, `0`, `false`, or omitted for standard roads): Create two directed edges $(u, v)$ and $(v, u)$ sharing identical metric attributes.
- **One-Way Roads** (`oneway=yes`, `1`, `true`, roundabouts, motorways): Create only the forward directed edge $(u, v)$.
- **Reverse One-Way Roads** (`oneway=-1`, `reverse`): Create only the reverse directed edge $(v, u)$.

---

## 4. Deterministic Behavior & Backward Compatibility

1. **Determinism**: The adapter contains zero randomized logic. Given identical OSM input (XML, JSON, or normalized dictionary), `osm_to_transport_graph` produces identical node/edge ordering, floating-point coordinates, and weight calculations.
2. **Backward Compatibility**: Existing synthetic network generation (`generate_synthetic_network`, `build_transport_graph`) and synthetic VRP generation remain 100% untouched and functional.

---

## 5. Verification Results

### A. M13 Focused Tests

All 37 tests across the M13 test suite passed cleanly:
- `backend/tests/test_m13_osm_ingestion.py` (14/14 passed)
- `backend/tests/test_m13_osm_client.py` (14/14 passed)
- `backend/tests/test_m13_osm_integration.py` (9/9 passed)

### B. Full Backend Regression

```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\git\Q-Route\backend
collected 428 items

tests\test_analysis.py ...                                               [  0%]
tests\test_api.py ..........................                             [  6%]
tests\test_api_persistence.py ...                                        [  7%]
tests\test_benchmark_runner.py ........                                  [  9%]
tests\test_benchmarks.py ........                                        [ 11%]
tests\test_comparators.py ........                                       [ 13%]
tests\test_db.py ....                                                    [ 14%]
tests\test_graph.py ...........................................          [ 24%]
tests\test_incidents.py ................................................ [ 35%]
...........................................                              [ 45%]
tests\test_m12_incident_rerouting.py ......                              [ 46%]
tests\test_m13_osm_client.py ..............                              [ 50%]
tests\test_m13_osm_ingestion.py ..............                           [ 53%]
tests\test_m13_osm_integration.py .........                              [ 55%]
tests\test_qpso.py ..................................                    [ 63%]
tests\test_repair_and_2opt.py ...........................                [ 69%]
tests\test_routes.py ................................................... [ 81%]
..................                                                       [ 85%]
tests\test_traffic.py ...............                                    [ 89%]
tests\test_vrp.py ..............................................         [100%]

======================= 428 passed, 1 warning in 51.48s =======================
```

### C. Frontend Production Build

```text
> frontend@0.0.0 build
> vite build

✓ 645 modules transformed.
dist/index.html                   1.08 kB │ gzip:   0.59 kB
dist/assets/index-LopClMwm.css   46.15 kB │ gzip:   8.20 kB
dist/assets/index-DAu9jxSO.js   722.16 kB │ gzip: 204.29 kB
✓ built in 10.49s
```

---

## 6. Protected Modules Verification

The following protected components were verified to be **completely unmodified**:
- `backend/app/qpso/*`
- `backend/app/vrp/objective.py`
- `backend/app/vrp/feasibility.py`
- `backend/app/incidents/rerouting.py`
- `backend/app/incidents/model.py`
- `backend/app/db/*`
- `frontend/*`
- `README.md`
