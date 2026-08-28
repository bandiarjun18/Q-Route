"""
app/routes/eta.py – ETA and travel-time calculation for Q-Route (Milestone 8).

Public API
----------
route_travel_time(tg, node_sequence)                        -> float
route_distance(tg, node_sequence)                           -> float
compute_eta(tg, node_sequence, elapsed_minutes=0.0)         -> float

Design notes
------------
- All numeric computation delegates to ``route_components()`` from
  app.vrp.objective.  That function is the single source of truth for
  edge-level travel-time and distance in Q-Route.  M8 does NOT reimplement
  this formula — doing so would violate the project-wide constraint against
  introducing a second fitness/cost formula.
- The ``congestion_factor`` on each edge reflects whatever the caller has
  applied via ``TrafficLayer.apply(tg)`` or ``IncidentLayer.apply(tg)``
  before querying these functions.  ETA therefore automatically reflects
  current conditions without any knowledge of the traffic or incident
  machinery.
- Route identity (node_sequence) and route cost (travel time) are explicitly
  separated: the route path never changes due to traffic; cost is recomputed
  on demand.
- All functions are pure: they read graph state, never mutate it.
- Returns ``math.inf`` if any edge on the path is closed or missing, which
  is the project-wide convention for impassable paths.
"""

from __future__ import annotations

import math
from typing import Any

from app.graph.model import TransportGraph
from app.vrp.objective import route_components


def route_travel_time(tg: TransportGraph, node_sequence: list[Any]) -> float:
    """
    Compute the congestion-aware total travel time for a node sequence.

    Delegates entirely to ``route_components(tg, node_sequence)`` and
    returns the ``travel_time`` component (sum of
    ``base_travel_time * congestion_factor`` over all edges).

    Parameters
    ----------
    tg            : TransportGraph – road network with current congestion factors.
    node_sequence : list           – ordered graph node ids.

    Returns
    -------
    float
        Total effective travel time in minutes.
        Returns ``math.inf`` if any edge in the sequence is closed or missing.

    Notes
    -----
    Re-querying after applying a new ``TrafficLayer`` or ``IncidentLayer``
    automatically reflects updated congestion without modifying the route.
    """
    travel_time, _distance, _congestion = route_components(tg, node_sequence)
    return travel_time


def route_distance(tg: TransportGraph, node_sequence: list[Any]) -> float:
    """
    Compute the total route distance for a node sequence.

    Delegates entirely to ``route_components(tg, node_sequence)`` and
    returns the ``distance`` component (sum of ``distance`` over all edges).

    Parameters
    ----------
    tg            : TransportGraph – road network.
    node_sequence : list           – ordered graph node ids.

    Returns
    -------
    float
        Total route distance in km.
        Returns ``math.inf`` if any edge in the sequence is closed or missing.
    """
    _travel_time, distance, _congestion = route_components(tg, node_sequence)
    return distance


def compute_eta(
    tg: TransportGraph,
    node_sequence: list[Any],
    elapsed_minutes: float = 0.0,
) -> float:
    """
    Compute the estimated remaining travel time (ETA) for a route.

    Formula::

        ETA = max(0.0, route_travel_time(tg, node_sequence) - elapsed_minutes)

    Parameters
    ----------
    tg              : TransportGraph – road network with current congestion.
    node_sequence   : list           – ordered graph node ids.
    elapsed_minutes : float          – minutes already elapsed on this route
                                       since departure (default 0.0).

    Returns
    -------
    float
        Estimated remaining travel time in minutes.  Always ≥ 0.0.
        Returns ``math.inf`` if any edge in the sequence is closed or missing.

    Notes
    -----
    - ``elapsed_minutes`` is caller-supplied.  A future milestone can derive
      this from actual wall-clock position along the route.
    - Re-querying after applying a new ``TrafficLayer`` automatically reflects
      updated congestion without changing the route path.
    - ETA is clamped to 0.0: it cannot be negative even when
      ``elapsed_minutes`` exceeds the total travel time (e.g. vehicle is
      already overdue).
    """
    total = route_travel_time(tg, node_sequence)
    if math.isinf(total):
        return total
    return max(0.0, total - elapsed_minutes)
