"""
app/routes/manager.py – Route manager for Q-Route (Milestone 8).

Public API
----------
RouteManager – manages a collection of ActiveRoute objects.

Design notes
------------
- RouteManager is a plain class — NOT a singleton, NOT a global.  Every
  call to RouteManager() produces a fully independent instance with its own
  private ``_routes`` dict.  No state is shared between instances.
- register() validates the route against the live graph (via validate_route),
  rejects duplicate route_id values, and stamps total_distance /
  total_travel_time before storing.
- deactivate() sets a terminal status without removing the route, preserving
  historical records.  list_active() filters to ACTIVE and AFFECTED only.
- update() enforces that structural-identity fields cannot be mutated after
  registration: route_id, vehicle_id, node_sequence, depot_node, visit_order.
- affected_by_incident() uses incident_layer.has_incident(u, v) for every
  consecutive edge pair in each route's node_sequence.  It never modifies the
  graph and never calls apply(); it only reads the incident registry.
- No module-level mutable state exists anywhere in this file.
"""

from __future__ import annotations

from typing import Any

from app.graph.model import TransportGraph
from app.incidents.model import IncidentLayer
from app.routes.eta import route_distance, route_travel_time
from app.routes.model import ActiveRoute, RouteStatus
from app.routes.validation import validate_route


# Fields that define a route's structural identity.
# Callers may NOT update these via RouteManager.update().
_PROTECTED_FIELDS: frozenset[str] = frozenset(
    {"route_id", "vehicle_id", "node_sequence", "depot_node", "visit_order"}
)

# Statuses considered "live" for list_active() and affected_by_incident().
_LIVE_STATUSES: frozenset[RouteStatus] = frozenset(
    {RouteStatus.ACTIVE, RouteStatus.AFFECTED}
)


class RouteManager:
    """
    Registry and lifecycle manager for active vehicle routes.

    Each instance is fully independent — there is no shared or global state.
    Creating two ``RouteManager`` objects produces two completely isolated
    registries that cannot interfere with one another.

    Usage
    -----
    ::

        rm = RouteManager()
        rm.register(active_route, tg)          # validates + stamps metrics
        route = rm.get("R1")                   # retrieve by id
        rm.update("R1", estimated_arrival=25.0) # update allowed field
        rm.deactivate("R1")                    # status → COMPLETED (stays in registry)
        rm.remove("R1")                        # removed entirely

    Key invariants
    --------------
    - ``route_id`` is unique within a registry; duplicates raise ValueError.
    - Structural-identity fields (route_id, vehicle_id, node_sequence,
      depot_node, visit_order) cannot be modified after registration.
    - Invalid routes (closed edges, missing nodes/edges) are rejected at
      registration time and never enter the registry.
    """

    def __init__(self) -> None:
        self._routes: dict[str, ActiveRoute] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, route: ActiveRoute, tg: TransportGraph) -> ActiveRoute:
        """
        Validate and register an ``ActiveRoute`` into this manager.

        Steps performed in order:

        1. Calls ``validate_route(tg, route.node_sequence)`` — raises
           ``ValueError`` if the sequence contains unknown nodes, missing
           directed edges, or closed edges.
        2. Raises ``ValueError`` if ``route.route_id`` is already registered
           (duplicate IDs are never silently overwritten).
        3. Stamps ``route.total_distance`` and ``route.total_travel_time``
           using the current graph state (reflecting any applied TrafficLayer
           or IncidentLayer).
        4. Stores the route and returns it.

        Parameters
        ----------
        route : ActiveRoute    – the route to register.
        tg    : TransportGraph – the current road network.

        Returns
        -------
        ActiveRoute – the registered route with metrics stamped in-place.

        Raises
        ------
        ValueError
            If the route is invalid (bad node, missing/closed edge, sequence
            too short) or if ``route.route_id`` is already registered.
        """
        validate_route(tg, route.node_sequence)

        if route.route_id in self._routes:
            raise ValueError(
                f"A route with id {route.route_id!r} is already registered. "
                f"Use a unique route_id or call remove() first."
            )

        route.total_distance = route_distance(tg, route.node_sequence)
        route.total_travel_time = route_travel_time(tg, route.node_sequence)

        self._routes[route.route_id] = route
        return route

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, route_id: str) -> ActiveRoute:
        """
        Return the route with the given ``route_id``.

        Parameters
        ----------
        route_id : str

        Returns
        -------
        ActiveRoute

        Raises
        ------
        KeyError
            If no route with ``route_id`` exists in this registry.
        """
        if route_id not in self._routes:
            raise KeyError(
                f"No route with id {route_id!r} found in this registry."
            )
        return self._routes[route_id]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, _route_id: str, **fields: Any) -> ActiveRoute:
        """
        Update one or more non-protected fields on an existing route.

        Permitted fields: ``status``, ``estimated_arrival``,
        ``total_travel_time``, ``total_distance``.

        Protected fields — ``route_id``, ``vehicle_id``, ``node_sequence``,
        ``depot_node``, ``visit_order`` — define the route's structural
        identity and cannot be changed through this method.

        Parameters
        ----------
        _route_id : str – identifier of the route to update.  The parameter
                         is prefixed with ``_`` to avoid shadowing a caller's
                         ``route_id`` keyword argument in ``**fields``.
        **fields        – keyword arguments mapping field names to new values.

        Returns
        -------
        ActiveRoute – the mutated route.

        Raises
        ------
        KeyError
            If no route with ``_route_id`` exists.
        ValueError
            If any key in ``fields`` names a protected field.
        """
        route = self.get(_route_id)  # raises KeyError if absent

        attempted_protected = _PROTECTED_FIELDS.intersection(fields)
        if attempted_protected:
            raise ValueError(
                f"The following field(s) are protected and cannot be updated "
                f"via RouteManager.update(): {sorted(attempted_protected)}. "
                f"They define the route's structural identity."
            )

        for key, value in fields.items():
            setattr(route, key, value)

        return route

    # ------------------------------------------------------------------
    # Deactivation
    # ------------------------------------------------------------------

    def deactivate(
        self,
        route_id: str,
        status: RouteStatus = RouteStatus.COMPLETED,
    ) -> ActiveRoute:
        """
        Mark a route as terminal without removing it from the registry.

        The route's status is updated to the given terminal status.  It
        remains accessible via ``get()`` and ``routes_for_vehicle()`` for
        historical queries, but is no longer returned by ``list_active()``.

        Parameters
        ----------
        route_id : str         – identifier of the route to deactivate.
        status   : RouteStatus – terminal status to apply
                                 (default: ``RouteStatus.COMPLETED``).

        Returns
        -------
        ActiveRoute – the deactivated route.

        Raises
        ------
        KeyError
            If no route with ``route_id`` exists.
        """
        route = self.get(route_id)
        route.status = status
        return route

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------

    def remove(self, route_id: str) -> None:
        """
        Unconditionally remove a route from this registry.

        Parameters
        ----------
        route_id : str

        Raises
        ------
        KeyError
            If no route with ``route_id`` exists.
        """
        if route_id not in self._routes:
            raise KeyError(
                f"No route with id {route_id!r} found in this registry."
            )
        del self._routes[route_id]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_active(self) -> list[ActiveRoute]:
        """
        Return all routes with status ``ACTIVE`` or ``AFFECTED``.

        Routes with terminal status (``COMPLETED``, ``CANCELLED``) are
        excluded.

        Returns
        -------
        list[ActiveRoute] – may be empty; order is not guaranteed.
        """
        return [
            r for r in self._routes.values()
            if r.status in _LIVE_STATUSES
        ]

    def routes_for_vehicle(self, vehicle_id: Any) -> list[ActiveRoute]:
        """
        Return all stored routes for a specific vehicle, regardless of status.

        Parameters
        ----------
        vehicle_id : any hashable – value matching ``ActiveRoute.vehicle_id``.

        Returns
        -------
        list[ActiveRoute] – may be empty; includes terminal-status routes.
        """
        return [
            r for r in self._routes.values()
            if r.vehicle_id == vehicle_id
        ]

    # ------------------------------------------------------------------
    # Incident integration
    # ------------------------------------------------------------------

    def affected_by_incident(
        self,
        incident_layer: IncidentLayer,
        mark: bool = False,
    ) -> list[ActiveRoute]:
        """
        Identify live routes whose path overlaps with a registered incident.

        A route is considered affected when any consecutive directed edge
        ``(u, v)`` in its ``node_sequence`` has an incident registered in
        ``incident_layer`` (checked via ``incident_layer.has_incident(u, v)``).

        Both closure incidents (``ROAD_CLOSURE`` → edge becomes impassable)
        and partial incidents (congestion-increase only) trigger affectedness,
        because either type of incident degrades the route's planned behaviour.

        Only routes with status ``ACTIVE`` or ``AFFECTED`` are evaluated.
        Routes with terminal status (``COMPLETED``, ``CANCELLED``) are
        ignored — they are no longer operationally relevant.

        Parameters
        ----------
        incident_layer : IncidentLayer – the incident registry to check against.
                                         This function reads only; it does not
                                         call apply() or mutate the graph.
        mark           : bool          – if ``True``, set the status of every
                                         newly identified affected route to
                                         ``RouteStatus.AFFECTED``.
                                         Default: ``False`` (query-only).

        Returns
        -------
        list[ActiveRoute]
            Routes with status ``ACTIVE`` or ``AFFECTED`` that overlap with
            at least one incident.  Order is not guaranteed.

        Notes
        -----
        This method does NOT trigger re-optimisation — that is a future
        milestone.  It establishes the detection foundation required for
        selective re-optimisation.
        """
        affected: list[ActiveRoute] = []

        for route in self._routes.values():
            if route.status not in _LIVE_STATUSES:
                continue

            seq = route.node_sequence
            route_is_affected = any(
                incident_layer.has_incident(u, v)
                for u, v in zip(seq[:-1], seq[1:])
            )

            if route_is_affected:
                affected.append(route)
                if mark:
                    route.status = RouteStatus.AFFECTED

        return affected

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the total number of routes in this registry (all statuses)."""
        return len(self._routes)

    def __repr__(self) -> str:
        active_count = sum(
            1 for r in self._routes.values() if r.status in _LIVE_STATUSES
        )
        return (
            f"RouteManager({len(self._routes)} total routes, "
            f"{active_count} live)"
        )
