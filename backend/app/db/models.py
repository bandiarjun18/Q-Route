"""
app/db/models.py – SQLAlchemy ORM models for Q-Route.

Provides relational persistence for:
1. NetworkModel        – networks table (metadata and graph generation params)
2. NodeModel           – nodes table (spatial vertices and node types)
3. EdgeModel           – edges table (directed road links and congestion attributes)
4. FleetVehicleModel   – fleet_vehicles table (vehicle configurations & depots)
5. CustomerModel       – customers table (orders, delivery locations & demands)
6. OptimizationRunModel – optimization_runs table (QPSO execution records & convergence)
7. RouteModel          – routes table (active & historic vehicle delivery routes)
8. IncidentModel       – incidents table (road disruption registry & severities)
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


# Helper for dialect-agnostic JSON (JSONB on PostgreSQL, standard JSON elsewhere)
JsonColumn = JSON().with_variant(JSONB, "postgresql")


class NetworkModel(Base):
    """Stores transport network metadata and generation parameters."""

    __tablename__ = "networks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), default="Synthetic Network")
    n_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    n_edges: Mapped[int] = mapped_column(Integer, nullable=False)
    n_depots: Mapped[int] = mapped_column(Integer, nullable=False)
    n_customers: Mapped[int] = mapped_column(Integer, nullable=False)
    n_intersections: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    connect_radius_km: Mapped[float] = mapped_column(Float, nullable=False)
    grid_size_km: Mapped[float] = mapped_column(Float, nullable=False)
    closed_fraction: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    nodes: Mapped[List[NodeModel]] = relationship(
        "NodeModel", back_populates="network", cascade="all, delete-orphan"
    )
    edges: Mapped[List[EdgeModel]] = relationship(
        "EdgeModel", back_populates="network", cascade="all, delete-orphan"
    )
    fleet_vehicles: Mapped[List[FleetVehicleModel]] = relationship(
        "FleetVehicleModel", back_populates="network", cascade="all, delete-orphan"
    )
    customers: Mapped[List[CustomerModel]] = relationship(
        "CustomerModel", back_populates="network", cascade="all, delete-orphan"
    )
    optimization_runs: Mapped[List[OptimizationRunModel]] = relationship(
        "OptimizationRunModel", back_populates="network", cascade="all, delete-orphan"
    )
    incidents: Mapped[List[IncidentModel]] = relationship(
        "IncidentModel", back_populates="network", cascade="all, delete-orphan"
    )


class NodeModel(Base):
    """Stores spatial vertices for a network."""

    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)  # depot | customer | intersection
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="nodes")

    __table_args__ = (
        Index("ix_nodes_network_node_id", "network_id", "node_id"),
    )


class EdgeModel(Base):
    """Stores directed road segments."""

    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    u: Mapped[str] = mapped_column(String(64), nullable=False)
    v: Mapped[str] = mapped_column(String(64), nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    base_travel_time: Mapped[float] = mapped_column(Float, nullable=False)
    congestion_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    road_status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="edges")

    __table_args__ = (
        Index("ix_edges_network_u_v", "network_id", "u", "v"),
    )


class FleetVehicleModel(Base):
    """Stores vehicle configurations."""

    __tablename__ = "fleet_vehicles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    depot_node: Mapped[str] = mapped_column(String(64), nullable=False)

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="fleet_vehicles")


class CustomerModel(Base):
    """Stores customer delivery orders."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    location_node: Mapped[str] = mapped_column(String(64), nullable=False)
    demand: Mapped[float] = mapped_column(Float, nullable=False)

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="customers")


class OptimizationRunModel(Base):
    """Stores QPSO optimization execution results and convergence history."""

    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    n_particles: Mapped[int] = mapped_column(Integer, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    w_time: Mapped[float] = mapped_column(Float, default=1.0)
    w_distance: Mapped[float] = mapped_column(Float, default=0.5)
    w_congestion: Mapped[float] = mapped_column(Float, default=0.3)
    best_fitness: Mapped[float] = mapped_column(Float, nullable=False)
    is_feasible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    n_iterations_run: Mapped[int] = mapped_column(Integer, nullable=False)
    stopped_early: Mapped[bool] = mapped_column(Boolean, default=False)
    pre_repair_fitness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    post_repair_fitness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    convergence_history: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="optimization_runs")
    routes: Mapped[List[RouteModel]] = relationship(
        "RouteModel", back_populates="optimization_run", cascade="all, delete-orphan"
    )


class RouteModel(Base):
    """Stores active and historic vehicle routes."""

    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    optimization_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    depot_node: Mapped[str] = mapped_column(String(64), nullable=False)
    visit_order: Mapped[list[Any]] = mapped_column(JsonColumn, nullable=False)
    node_sequence: Mapped[list[Any]] = mapped_column(JsonColumn, nullable=False)
    total_distance: Mapped[float] = mapped_column(Float, nullable=False)
    total_travel_time: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_arrival: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    optimization_run: Mapped[OptimizationRunModel] = relationship(
        "OptimizationRunModel", back_populates="routes"
    )


class IncidentModel(Base):
    """Stores road disruption events and severities."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    optimization_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("optimization_runs.id", ondelete="SET NULL"), nullable=True
    )
    edge_u: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_v: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_closure: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    network: Mapped[NetworkModel] = relationship("NetworkModel", back_populates="incidents")
