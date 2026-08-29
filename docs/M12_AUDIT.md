# Milestone 12 Audit: Incident-Aware Dynamic Selective Rerouting

---

## 1. Executive Summary

Milestone 12 delivers **Incident-Aware Dynamic Selective Rerouting** for Q-Route.

When unexpected road network disruptions occur (e.g. accidents, closures, construction, obstructions), Q-Route isolates only the vehicles whose planned paths intersect the disruption, preserving all unaffected vehicle routes intact. Only the affected vehicles are re-routed via QPSO on the updated graph, guaranteeing that all updated paths are graph-valid, avoid closed road segments, and respect vehicle capacity constraints.

---

## 2. Core Architecture & Modules

### 2.1 Rerouting Engine ([`backend/app/incidents/rerouting.py`](../backend/app/incidents/rerouting.py))
- **`detect_affected_routes(rm, incident_layer, graph)`**:
  - Traverses the consecutive directed edges `(u, v)` of each live route in `RouteManager`.
  - Classifies routes as **affected** if any edge has an active incident or has `road_status == 'closed'`.
  - Classifies all other active routes as **unaffected** (preserved).
- **`selective_reroute(graph, problem, rm, incident_layer, qpso_config)`**:
  - Ensures incidents are stamped on the transport graph.
  - Detects affected vehicle routes.
  - If no routes are affected, immediately returns a no-op result without running unnecessary optimization cycles.
  - Re-optimizes only affected vehicles using QPSO on the updated graph topology.
  - Validates newly generated paths (`validate_route`) to guarantee graph continuity and absence of closed edges.
  - Atomically replaces only the affected routes in `RouteManager`, keeping preserved routes 100% unaltered.
  - Computes global feasibility and multi-objective post-incident fitness.
- **`RerouteResult`**:
  - `affected_vehicle_ids: list[Any]`
  - `unaffected_vehicle_ids: list[Any]`
  - `updated_routes: list[ActiveRoute]`
  - `preserved_routes: list[ActiveRoute]`
  - `all_active_routes: list[ActiveRoute]`
  - `is_feasible: bool`
  - `post_incident_fitness: Optional[float]`

---

## 3. API & Database Integration

### 3.1 REST Endpoint (`POST /incidents`)
- Location: [`backend/app/api/routes/incidents.py`](../backend/app/api/routes/incidents.py)
- Ingests `IncidentRequest` (`edge_u`, `edge_v`, `incident_type`, `severity`, `description`).
- Invokes `selective_reroute` to isolate and update affected vehicle routes.
- Persists the incident event to the PostgreSQL `incidents` table with foreign key linkage to the active network and optimization run.
- Returns `IncidentResponse` with `affected_vehicle_ids`, `n_affected`, `updated_routes`, and `unaffected_route_count`.

---

## 4. Verification & Testing

### 4.1 Focused M12 Test Suite ([`backend/tests/test_m12_incident_rerouting.py`](../backend/tests/test_m12_incident_rerouting.py))
- `test_incident_validation`: Verifies rejection of self-loops and invalid types.
- `test_detect_affected_routes`: Verifies accurate partition into affected and unaffected routes.
- `test_selective_reroute_preserves_unaffected`: Proves unaffected vehicle routes remain 100% identical while affected vehicle is rerouted and avoids closed edges.
- `test_selective_reroute_no_overlap`: Fast no-op when disruption does not intersect active routes.
- `test_post_incidents_api_full_flow`: End-to-end API integration from network generation to incident re-routing.
- `test_incident_persistence_in_db`: Database persistence verification in PostgreSQL.
- **Result**: `6/6 passed` in 3.21s.

### 4.2 Full Regression Suite
- **Total Backend Tests**: 391 passed, 0 failed, 43.49s across all 16 test suites.
- **Frontend Production Build**: built successfully, 0 errors, 587ms.


---

## 5. Protected Invariance Checklist

| Item | Status | Confirmation |
|---|---|---|
| `backend/app/qpso/*` | **Untouched** | Core QPSO optimizer, particle wave function, and repair logic preserved |
| `backend/app/vrp/objective.py` | **Untouched** | Canonical fitness formula and weight definitions preserved |
| `backend/app/vrp/feasibility.py` | **Untouched** | Canonical feasibility checker preserved |
| `frontend/*` | **Untouched** | UI components and dashboards preserved |
| API Request/Response Schemas | **Compliant** | 100% backward compatible contracts |
| Database Layer | **Compatible** | Uses existing PostgreSQL 18 schema and session pooling |
| Dependencies | **Zero Added** | Uses existing verified dependencies |
