"""
app/api/models.py – Pydantic request and response models for the Q-Route API.

Design notes
------------
* Request models perform input validation via Pydantic field constraints.
  Domain-level validation (e.g. node id existence) is done in the endpoint.
* Response models are pure data-transfer objects — no domain logic lives here.
* ``model_config = ConfigDict(from_attributes=True)`` allows constructing
  response models from domain dataclass instances.
* All models use ``from __future__ import annotations`` so forward references
  resolve lazily (Pydantic v2 compatible).
* ``Any`` is used for ``vehicle_id`` / ``customer_id`` / ``node`` fields
  because the domain models allow any hashable type (int or str).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════════
# Network
# ═══════════════════════════════════════════════════════════════════════════

class NetworkRequest(BaseModel):
    """Parameters for POST /network — creates a synthetic transport network."""

    n_nodes: int = Field(20, ge=4, description="Total graph nodes (≥ 4)")
    n_depots: int = Field(1, ge=1, description="Number of depot nodes (≥ 1)")
    n_customers: int = Field(6, ge=1, description="Number of customer nodes (≥ 1)")
    connect_radius_km: float = Field(3.5, gt=0, description="Edge radius in km")
    grid_size_km: float = Field(10.0, gt=0, description="Grid side length in km")
    closed_fraction: float = Field(
        0.05, ge=0.0, le=1.0,
        description="Fraction of non-MST edges to close (0–1)",
    )
    seed: int = Field(42, description="Random seed for reproducibility")


class NodeOut(BaseModel):
    """A single graph node in the network response."""
    id: Any
    node_type: str
    x: float
    y: float


class EdgeOut(BaseModel):
    """A single directed edge in the network response."""
    u: Any
    v: Any
    distance: float
    base_travel_time: float
    congestion_factor: float
    road_status: str


class NetworkResponse(BaseModel):
    """Response from POST /network."""
    n_nodes: int
    n_edges: int
    n_depots: int
    n_customers: int
    n_intersections: int
    seed: int
    nodes: list[NodeOut]
    edges: list[EdgeOut]


# ═══════════════════════════════════════════════════════════════════════════
# Fleet
# ═══════════════════════════════════════════════════════════════════════════

class VehicleIn(BaseModel):
    """Configuration for one vehicle in POST /fleet."""
    vehicle_id: Any = Field(..., description="Unique vehicle identifier")
    capacity: float = Field(..., gt=0, description="Maximum load capacity (> 0)")
    depot_node: Any = Field(..., description="Home depot graph node id")


class CustomerIn(BaseModel):
    """One customer/delivery order in POST /fleet."""
    customer_id: Any = Field(..., description="Unique customer identifier")
    location_node: Any = Field(..., description="Delivery graph node id")
    demand: float = Field(..., ge=0, description="Demand units (≥ 0)")


class FleetRequest(BaseModel):
    """Parameters for POST /fleet — configures vehicles and customers."""
    vehicles: list[VehicleIn] = Field(..., min_length=1)
    customers: list[CustomerIn] = Field(..., min_length=1)


class FleetResponse(BaseModel):
    """Response from POST /fleet."""
    n_vehicles: int
    n_customers: int
    vehicles: list[VehicleIn]
    customers: list[CustomerIn]


# ═══════════════════════════════════════════════════════════════════════════
# Optimize
# ═══════════════════════════════════════════════════════════════════════════

class OptimizeRequest(BaseModel):
    """Parameters for POST /optimize — configures and runs the QPSO optimizer."""
    n_particles: int = Field(20, ge=2, description="Swarm size (≥ 2)")
    max_iterations: int = Field(100, ge=1, description="Maximum iterations (≥ 1)")
    time_budget_seconds: Optional[float] = Field(
        None, gt=0, description="Wall-clock time limit in seconds"
    )
    seed: int = Field(42, description="QPSO random seed")
    w_time: float = Field(1.0, gt=0, description="Travel-time weight")
    w_distance: float = Field(0.5, gt=0, description="Distance weight")
    w_congestion: float = Field(0.3, ge=0, description="Congestion penalty weight")


class RouteOut(BaseModel):
    """Serialisable representation of one vehicle's active route."""
    vehicle_id: Any
    depot_node: Any
    visit_order: list[Any]
    node_sequence: list[Any]
    total_distance: float
    total_travel_time: float
    estimated_arrival: Optional[float]


class FitnessBreakdown(BaseModel):
    """Objective function component breakdown from the best solution."""
    best_fitness: float
    pre_repair_fitness: Optional[float]
    post_repair_fitness: Optional[float]


class OptimizeResponse(BaseModel):
    """Response from POST /optimize."""
    best_fitness: float
    is_feasible: bool
    n_iterations_run: int
    stopped_early: bool
    pre_repair_fitness: Optional[float]
    post_repair_fitness: Optional[float]
    n_routes: int
    routes: list[RouteOut]


# ═══════════════════════════════════════════════════════════════════════════
# Incidents
# ═══════════════════════════════════════════════════════════════════════════

class IncidentRequest(BaseModel):
    """Parameters for POST /incidents — registers a road incident."""
    edge_u: Any = Field(..., description="Start node of the directed edge")
    edge_v: Any = Field(..., description="End node of the directed edge")
    incident_type: str = Field(
        ...,
        description="One of: ACCIDENT, ROAD_CLOSURE, CONSTRUCTION, OBSTRUCTION",
    )
    severity: str = Field(
        "LOW",
        description="One of: NONE, LOW, MEDIUM, HIGH, CRITICAL",
    )
    description: str = Field("", description="Optional free-text incident note")

    @field_validator("incident_type")
    @classmethod
    def validate_incident_type(cls, v: str) -> str:
        valid = {"ACCIDENT", "ROAD_CLOSURE", "CONSTRUCTION", "OBSTRUCTION"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(
                f"incident_type must be one of {sorted(valid)}, got {v!r}"
            )
        return upper

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid = {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(
                f"severity must be one of {sorted(valid)}, got {v!r}"
            )
        return upper


class IncidentResponse(BaseModel):
    """Response from POST /incidents."""
    edge_u: Any
    edge_v: Any
    incident_type: str
    severity: str
    is_closure: bool
    affected_vehicle_ids: list[Any]
    n_affected: int
    updated_routes: list[RouteOut]
    unaffected_route_count: int


# ═══════════════════════════════════════════════════════════════════════════
# Routes current
# ═══════════════════════════════════════════════════════════════════════════

class RoutesResponse(BaseModel):
    """Response from GET /routes/current."""
    total_active: int
    routes: list[RouteOut]


# ═══════════════════════════════════════════════════════════════════════════
# Analytics / convergence
# ═══════════════════════════════════════════════════════════════════════════

class ConvergencePoint(BaseModel):
    """One data point in a convergence history."""
    iteration: int
    fitness: float


class ConvergenceResponse(BaseModel):
    """Response from GET /analytics/convergence."""
    n_iterations: int
    best_fitness: float
    stopped_early: bool
    history: list[ConvergencePoint]
