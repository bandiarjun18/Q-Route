"""
app/api/dependencies.py – FastAPI dependency functions for Q-Route M9 API.

Provides typed dependency-injection functions that:
1. Extract ``AppState`` from ``request.app.state.qroute``.
2. Guard endpoints against being called before required state exists,
   returning HTTP 409 Conflict with a clear message.

Usage in endpoints::

    @router.post("/fleet")
    def create_fleet(
        body: FleetRequest,
        state: AppState = Depends(require_graph),
    ):
        # state.graph is guaranteed non-None here
        ...

HTTP status choices
-------------------
- **409 Conflict** for "required prior step not completed" errors.
  This accurately represents that the resource (optimization, network, etc.)
  has not yet been created — the request conflicts with the server's current
  state.  A 412 Precondition Failed would be equally valid but 409 is more
  widely understood for API sequencing errors.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.api.state import AppState


# ---------------------------------------------------------------------------
# Base accessor
# ---------------------------------------------------------------------------

def get_state(request: Request) -> AppState:
    """Extract AppState from the FastAPI app state."""
    if not hasattr(request.app.state, "qroute") or request.app.state.qroute is None:
        request.app.state.qroute = AppState()
    return request.app.state.qroute  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Guarded accessors
# ---------------------------------------------------------------------------

def require_graph(state: AppState = Depends(get_state)) -> AppState:
    """
    Return state, or raise HTTP 409 if no network has been created yet.

    Used by: POST /fleet, POST /optimize, POST /incidents,
             GET /routes/current, GET /analytics/convergence.
    """
    if state.graph is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No network loaded. Call POST /network first to create or "
                "load a transportation network."
            ),
        )
    return state


def require_problem(state: AppState = Depends(require_graph)) -> AppState:
    """
    Return state, or raise HTTP 409 if no fleet has been configured yet.

    Used by: POST /optimize.
    """
    if state.problem is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No fleet configured. Call POST /fleet first to set up "
                "vehicles and customers."
            ),
        )
    return state


def require_optimization(state: AppState = Depends(require_problem)) -> AppState:
    """
    Return state, or raise HTTP 409 if optimization has not been run yet.

    Used by: POST /incidents, GET /routes/current, GET /analytics/convergence.
    """
    if state.qpso_result is None or state.route_manager is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No optimization result available. Call POST /optimize first."
            ),
        )
    return state
