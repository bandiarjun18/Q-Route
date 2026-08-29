"""
app/api/state.py – Application-level state container for Q-Route M9 API.

Design
------
``AppState`` is a plain dataclass stored on ``app.state.qroute`` at startup.
This is FastAPI's recommended pattern for request-lifetime-independent shared
state:

    app = FastAPI(...)
    app.state.qroute = AppState()

    @router.post("/network")
    def create_network(request: Request):
        state: AppState = request.app.state.qroute
        state.graph = ...

Key properties
--------------
* One dataclass field per layer of the Q-Route pipeline.
* All fields default to ``None`` (nothing is initialised at startup).
* ``clear_downstream(from_stage)`` resets all fields that would be
  invalidated by a new value at the given stage.  This keeps the state
  consistent without requiring callers to remember the dependency order.
* No singletons, no module-level mutable state, no global variables.
* Multiple independent ``AppState`` instances can coexist in tests.

Dependency order (each stage invalidates all later stages):
    graph → problem → qpso_result / route_manager → incident_layer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.graph.model import TransportGraph
    from app.incidents.model import IncidentLayer
    from app.qpso.optimizer import QPSOResult
    from app.routes.manager import RouteManager
    from app.vrp.models import VRPProblem


@dataclass
class AppState:
    """
    Per-application state for the Q-Route API (Milestone 9).

    All fields default to None; endpoints populate them in order:

        POST /network   →  graph, network_meta
        POST /fleet     →  problem
        POST /optimize  →  qpso_result, route_manager, last_qpso_config
        POST /incidents →  incident_layer (+ updates qpso_result, route_manager)

    Attributes
    ----------
    graph             : TransportGraph | None   – live road network.
    network_meta      : dict | None             – serialisable metadata from
                                                  the last /network call.
    problem           : VRPProblem | None       – fleet + customer VRP instance.
    qpso_result       : QPSOResult | None       – output of the most recent
                                                  QPSO optimisation run.
    route_manager     : RouteManager | None     – active-route registry built
                                                  from qpso_result.
    incident_layer    : IncidentLayer | None    – accumulated incident registry.
    last_qpso_config  : dict | None             – raw config params used in
                                                  the last optimize call, so
                                                  POST /incidents can re-run
                                                  with the same config.
    """

    graph: Optional[TransportGraph] = None
    network_meta: Optional[dict[str, Any]] = None
    network_db_id: Optional[str] = None
    problem: Optional[VRPProblem] = None
    qpso_result: Optional[QPSOResult] = None
    opt_run_db_id: Optional[str] = None
    route_manager: Optional[RouteManager] = None
    incident_layer: Optional[IncidentLayer] = None
    last_qpso_config: Optional[dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Invalidation helpers
    # ------------------------------------------------------------------

    def clear_from_network(self) -> None:
        """Reset all fields that depend on graph state."""
        self.network_meta = None
        self.network_db_id = None
        self.problem = None
        self.qpso_result = None
        self.opt_run_db_id = None
        self.route_manager = None
        self.incident_layer = None
        self.last_qpso_config = None

    def clear_from_fleet(self) -> None:
        """Reset all fields that depend on fleet/problem state."""
        self.problem = None
        self.qpso_result = None
        self.opt_run_db_id = None
        self.route_manager = None
        self.incident_layer = None
        self.last_qpso_config = None

    def clear_from_optimize(self) -> None:
        """Reset optimization and incident state."""
        self.qpso_result = None
        self.opt_run_db_id = None
        self.route_manager = None
        self.incident_layer = None
        self.last_qpso_config = None

