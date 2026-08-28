"""
Q-Route Backend – FastAPI application entry point.

Milestone 1: skeleton with health-check endpoint only.
Subsequent milestones will register routers from the sub-packages
(graph, vrp, qpso, traffic, incidents, routes).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Q-Route API",
    description=(
        "Smart logistics routing platform using Quantum Particle Swarm "
        "Optimisation (QPSO) for the Multi-Vehicle Vehicle Routing Problem."
    ),
    version="0.1.0",
)

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
# Health-check
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
