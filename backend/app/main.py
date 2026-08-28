"""
Q-Route Backend – FastAPI application entry point.

Milestone 9: Exposes the M2–M8 stack through a REST API.

Routers registered
------------------
POST /network           – create synthetic transport network
POST /fleet             – configure vehicles and customers
POST /optimize          – run QPSO + repair + 2-opt optimization
POST /incidents         – register incident and re-optimize
GET  /routes/current    – retrieve active vehicle routes
GET  /analytics/convergence – QPSO convergence history

State
-----
``app.state.qroute`` is an ``AppState`` instance created via the lifespan
context manager and at module-load time as a fallback (for TestClient).
No module-level mutable state beyond this app instance is used.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analytics import router as analytics_router
from app.api.routes.current import router as current_router
from app.api.routes.fleet import router as fleet_router
from app.api.routes.incidents import router as incidents_router
from app.api.routes.network import router as network_router
from app.api.routes.optimize import router as optimize_router
from app.api.state import AppState


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise AppState before the first request; clean up on shutdown."""
    if not hasattr(application.state, "qroute") or application.state.qroute is None:
        application.state.qroute = AppState()
    yield
    # Shutdown: nothing to clean up for MVP state


app = FastAPI(
    title="Q-Route API",
    description=(
        "Smart logistics routing platform using Quantum Particle Swarm "
        "Optimisation (QPSO) for the Multi-Vehicle Vehicle Routing Problem.\n\n"
        "**API Flow:**\n"
        "1. `POST /network` – create network\n"
        "2. `POST /fleet` – configure vehicles & customers\n"
        "3. `POST /optimize` – run QPSO optimizer\n"
        "4. `GET /routes/current` – retrieve optimized routes\n"
        "5. `POST /incidents` – register incident & re-optimize\n"
        "6. `GET /routes/current` – updated routes\n"
        "7. `GET /analytics/convergence` – convergence history"
    ),
    version="0.9.0",
    lifespan=lifespan,
)

# Initialise AppState on app instance at module-load time (fallback for TestClient)
app.state.qroute = AppState()

# ---------------------------------------------------------------------------
# CORS – allow the Vite dev server (port 5173) to reach this API
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(network_router)
app.include_router(fleet_router)
app.include_router(optimize_router)
app.include_router(incidents_router)
app.include_router(current_router)
app.include_router(analytics_router)


# ---------------------------------------------------------------------------
# Health-check (unchanged from M1)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check() -> dict:
    """
    Returns a simple status payload so the frontend (and CI) can verify
    that the backend is running and reachable.
    """
    return {
        "status": "ok",
        "service": "Q-Route API",
        "version": app.version,
    }
