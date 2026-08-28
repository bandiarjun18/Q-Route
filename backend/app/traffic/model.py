"""
app/traffic/model.py – Traffic simulation layer for Q-Route (Milestone 6).

Provides a clean, deterministic abstraction for road traffic conditions that
sits on top of the existing ``TransportGraph`` without altering base graph
data.

Public API
----------
TrafficState          – enum of named traffic levels and their multipliers
effective_travel_time – pure function: base_time * traffic_multiplier
TrafficLayer          – per-edge traffic state map with apply/reset support

Design notes
------------
- ``TrafficState`` enum values *are* the multipliers (e.g. HEAVY = 1.6),
  eliminating the need for a separate lookup table.
- ``TrafficLayer`` is a plain value object (no global state).  Multiple
  independent layers can coexist; callers control which one is applied.
- ``TrafficLayer.apply(tg)`` stamps each edge's ``congestion_factor`` so
  that all existing code paths — pathfinding, QPSO fitness, 2-opt — pick
  up traffic effects automatically without modification.
- ``TrafficLayer.reset(tg)`` restores ``congestion_factor`` to 1.0 on all
  managed edges.
- ``TrafficLayer.random()`` accepts an optional seed for fully deterministic
  traffic assignment, which is essential for reproducible experiments.
- The module introduces no import-time side effects and no module-level
  mutable state.

Extension points
----------------
- Incidents (M7+): set a specific edge's state via ``set_state(u, v, state)``
  then call ``apply(tg)`` again.
- Dynamic re-optimisation (future): build a new ``TrafficLayer`` per time
  step and call ``apply`` before each QPSO run.
- Time-of-day profiles: subclass or compose ``TrafficLayer`` with a schedule
  function that returns a state given a timestamp.
"""

from __future__ import annotations

import enum
import random as _random
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.graph.model import TransportGraph


# ---------------------------------------------------------------------------
# Traffic state enum
# ---------------------------------------------------------------------------

class TrafficState(enum.Enum):
    """
    Named traffic levels with associated travel-time multipliers.

    The enum *value* is the multiplier applied to ``base_travel_time``::

        effective_time = base_travel_time * TrafficState.HEAVY.value
                       = base_travel_time * 1.6

    Levels
    ------
    NORMAL : 1.0 – free-flow; travel time equals the uncongested baseline.
    LIGHT  : 1.1 – minor delays; 10 % longer than baseline.
    MEDIUM : 1.3 – moderate congestion; 30 % longer than baseline.
    HEAVY  : 1.6 – severe congestion; 60 % longer than baseline.
    """

    NORMAL = 1.0
    LIGHT  = 1.1
    MEDIUM = 1.3
    HEAVY  = 1.6


# ---------------------------------------------------------------------------
# Pure utility function
# ---------------------------------------------------------------------------

def effective_travel_time(base_travel_time: float, state: TrafficState) -> float:
    """
    Compute effective travel time for a road segment under given traffic.

    This is a **pure function** with no side effects.

    Parameters
    ----------
    base_travel_time : float
        Uncongested travel time for the road segment (minutes).
    state : TrafficState
        Current traffic level on the segment.

    Returns
    -------
    float
        ``base_travel_time * state.value`` (minutes).

    Examples
    --------
    >>> effective_travel_time(10.0, TrafficState.NORMAL)
    10.0
    >>> effective_travel_time(10.0, TrafficState.HEAVY)
    16.0
    """
    return base_travel_time * state.value


# ---------------------------------------------------------------------------
# Traffic layer
# ---------------------------------------------------------------------------

@dataclass
class TrafficLayer:
    """
    Per-edge traffic state map for a transport network.

    A ``TrafficLayer`` maps directed edges ``(u, v)`` to ``TrafficState``
    values.  Edges absent from the map implicitly have ``TrafficState.NORMAL``
    (multiplier 1.0, no change to travel time).

    Instances are independent value objects — there is no shared or global
    state.  Multiple layers can be created and compared without interfering
    with one another.

    Construction
    ------------
    Use one of the class-method factories rather than constructing directly:

    * ``TrafficLayer.from_dict(mapping)``   – explicit per-edge assignment
    * ``TrafficLayer.uniform(tg, state)``   – same state on every edge
    * ``TrafficLayer.random(tg, seed=...)`` – random assignment (reproducible)

    Applying to a graph
    -------------------
    ``layer.apply(tg)`` stamps each managed edge's ``congestion_factor``
    with the corresponding state's multiplier.  All existing code that reads
    ``congestion_factor`` (pathfinding, QPSO fitness, 2-opt) automatically
    reflects the traffic without any further changes.

    ``layer.reset(tg)`` restores ``congestion_factor`` to 1.0 on every
    managed edge, effectively removing the traffic overlay.

    Attributes
    ----------
    _states : dict[tuple[Any, Any], TrafficState]
        Internal mapping of ``(u, v)`` → ``TrafficState``.  Use the public
        accessor/mutator methods rather than accessing this directly.
    """

    _states: dict[tuple[Any, Any], TrafficState] = field(
        default_factory=dict, repr=False
    )

    # ------------------------------------------------------------------
    # Construction factories
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        mapping: Mapping[tuple[Any, Any], TrafficState | str],
    ) -> "TrafficLayer":
        """
        Build a ``TrafficLayer`` from an explicit edge-to-state mapping.

        Parameters
        ----------
        mapping : dict
            Keys are ``(u, v)`` edge tuples; values are ``TrafficState``
            members *or* their string names (e.g. ``"HEAVY"``).

        Returns
        -------
        TrafficLayer

        Raises
        ------
        ValueError
            If any value in ``mapping`` is not a valid ``TrafficState``.

        Examples
        --------
        >>> layer = TrafficLayer.from_dict({(0, 1): TrafficState.HEAVY,
        ...                                 (1, 2): TrafficState.LIGHT})
        >>> layer = TrafficLayer.from_dict({(0, 1): "MEDIUM"})
        """
        validated: dict[tuple[Any, Any], TrafficState] = {}
        for edge, state in mapping.items():
            if isinstance(state, TrafficState):
                validated[edge] = state
            elif isinstance(state, str):
                try:
                    validated[edge] = TrafficState[state]
                except KeyError:
                    valid_names = [s.name for s in TrafficState]
                    raise ValueError(
                        f"Invalid traffic state {state!r}. "
                        f"Valid states are: {valid_names}"
                    )
            else:
                valid_names = [s.name for s in TrafficState]
                raise ValueError(
                    f"Traffic state must be a TrafficState enum member or "
                    f"string name, got {type(state).__name__!r}. "
                    f"Valid states are: {valid_names}"
                )
        return cls(_states=validated)

    @classmethod
    def uniform(
        cls,
        tg: TransportGraph,
        state: TrafficState,
    ) -> "TrafficLayer":
        """
        Build a ``TrafficLayer`` that applies the same ``state`` to every
        edge in ``tg``.

        Parameters
        ----------
        tg    : TransportGraph
        state : TrafficState

        Returns
        -------
        TrafficLayer
        """
        states: dict[tuple[Any, Any], TrafficState] = {
            (u, v): state for u, v in tg.graph.edges()
        }
        return cls(_states=states)

    @classmethod
    def random(
        cls,
        tg: TransportGraph,
        seed: int | None = None,
        weights: dict[TrafficState, float] | None = None,
    ) -> "TrafficLayer":
        """
        Build a ``TrafficLayer`` with randomly assigned states for every
        edge in ``tg``.

        Parameters
        ----------
        tg      : TransportGraph
        seed    : int | None
            Random seed for reproducibility.  The same ``seed`` always
            produces the same assignment on the same graph.
        weights : dict[TrafficState, float] | None
            Relative probability weights for each state.  Defaults to
            equal probability for all four states.

        Returns
        -------
        TrafficLayer

        Examples
        --------
        >>> layer1 = TrafficLayer.random(tg, seed=42)
        >>> layer2 = TrafficLayer.random(tg, seed=42)
        >>> layer1.to_dict() == layer2.to_dict()
        True
        """
        rng = _random.Random(seed)
        all_states = list(TrafficState)
        if weights is not None:
            population = all_states
            w_list = [weights.get(s, 0.0) for s in all_states]
        else:
            population = all_states
            w_list = [1.0] * len(all_states)

        states: dict[tuple[Any, Any], TrafficState] = {}
        for u, v in tg.graph.edges():
            states[(u, v)] = rng.choices(population, weights=w_list, k=1)[0]
        return cls(_states=states)

    # ------------------------------------------------------------------
    # Accessors / mutators
    # ------------------------------------------------------------------

    def get_state(self, u: Any, v: Any) -> TrafficState:
        """
        Return the traffic state for edge ``(u, v)``.

        Falls back to ``TrafficState.NORMAL`` if the edge is not explicitly
        tracked by this layer.

        Parameters
        ----------
        u, v : any hashable – edge endpoints

        Returns
        -------
        TrafficState
        """
        return self._states.get((u, v), TrafficState.NORMAL)

    def set_state(self, u: Any, v: Any, state: TrafficState) -> None:
        """
        Update the traffic state for edge ``(u, v)``.

        Call ``apply(tg)`` afterwards to propagate the change to the graph.

        Parameters
        ----------
        u, v  : any hashable  – edge endpoints
        state : TrafficState  – new traffic level
        """
        self._states[(u, v)] = state

    def effective_time(
        self,
        u: Any,
        v: Any,
        base_travel_time: float,
    ) -> float:
        """
        Compute effective travel time for edge ``(u, v)`` without mutating
        anything.

        Parameters
        ----------
        u, v             : any hashable – edge endpoints
        base_travel_time : float – uncongested travel time (minutes)

        Returns
        -------
        float – ``base_travel_time * state.value``
        """
        return effective_travel_time(base_travel_time, self.get_state(u, v))

    # ------------------------------------------------------------------
    # Graph integration
    # ------------------------------------------------------------------

    def apply(self, tg: TransportGraph) -> None:
        """
        Stamp each tracked edge's ``congestion_factor`` with the traffic
        state's multiplier.

        Edges present in ``tg`` but absent from this layer are left
        unchanged (they retain their current ``congestion_factor``).

        Edges tracked by this layer but absent from ``tg`` are silently
        ignored — this allows a layer built on one snapshot of a graph to
        be applied to a modified version of the same graph.

        Parameters
        ----------
        tg : TransportGraph
        """
        g = tg.graph
        for (u, v), state in self._states.items():
            if g.has_edge(u, v):
                g[u][v]["congestion_factor"] = state.value

    def reset(self, tg: TransportGraph) -> None:
        """
        Restore ``congestion_factor`` to 1.0 for every edge tracked by
        this layer that exists in ``tg``.

        After calling ``reset``, the graph behaves as if no traffic overlay
        is active (NORMAL conditions on all managed edges).

        Parameters
        ----------
        tg : TransportGraph
        """
        g = tg.graph
        for (u, v) in self._states:
            if g.has_edge(u, v):
                g[u][v]["congestion_factor"] = TrafficState.NORMAL.value

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, str]:
        """
        Serialise to a JSON-compatible dict.

        Returns
        -------
        dict
            Keys are ``"u,v"`` string representations of edge tuples;
            values are ``TrafficState`` name strings (e.g. ``"HEAVY"``).

        Notes
        -----
        Edge tuple keys are converted to strings because JSON requires
        string keys.  Use ``from_dict`` with the original tuple keys to
        reconstruct.
        """
        return {
            f"{u},{v}": state.name
            for (u, v), state in self._states.items()
        }

    def __len__(self) -> int:
        """Return the number of edges explicitly tracked by this layer."""
        return len(self._states)

    def __repr__(self) -> str:
        return (
            f"TrafficLayer({len(self._states)} edges, "
            f"states={list(set(s.name for s in self._states.values()))})"
        )
