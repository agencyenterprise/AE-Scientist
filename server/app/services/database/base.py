"""
Base database functionality.

Provides common database connection and initialization logic.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator
from urllib.parse import urlparse

from psycopg2.extensions import connection
from psycopg2.pool import ThreadedConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionProvider:
    @contextmanager
    def _get_connection(self) -> Iterator[connection]:
        raise NotImplementedError


class BaseDatabaseManager(ConnectionProvider):
    """Base database manager with pooled connection logic."""

    _pool: ThreadedConnectionPool | None = None

    def __init__(self) -> None:
        """Initialize database manager."""
        skip_db = os.environ.get("SKIP_DB_CONNECTION", "").lower() in ("true", "1", "yes")

        if settings.DATABASE_URL:
            parsed = urlparse(settings.DATABASE_URL)
            self.pg_config: Dict[str, Any] = {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": parsed.path[1:] if parsed.path else settings.POSTGRES_DB,
                "user": parsed.username,
                "password": parsed.password,
            }
        else:
            self.pg_config = {
                "host": settings.POSTGRES_HOST,
                "port": settings.POSTGRES_PORT,
                "database": settings.POSTGRES_DB,
                "user": settings.POSTGRES_USER,
                "password": settings.POSTGRES_PASSWORD,
            }

        if skip_db:
            logger.info("Skipping database connection (SKIP_DB_CONNECTION=true)")
            return

        if BaseDatabaseManager._pool is None:
            min_conn = int(os.environ.get("DB_POOL_MIN_CONN", "1"))
            max_conn = int(os.environ.get("DB_POOL_MAX_CONN", "10"))
            BaseDatabaseManager._pool = ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                **self.pg_config,
            )

    @contextmanager
    def _get_connection(self) -> Iterator[connection]:
        """Context manager that provides a pooled PostgreSQL connection."""
        assert BaseDatabaseManager._pool is not None, "Connection pool not initialized"
        conn = BaseDatabaseManager._pool.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            BaseDatabaseManager._pool.putconn(conn)
            raise
        else:
            conn.commit()
            BaseDatabaseManager._pool.putconn(conn)
