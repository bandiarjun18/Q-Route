"""
app/incidents/model.py – Incident / Road Disruption layer for Q-Route (Milestone 7).

Provides a clean, deterministic abstraction for road incidents that sits on
top of the existing ``TransportGraph`` and ``TrafficLayer`` without altering
base graph data or introducing global mutable state.

Public API
----------
IncidentType     – enum of road disruption categories
IncidentSeverity – enum of impact levels with multipliers
Incident         – immutable value object: one incident on one directed edge
IncidentLayer    – per-edge incident registry; apply / remove / query incidents

Design notes
------------
* ``IncidentType`` captures meaningful real-world categories — ``ACCIDENT``,
  ``ROAD_CLOSURE``, ``CONSTRUCTION``, ``OBSTRUCTION`` — as a proper enum
  rather than bare strings, which eliminates typo-class bugs and enables
  exhaustive matching.
* ``IncidentSeverity`` mirrors the ``TrafficState`` design: the enum *value*
  is the additional congestion multiplier applied on top of any existing
  traffic state::

      effective_congestion = base_congestion * IncidentSeverity.HIGH.value

  NONE is deliberately included (multiplier = 1.0) to express "incident
  present but not yet affecting travel time" — useful for monitoring /
  warning states.
* A ``ROAD_CLOSURE`` incident always results in ``road_status = "closed"``
  on the graph edge, which is the canonical representation throughout the
  project (graph model, pathfinding, VRP fitness all honour this flag).
  All other incident types modify only ``congestion_factor``, preserving the
  original base travel-time data.
* ``Incident`` is a frozen dataclass (immutable) — it cannot be mutated
  after creation.  The mutable registry is isolated to ``IncidentLayer``.
* ``IncidentLayer`` stores ``Incident`` objects keyed by ``(u, v)`` edge
  tuples.  One incident per directed edge is the current model; replacing
  an incident is explicit (add the new one, which overwrites the old).
* ``IncidentLayer.apply(tg)`` stamps each tracked edge:
  - Closure  → ``road_status = "closed"`` (edge becomes impassable)
  - Partial  → ``congestion_factor *= severity.value`` (travel time grows)
  Edges absent from the layer are left completely untouched.
* ``IncidentLayer.reset(tg)`` removes all incident effects by restoring
  ``road_status = "open"`` and ``congestion_factor`` to the pre-apply
  snapshot kept internally.  The underlying base_travel_time is never
  touched.
* No module-level mutable state exists anywhere in this file.

Extension points
----------------
* Time-bounded incidents (M8+): add ``start_time`` / ``end_time`` fields to
  ``Incident`` and filter in ``apply()``.
* Multi-incident-per-edge (M8+): change the storage to
  ``dict[edge, list[Incident]]`` and aggregate effects.
* Dynamic re-optimisation: rebuild ``IncidentLayer`` each time step and call
  ``apply(tg)`` before each QPSO run.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any

from app.graph.model import TransportGraph


# ---------------------------------------------------------------------------
# Incident type enum
# ---------------------------------------------------------------------------

class IncidentType(enum.Enum):
    """
    Categories of road disruption modelled by Q-Route.

    Members
    -------
    ACCIDENT      – vehicle collision; partial or full lane blockage.
    ROAD_CLOSURE  – entire road segment closed; edge becomes impassable.
    CONSTRUCTION  – roadworks; reduced speed, partial lane closure.
    OBSTRUCTION   – debris, fallen tree, broken-down vehicle, etc.
    """

    ACCIDENT      = "accident"
    ROAD_CLOSURE  = "road_closure"
    CONSTRUCTION  = "construction"
    OBSTRUCTION   = "obstruction"


# ---------------------------------------------------------------------------
# Incident severity enum
# ---------------------------------------------------------------------------

class IncidentSeverity(enum.Enum):
    """
    Impact levels for a road incident.

    The enum *value* is the additional congestion multiplier applied to the
    existing ``congestion_factor`` of an edge when an incident is active::

        new_congestion = existing_congestion * severity.value

    Levels
    ------
    NONE   : 1.0 – incident recorded but causes no travel-time increase.
    LOW    : 1.2 – minor disruption; 20 % longer than current conditions.
    MEDIUM : 1.5 – notable disruption; 50 % longer than current conditions.
    HIGH   : 2.0 – severe disruption; travel time doubles.
    CRITICAL: 3.0 – near-impassable; for extreme cases short of full closure.

    Note
    ----
    ``ROAD_CLOSURE``-type incidents always close the edge regardless of
    severity; severity still encodes how long the closure is expected to last
    (advisory metadata) but does not alter the routing behaviour further.
    """

    NONE     = 1.0
    LOW      = 1.2
    MEDIUM   = 1.5
    HIGH     = 2.0
    CRITICAL = 3.0


# ---------------------------------------------------------------------------
# Incident value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Incident:
    """
    Immutable description of a single road incident on a directed edge.

    Parameters
    ----------
    u, v      : any hashable – directed edge endpoints (same convention as
                ``TransportGraph.add_edge``).
    type      : IncidentType  – category of disruption.
    severity  : IncidentSeverity – impact level (default LOW).
    description : str – optional free-text note (for logging / UI display).

    Invariants
    ----------
    * ``u != v`` – self-loops are not meaningful road incidents.
    * ``severity`` must be an ``IncidentSeverity`` member.
    * ``type`` must be an ``IncidentType`` member.

    Examples
    --------
    >>> from app.incidents import Incident, IncidentType, IncidentSeverity
    >>> inc = Incident(u=0, v=1, type=IncidentType.ACCIDENT,
    ...                severity=IncidentSeverity.HIGH)
    >>> inc.is_closure
    False
    >>> inc.congestion_multiplier
    2.0
    """

    u: Any
    v: Any
    type: IncidentType
    severity: IncidentSeverity = IncidentSeverity.LOW
    description: str = ""

    # Post-init validation -------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.type, IncidentType):
            raise TypeError(
                f"Incident.type must be an IncidentType member, "
                f"got {type(self.type).__name__!r}."
            )
        if not isinstance(self.severity, IncidentSeverity):
            raise TypeError(
                f"Incident.severity must be an IncidentSeverity member, "
                f"got {type(self.severity).__name__!r}."
            )
        if self.u == self.v:
            raise ValueError(
                f"Incident edge endpoints must differ; got u=v={self.u!r}."
            )

    # Convenience properties -----------------------------------------------

    @property
    def edge(self) -> tuple[Any, Any]:
        """Return ``(u, v)`` as a tuple."""
        return (self.u, self.v)

    @property
    def is_closure(self) -> bool:
        """True iff the incident type is ``ROAD_CLOSURE``."""
        return self.type is IncidentType.ROAD_CLOSURE

    @property
    def congestion_multiplier(self) -> float:
        """
        The additional congestion multiplier introduced by this incident.

        For closures, this is still meaningful as a severity indicator, but
        the routing effect is handled through ``road_status``, not through
        ``congestion_factor``.
        """
        return self.severity.value


# ---------------------------------------------------------------------------
# Incident layer
# ---------------------------------------------------------------------------

@dataclass
class IncidentLayer:
    """
    Per-edge incident registry for a transport network.

    An ``IncidentLayer`` maps directed edges ``(u, v)`` to ``Incident``
    objects.  Edges absent from the registry are unaffected.

    One incident per directed edge is supported by the current model.
    Adding a new incident to an edge that already has one replaces the old
    incident (explicit override semantics).

    Instances are independent value objects — no shared or global state
    exists.  Multiple layers can be created independently.

    Construction
    ------------
    ``IncidentLayer()``                – empty layer
    ``IncidentLayer.from_incidents(incidents)`` – build from an iterable

    Applying to a graph
    -------------------
    ``layer.apply(tg)``
        Stamps each managed edge:

        * ``ROAD_CLOSURE`` → sets ``road_status = "closed"`` (impassable)
        * All other types  → multiplies ``congestion_factor`` by
          ``incident.severity.value``

        A snapshot of pre-apply values is stored internally so that ``reset``
        can restore them exactly.

    ``layer.reset(tg)``
        Restores every managed edge to its pre-apply state.
        Safe to call multiple times or when ``apply`` was never called.

    Attributes
    ----------
    _incidents : dict[tuple[Any, Any], Incident]
        Internal mapping of ``(u, v)`` → ``Incident``.  Use the public API.
    _snapshot  : dict[tuple[Any, Any], dict]
        Internal pre-apply snapshot of edge attributes.  Populated by
        ``apply()``, cleared by ``reset()``.
    """

    _incidents: dict[tuple[Any, Any], Incident] = field(
        default_factory=dict, repr=False
    )
    _snapshot: dict[tuple[Any, Any], dict] = field(
        default_factory=dict, repr=False
    )

    # ------------------------------------------------------------------
    # Construction factories
    # ------------------------------------------------------------------

    @classmethod
    def from_incidents(cls, incidents: list[Incident]) -> "IncidentLayer":
        """
        Build an ``IncidentLayer`` from a list of ``Incident`` objects.

        If the list contains multiple incidents for the same edge, the last
        one wins (list order).

        Parameters
        ----------
        incidents : list[Incident]

        Returns
        -------
        IncidentLayer
        """
        layer = cls()
        for inc in incidents:
            layer.add_incident(inc)
        return layer

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_incident(self, incident: Incident) -> None:
        """
        Register ``incident`` for its associated edge ``(u, v)``.

        If an incident already exists for that edge it is replaced.
        Call ``apply(tg)`` afterwards to propagate the change to the graph.

        Parameters
        ----------
        incident : Incident
        """
        self._incidents[incident.edge] = incident

    def remove_incident(self, u: Any, v: Any) -> None:
        """
        Deregister any incident on edge ``(u, v)``.

        This does **not** automatically restore graph edge attributes.
        Call ``reset(tg)`` or ``apply(tg)`` to propagate the change.

        Parameters
        ----------
        u, v : any hashable – edge endpoints

        Raises
        ------
        KeyError
            If no incident is registered for ``(u, v)``.
        """
        edge = (u, v)
        if edge not in self._incidents:
            raise KeyError(
                f"No incident registered for edge ({u!r}, {v!r})."
            )
        del self._incidents[edge]
        # Remove snapshot entry so reset won't attempt to restore a gone incident
        self._snapshot.pop(edge, None)

    # ------------------------------------------------------------------
    # Accessors / queries
    # ------------------------------------------------------------------

    def has_incident(self, u: Any, v: Any) -> bool:
        """
        Return True if an incident is registered for edge ``(u, v)``.

        Parameters
        ----------
        u, v : any hashable – edge endpoints
        """
        return (u, v) in self._incidents

    def get_incident(self, u: Any, v: Any) -> Incident | None:
        """
        Return the ``Incident`` registered for edge ``(u, v)``, or ``None``.

        Parameters
        ----------
        u, v : any hashable – edge endpoints

        Returns
        -------
        Incident | None
        """
        return self._incidents.get((u, v))

    def all_incidents(self) -> list[Incident]:
        """Return a list of all registered incidents (unordered)."""
        return list(self._incidents.values())

    # ------------------------------------------------------------------
    # Graph integration
    # ------------------------------------------------------------------

    def apply(self, tg: TransportGraph) -> None:
        """
        Stamp each tracked edge in ``tg`` with the incident's effects.

        For each registered incident whose edge exists in ``tg``:

        * A snapshot of the original ``congestion_factor`` and
          ``road_status`` is stored (overwriting any previous snapshot for
          that edge).
        * ``ROAD_CLOSURE`` → sets ``road_status = "closed"``.
        * All other types  → multiplies the current ``congestion_factor``
          by ``incident.severity.value``.

        Edges in the layer that are absent from ``tg`` are silently ignored.

        Parameters
        ----------
        tg : TransportGraph
        """
        g = tg.graph
        for edge, incident in self._incidents.items():
            u, v = edge
            if not g.has_edge(u, v):
                continue
            data = g[u][v]
            # Snapshot original values (only if not already snapshotted)
            if edge not in self._snapshot:
                self._snapshot[edge] = {
                    "congestion_factor": data["congestion_factor"],
                    "road_status":       data.get("road_status", TransportGraph.OPEN),
                }
            if incident.is_closure:
                data["road_status"] = TransportGraph.CLOSED
            else:
                data["congestion_factor"] = (
                    self._snapshot[edge]["congestion_factor"]
                    * incident.congestion_multiplier
                )

    def reset(self, tg: TransportGraph) -> None:
        """
        Restore every managed edge in ``tg`` to its pre-apply state.

        Reverses the effects of ``apply()``:

        * Reopens any closures (``road_status → "open"``).
        * Restores the original ``congestion_factor``.

        Safe to call multiple times or when ``apply`` was never called.
        If no snapshot exists for an edge (``apply`` was not called), the
        edge is left unchanged.

        Parameters
        ----------
        tg : TransportGraph
        """
        g = tg.graph
        for edge, snap in self._snapshot.items():
            u, v = edge
            if g.has_edge(u, v):
                g[u][v]["congestion_factor"] = snap["congestion_factor"]
                g[u][v]["road_status"]       = snap["road_status"]
        self._snapshot.clear()

    def reset_edge(self, tg: TransportGraph, u: Any, v: Any) -> None:
        """
        Restore only the edge ``(u, v)`` to its pre-apply state.

        Parameters
        ----------
        tg   : TransportGraph
        u, v : any hashable – edge endpoints

        Raises
        ------
        KeyError
            If no snapshot exists for ``(u, v)`` (i.e., apply was never
            called for this edge or reset has already been called).
        """
        edge = (u, v)
        if edge not in self._snapshot:
            raise KeyError(
                f"No snapshot for edge ({u!r}, {v!r}). "
                "Has apply() been called?"
            )
        g = tg.graph
        if g.has_edge(u, v):
            snap = self._snapshot[edge]
            g[u][v]["congestion_factor"] = snap["congestion_factor"]
            g[u][v]["road_status"]       = snap["road_status"]
        del self._snapshot[edge]

    # ------------------------------------------------------------------
    # Query helpers for routing integration
    # ------------------------------------------------------------------

    def effective_congestion(self, u: Any, v: Any, base_congestion: float = 1.0) -> float:
        """
        Return the effective congestion factor for edge ``(u, v)``
        incorporating any active incident, without mutating the graph.

        For closure incidents, returns ``math.inf`` to signal impassability.
        For partial incidents, returns ``base_congestion * severity.value``.
        If no incident is registered, returns ``base_congestion`` unchanged.

        Parameters
        ----------
        u, v            : any hashable – edge endpoints
        base_congestion : float – existing congestion factor from the graph
                          or ``TrafficLayer`` (default 1.0)

        Returns
        -------
        float
        """
        incident = self._incidents.get((u, v))
        if incident is None:
            return base_congestion
        if incident.is_closure:
            return math.inf
        return base_congestion * incident.congestion_multiplier

    # ------------------------------------------------------------------
    # Serialisation / representation
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of edges with registered incidents."""
        return len(self._incidents)

    def __repr__(self) -> str:
        type_names = list({i.type.name for i in self._incidents.values()})
        return (
            f"IncidentLayer({len(self._incidents)} incidents, "
            f"types={type_names})"
        )
