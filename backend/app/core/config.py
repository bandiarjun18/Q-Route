"""
app/core/config.py – Application and Database Configuration.

Reads settings from environment variables and optional .env file.
"""

from __future__ import annotations

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Q-Route configuration settings."""

    # Project
    PROJECT_NAME: str = "Q-Route API"
    VERSION: str = "0.9.0"

    # Database
    # Default connects to local PostgreSQL database 'qroute' with user 'postgres'
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/qroute"

    # Optional test DB URL (e.g. SQLite for unit tests or isolated test DB)
    TEST_DATABASE_URL: Optional[str] = None

    # Connection pool configuration
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
