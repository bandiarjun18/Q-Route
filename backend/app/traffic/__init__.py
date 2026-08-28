"""
app/traffic/__init__.py – Public API for the Q-Route traffic simulation layer.

Import from here rather than from sub-modules directly:

    from app.traffic import TrafficState, TrafficLayer, effective_travel_time
"""

from .model import TrafficState, TrafficLayer, effective_travel_time

__all__ = [
    "TrafficState",
    "TrafficLayer",
    "effective_travel_time",
]
