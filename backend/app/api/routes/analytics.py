"""
app/api/routes/analytics.py – GET /analytics/convergence endpoint.

Returns the convergence history from the most recent QPSO optimization run.
The history is a non-increasing series of global-best fitness values, one
per iteration, suitable for Recharts in the M10 dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_optimization
from app.api.models import ConvergencePoint, ConvergenceResponse
from app.api.state import AppState

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/convergence",
    response_model=ConvergenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get QPSO convergence history",
    description=(
        "Returns the global-best fitness per iteration from the most recent "
        "QPSO run (including any post-incident re-optimization).  "
        "The history is non-increasing and is ready for Recharts.  "
        "Requires POST /optimize first."
    ),
)
def get_convergence(
    state: AppState = Depends(require_optimization),
) -> ConvergenceResponse:
    """
    Return convergence history from ``state.qpso_result.convergence_history``.

    The history dict maps ``iteration_index → global_best_fitness``.
    Returned sorted by iteration for deterministic JSON ordering.
    """
    result = state.qpso_result
    assert result is not None

    history_points = [
        ConvergencePoint(iteration=it, fitness=fit)
        for it, fit in sorted(result.convergence_history.items())
    ]

    return ConvergenceResponse(
        n_iterations=result.n_iterations_run,
        best_fitness=result.best_fitness,
        stopped_early=result.stopped_early,
        history=history_points,
    )
