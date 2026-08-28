"""
app/routes/__init__.py – Public API for the Q-Route route management layer.

Milestone 8: Route Management + ETA
------------------------------------
This package implements the operational route-management layer that sits above
the existing VRP/QPSO/traffic/incident stack.

Import from here rather than from sub-modules directly::

    from app.routes import RouteStatus, ActiveRoute
    from app.routes import RouteManager
    from app.routes import validate_route
    from app.routes import route_travel_time, route_distance, compute_eta

Architecture
------------
The flow this package enables:

    VRP/QPSO optimised solution
            ↓
    ActiveRoute.from_vehicle_route(vehicle_route, route_id)
            ↓
    RouteManager.register(active_route, tg)  ← validate + stamp metrics
            ↓
    Active vehicle routes
            ↓
    route_travel_time / route_distance / compute_eta  ← congestion-aware
            ↓
    Traffic / incident-aware route state

Key design choices
------------------
* ``RouteStatus``    – four-state enum: ACTIVE / COMPLETED / CANCELLED / AFFECTED.
* ``ActiveRoute``    – operational entity, separate from VRP's ``VehicleRoute``.
* ``RouteManager``   – independent, non-singleton registry; no global state.
* ``validate_route`` – pure graph-validity checker (no graph mutation).
* ETA functions      – delegate to ``route_components()``; no new formula.

No global mutable state is introduced anywhere in this package.
Multiple independent ``RouteManager`` instances can coexist safely.
"""

from .model import RouteStatus, ActiveRoute
from .validation import validate_route
from .eta import route_travel_time, route_distance, compute_eta
from .manager import RouteManager

__all__ = [
    # Model
    "RouteStatus",
    "ActiveRoute",
    # Validation
    "validate_route",
    # ETA / travel-time
    "route_travel_time",
    "route_distance",
    "compute_eta",
    # Manager
    "RouteManager",
]
