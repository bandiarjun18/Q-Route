"""
app/db/base.py – SQLAlchemy Declarative Base class for Q-Route.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all Q-Route SQLAlchemy ORM models."""
    pass
