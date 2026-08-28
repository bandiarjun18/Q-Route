"""
app/routes/model.py – Route data model for Q-Route (Milestone 8).

Defines:
  RouteStatus  – operational state enum for an active route.
  ActiveRoute  – operational representation of a vehicle route, separate
                 from the VRP planning layer's VehicleRoute.

Design notes
------------
- ActiveRoute is the operational counterpart to VehicleRoute.  VehicleRoute
  belongs to the VRP/QPSO planning layer; ActiveRoute belongs to the route-
  management layer.  They have different lifecycles and must not be merged.
- RouteManager computes and stamps total_distance and total_travel_time at
  registration time.  Both may be re-stamped later via RouteManager.update()
  when traffic conditions change.
- estimated_arrival is minutes-from-now (float | None), consistent with the
  project-wide time unit (minutes throughout graph, VRP, traffic layers).
- from_vehicle_route() is a convenience factory for the QPSO → RouteManager
  handoff; it does not modify or couple the VRP layer in any way.
- No module-level mutable state exists anywhere in this file.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # VehicleRoute is only referenced in the type annotation of
    # from_vehicle_route(); TYPE_CHECKING keeps the import cost-free at
    # runtime while giving type checkers full resolution.
    from app.vrp.models import VehicleRoute


# ---------------------------------------------------------------------------
# Route status enum
# ---------------------------------------------------------------------------

class RouteStatus(enum.Enum):
    """
    Operational status of an active vehicle route.

    Members
    -------
    ACTIVE    – route is currently being executed by the vehicle.
    COMPLETED – vehicle has finished all deliveries and returned to depot.
    CANCELLED – route was cancelled before execution began.
    AFFECTED  – at least one edge on the route has a registered incident;
                route is still in use but may require re-optimisation.

    Notes
    -----
    - ``ACTIVE`` and ``AFFECTED`` are treated as "live" by ``RouteManager``;
      ``COMPLETED`` and ``CANCELLED`` are terminal.
    - ``AFFECTED`` deliberately does not trigger automatic re-optimisation —
      that is a future milestone.  It serves as a flag so operators can
      identify which routes need attention.
    """

    ACTIVE    = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AFFECTED  = "affected"


# ---------------------------------------------------------------------------
# Active route dataclass
# ---------------------------------------------------------------------------

@dataclass
class ActiveRoute:
    """
    Operational representation of a vehicle's active route.

    This is the M8 route-management layer's primary entity.  It augments
    the VRP planner's ``VehicleRoute`` with an operational ``route_id``,
    a mutable ``status``, pre-computed distance and travel-time metrics,
    and an optional ETA.

    Attributes
    ----------
    route_id          : str              – unique identifier for this route
                                          instance (e.g. "V1-20260829-001").
                                          Must be unique within a RouteManager.
    vehicle_id        : any              – matches ``Vehicle.vehicle_id``.
    depot_node        : any              – home depot graph node id.
    visit_order       : list             – ordered ``customer_id`` values this
                                          vehicle is scheduled to serve.
    node_sequence     : list             – full graph path including depot at
                                          index [0] and [-1].
    status            : RouteStatus      – current operational status
                                          (default: ACTIVE).
    total_distance    : float            – total route distance in km; stamped
                                          by ``RouteManager.register()``.
    total_travel_time : float            – congestion-aware travel time in
                                          minutes; stamped by ``register()``.
    estimated_arrival : float | None     – minutes remaining from now (ETA);
                                          ``None`` until explicitly set.

    Notes
    -----
    - Capacity and demand fields are deliberately excluded — they are planning
      concerns that belong to the VRP layer (``Vehicle``, ``Customer``).
    - ``vehicle_id``, ``visit_order``, and ``node_sequence`` mirror the
      corresponding fields in ``VehicleRoute``.
    - ``RouteManager.update()`` enforces that the structural identity fields
      (``route_id``, ``vehicle_id``, ``node_sequence``, ``depot_node``,
      ``visit_order``) cannot be modified after registration.
    """

    route_id: str
    vehicle_id: Any
    depot_node: Any
    visit_order: list = field(default_factory=list)
    node_sequence: list = field(default_factory=list)
    status: RouteStatus = RouteStatus.ACTIVE
    total_distance: float = 0.0
    total_travel_time: float = 0.0
    estimated_arrival: float | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_vehicle_route(
        cls,
        vehicle_route: VehicleRoute,
        route_id: str,
    ) -> ActiveRoute:
        """
        Convenience factory: build an ``ActiveRoute`` from a ``VehicleRoute``.

        Copies ``vehicle_id``, ``depot_node``, ``visit_order``, and
        ``node_sequence`` from the VRP planner's output.  Metrics
        (``total_distance``, ``total_travel_time``) are zeroed and will be
        stamped when ``RouteManager.register()`` is called.

        Parameters
        ----------
        vehicle_route : VehicleRoute – output from the VRP planner / QPSO.
        route_id      : str          – unique identifier for this operational
                                       route instance.

        Returns
        -------
        ActiveRoute with status=ACTIVE and zeroed metrics.
        """
        return cls(
            route_id=route_id,
            vehicle_id=vehicle_route.vehicle_id,
            depot_node=vehicle_route.depot_node,
            visit_order=list(vehicle_route.visit_order),
            node_sequence=list(vehicle_route.node_sequence),
        )
