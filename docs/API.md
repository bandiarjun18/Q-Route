# Q-Route API Documentation

**Version:** 0.9.0
**Base URL (local dev):** `http://localhost:8000`
**Interactive docs:** `http://localhost:8000/docs` (Swagger UI)
**ReDoc:** `http://localhost:8000/redoc`

---

## Overview

The Q-Route API exposes a QPSO-powered multi-vehicle routing optimizer through six REST endpoints. Endpoints must be called in a specific order because each stage builds on the previous one.

### Required Call Order

```
POST /network          → creates the road network
      ↓
POST /fleet            → configures vehicles and customers
      ↓
POST /optimize         → runs QPSO + repair + 2-opt
      ↓
GET  /routes/current   → retrieves active routes
      ↓
POST /incidents        → registers incident, re-optimizes
      ↓
GET  /routes/current   → updated routes
      ↓
GET  /analytics/convergence  → QPSO convergence history
```

Calling an endpoint before its prerequisites returns **HTTP 409 Conflict**.

---

## Endpoints

---

### GET /health

**Purpose:** Verify the backend is running.

**Request:** None

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "Q-Route API",
  "version": "0.9.0"
}
```

---

### POST /network

**Purpose:** Generate a synthetic transport network using the M2 graph generator.
Replaces any existing network and clears all downstream state.

**Request body:**
```json
{
  "n_nodes": 20,
  "n_depots": 1,
  "n_customers": 6,
  "connect_radius_km": 3.5,
  "grid_size_km": 10.0,
  "closed_fraction": 0.05,
  "seed": 42
}
```

| Field | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `n_nodes` | int | ≥ 4 | 20 | Total graph nodes |
| `n_depots` | int | ≥ 1 | 1 | Depot nodes |
| `n_customers` | int | ≥ 1 | 6 | Customer nodes |
| `connect_radius_km` | float | > 0 | 3.5 | Edge radius (km) |
| `grid_size_km` | float | > 0 | 10.0 | Grid side length (km) |
| `closed_fraction` | float | 0–1 | 0.05 | Fraction of edges to close |
| `seed` | int | — | 42 | Random seed |

**Response (200 OK):**
```json
{
  "n_nodes": 20,
  "n_edges": 74,
  "n_depots": 1,
  "n_customers": 6,
  "n_intersections": 13,
  "seed": 42,
  "nodes": [
    { "id": 0, "node_type": "depot", "x": 4.17, "y": 7.20 },
    { "id": 1, "node_type": "customer", "x": 0.01, "y": 3.02 }
  ],
  "edges": [
    {
      "u": 0, "v": 1,
      "distance": 4.32,
      "base_travel_time": 8.65,
      "congestion_factor": 1.0,
      "road_status": "open"
    }
  ]
}
```

**Errors:**
| Code | Reason |
|---|---|
| 422 | Invalid field value (e.g. n_nodes < 4, closed_fraction > 1) |

---

### POST /fleet

**Purpose:** Configure vehicles and customer delivery orders.
All node IDs are validated against the loaded network.

**Requires:** `POST /network`

**Request body:**
```json
{
  "vehicles": [
    { "vehicle_id": 0, "capacity": 50.0, "depot_node": 0 },
    { "vehicle_id": 1, "capacity": 50.0, "depot_node": 0 }
  ],
  "customers": [
    { "customer_id": 0, "location_node": 3, "demand": 8.5 },
    { "customer_id": 1, "location_node": 7, "demand": 6.0 },
    { "customer_id": 2, "location_node": 11, "demand": 4.2 }
  ]
}
```

| Field | Constraints | Description |
|---|---|---|
| `vehicles` | ≥ 1 item | List of vehicle configurations |
| `capacity` | > 0 | Maximum load |
| `depot_node` | must exist in graph | Home depot node ID |
| `customers` | ≥ 1 item | List of delivery orders |
| `demand` | ≥ 0 | Delivery demand |
| `location_node` | must exist in graph | Delivery node ID |

**Response (200 OK):**
```json
{
  "n_vehicles": 2,
  "n_customers": 3,
  "vehicles": [...],
  "customers": [...]
}
```

**Errors:**
| Code | Reason |
|---|---|
| 409 | Network not created yet |
| 400 | `depot_node` or `location_node` not in graph |
| 422 | `capacity` ≤ 0 or `demand` < 0 |

---

### POST /optimize

**Purpose:** Run the QPSO + capacity-repair + 2-opt optimization pipeline.
Returns optimized vehicle routes, ETA data, and objective breakdown.

**Requires:** `POST /network`, `POST /fleet`

**Request body:**
```json
{
  "n_particles": 20,
  "max_iterations": 100,
  "time_budget_seconds": null,
  "seed": 42,
  "w_time": 1.0,
  "w_distance": 0.5,
  "w_congestion": 0.3
}
```

| Field | Constraints | Default | Description |
|---|---|---|---|
| `n_particles` | ≥ 2 | 20 | Swarm size |
| `max_iterations` | ≥ 1 | 100 | Max iterations |
| `time_budget_seconds` | > 0 or null | null | Wall-clock limit |
| `seed` | — | 42 | RNG seed |
| `w_time` | > 0 | 1.0 | Travel-time weight |
| `w_distance` | > 0 | 0.5 | Distance weight |
| `w_congestion` | ≥ 0 | 0.3 | Congestion penalty weight |

**Response (200 OK):**
```json
{
  "best_fitness": 142.7,
  "is_feasible": true,
  "n_iterations_run": 100,
  "stopped_early": false,
  "pre_repair_fitness": 198.3,
  "post_repair_fitness": 155.1,
  "n_routes": 2,
  "routes": [
    {
      "vehicle_id": 0,
      "depot_node": 0,
      "visit_order": [2, 5],
      "node_sequence": [0, 3, 2, 8, 5, 0],
      "total_distance": 28.4,
      "total_travel_time": 52.1,
      "estimated_arrival": null
    }
  ]
}
```

**Errors:**
| Code | Reason |
|---|---|
| 409 | Network or fleet not configured |
| 422 | Invalid optimizer parameters |

---

### POST /incidents

**Purpose:** Register a road incident on a directed edge, apply it to the graph,
and re-optimize to find updated routes for affected vehicles.

**Requires:** `POST /optimize`

**Request body:**
```json
{
  "edge_u": 3,
  "edge_v": 7,
  "incident_type": "ACCIDENT",
  "severity": "MEDIUM",
  "description": "Multi-vehicle collision on main road"
}
```

| Field | Valid values | Description |
|---|---|---|
| `edge_u`, `edge_v` | existing graph node IDs | Directed edge endpoints |
| `incident_type` | `ACCIDENT`, `ROAD_CLOSURE`, `CONSTRUCTION`, `OBSTRUCTION` | Category |
| `severity` | `NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | Impact level |
| `description` | any string | Optional free-text note |

**Congestion multipliers by severity:**
| Severity | Multiplier |
|---|---|
| NONE | ×1.0 |
| LOW | ×1.2 |
| MEDIUM | ×1.5 |
| HIGH | ×2.0 |
| CRITICAL | ×3.0 |

A `ROAD_CLOSURE` incident closes the edge regardless of severity.

**Response (200 OK):**
```json
{
  "edge_u": 3,
  "edge_v": 7,
  "incident_type": "ACCIDENT",
  "severity": "MEDIUM",
  "is_closure": false,
  "affected_vehicle_ids": [0],
  "n_affected": 1,
  "updated_routes": [
    {
      "vehicle_id": 0,
      "depot_node": 0,
      "visit_order": [2, 5],
      "node_sequence": [0, 2, 8, 5, 0],
      "total_distance": 31.2,
      "total_travel_time": 67.8,
      "estimated_arrival": null
    }
  ],
  "unaffected_route_count": 1
}
```

**Notes:**
- Vehicles not using the incident edge keep their original routes.
- `updated_routes` contains only the re-optimized routes for affected vehicles.
- `unaffected_route_count` is the number of routes that were not affected.

**Errors:**
| Code | Reason |
|---|---|
| 409 | Optimization not run yet |
| 400 | Edge `(edge_u, edge_v)` not in graph |
| 422 | Invalid `incident_type` or `severity` string |

---

### GET /routes/current

**Purpose:** Return all currently active vehicle routes.

**Requires:** `POST /optimize`

**Response (200 OK):**
```json
{
  "total_active": 2,
  "routes": [
    {
      "vehicle_id": 0,
      "depot_node": 0,
      "visit_order": [2, 5],
      "node_sequence": [0, 3, 2, 8, 5, 0],
      "total_distance": 28.4,
      "total_travel_time": 52.1,
      "estimated_arrival": null
    },
    {
      "vehicle_id": 1,
      "depot_node": 0,
      "visit_order": [1, 4],
      "node_sequence": [0, 1, 7, 4, 0],
      "total_distance": 24.8,
      "total_travel_time": 45.3,
      "estimated_arrival": null
    }
  ]
}
```

**Notes:**
- Routes with status `ACTIVE` or `AFFECTED` are included.
- Routes with terminal status (`COMPLETED`, `CANCELLED`) are excluded.
- `estimated_arrival` is minutes remaining (float) or `null` if not computed.

**Errors:**
| Code | Reason |
|---|---|
| 409 | Optimization not run yet |

---

### GET /analytics/convergence

**Purpose:** Return QPSO convergence history from the most recent optimization run.
The history is non-increasing (minimization) and is ready for Recharts.

**Requires:** `POST /optimize`

**Response (200 OK):**
```json
{
  "n_iterations": 100,
  "best_fitness": 142.7,
  "stopped_early": false,
  "history": [
    { "iteration": 0, "fitness": 320.5 },
    { "iteration": 1, "fitness": 298.1 },
    { "iteration": 2, "fitness": 275.4 },
    "...",
    { "iteration": 99, "fitness": 142.7 }
  ]
}
```

**Notes:**
- `history` is sorted by `iteration` in ascending order.
- `best_fitness` always equals `history[-1].fitness`.
- After `POST /incidents`, this reflects the re-optimization history.

**Errors:**
| Code | Reason |
|---|---|
| 409 | Optimization not run yet |

---

## Error Response Format

All error responses follow FastAPI's default format:

```json
{
  "detail": "Descriptive error message"
}
```

Validation errors (422) follow Pydantic's format:
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "n_nodes"],
      "msg": "Input should be greater than or equal to 4",
      "input": 2
    }
  ]
}
```

---

## Manual Testing via Swagger UI

1. Start the backend:
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

2. Open **http://localhost:8000/docs** in your browser.

3. Use the Swagger UI to call endpoints in order:
   - Click **POST /network** → **Try it out** → **Execute**
   - Click **POST /fleet** → paste vehicle/customer node IDs from the network response
   - Click **POST /optimize** → Execute
   - Click **GET /routes/current** → Execute
   - Click **POST /incidents** → paste a valid edge from the network response
   - Click **GET /analytics/convergence** → Execute

> The Swagger UI persists your last request bodies between calls, making it easy to copy node IDs from the `/network` response into the `/fleet` body.

---

## Running Tests

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/test_api.py -v
```

To run the full test suite (all milestones):
```bash
.venv\Scripts\python.exe -m pytest -q
```
