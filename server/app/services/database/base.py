"""
Base database functionality.

Provides common database connection and initialization logic.
"""

import logging
from typing import Any, Dict
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection

from app.config import settings

logger = logging.getLogger(__name__)


class BaseDatabaseManager:
    """Base database manager with connection and initialization logic."""

    def __init__(self) -> None:
        """Initialize database manager."""
        # PostgreSQL connection parameters
        if settings.DATABASE_URL:
            # Parse DATABASE_URL if provided
            parsed = urlparse(settings.DATABASE_URL)
            # Any is used here because psycopg2.connect accepts flexible configuration types
            self.pg_config: Dict[str, Any] = {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": parsed.path[1:] if parsed.path else settings.POSTGRES_DB,
                "user": parsed.username,
                "password": parsed.password,
            }
        else:
            # Use individual settings
            self.pg_config = {
                "host": settings.POSTGRES_HOST,
                "port": settings.POSTGRES_PORT,
                "database": settings.POSTGRES_DB,
                "user": settings.POSTGRES_USER,
                "password": settings.POSTGRES_PASSWORD,
            }

        # Database schema is now managed by Alembic migrations
        # Run: alembic upgrade head

    def _get_connection(self) -> connection:
        """Get a PostgreSQL database connection."""
        return psycopg2.connect(**self.pg_config)  # type: ignore[no-any-return]

    # Database schema is now managed by Alembic migrations
    # All table creation and initialization has been moved to Alembic migration files
    # To initialize the database, run: alembic upgrade head
