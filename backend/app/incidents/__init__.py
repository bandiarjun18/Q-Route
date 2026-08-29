"""
app/incidents/__init__.py – Public API for the Q-Route incident / road-disruption layer.

Import from here rather than from sub-modules directly::

    from app.incidents import (
        IncidentType,
        IncidentSeverity,
        Incident,
        IncidentLayer,
    )

Milestone 7 – Incident / Road Disruption Layer
-----------------------------------------------
This module sits on top of the existing ``TrafficLayer`` architecture and
the ``TransportGraph`` without permanently modifying underlying graph data.

Key design choices
------------------
* ``IncidentType``     – enum of meaningful road disruption categories.
* ``IncidentSeverity`` – enum of impact levels with associated multipliers.
* ``Incident``         – immutable value object describing a single event on
                         a directed edge ``(u, v)``.
* ``IncidentLayer``    – per-edge incident registry; applies / removes
                         incidents via the existing ``congestion_factor`` and
                         ``road_status`` mechanisms — no new routing machinery
                         required.

No global mutable state is introduced.  Multiple independent
``IncidentLayer`` instances can coexist safely.
"""

from .model import IncidentType, IncidentSeverity, Incident, IncidentLayer
from .rerouting import detect_affected_routes, selective_reroute, RerouteResult

__all__ = [
    "IncidentType",
    "IncidentSeverity",
    "Incident",
    "IncidentLayer",
    "detect_affected_routes",
    "selective_reroute",
    "RerouteResult",
]
