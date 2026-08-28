"""
app/qpso/__init__.py – Public API for the Q-Route QPSO package.

Import from here rather than sub-modules directly:

    from app.qpso import QPSOConfig, QPSOOptimizer, QPSOResult
    from app.qpso import encode_random, decode
"""

from .config import QPSOConfig
from .optimizer import QPSOOptimizer, QPSOResult
from .representation import encode_random, decode

__all__ = [
    "QPSOConfig",
    "QPSOOptimizer",
    "QPSOResult",
    "encode_random",
    "decode",
]
