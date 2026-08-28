"""
app/qpso/__init__.py – Public API for the Q-Route QPSO package.

Import from here rather than sub-modules directly:

    from app.qpso import QPSOConfig, QPSOOptimizer, QPSOResult
    from app.qpso import encode_random, decode
    from app.qpso import repair_capacity, two_opt
"""

from .config import QPSOConfig
from .local_search import two_opt
from .optimizer import QPSOOptimizer, QPSOResult
from .repair import repair_capacity
from .representation import decode, encode_random

__all__ = [
    "QPSOConfig",
    "QPSOOptimizer",
    "QPSOResult",
    "decode",
    "encode_random",
    "repair_capacity",
    "two_opt",
]
