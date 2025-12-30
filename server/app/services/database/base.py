"""
Base database functionality.

Provides common database connection and initialization logic.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Tuple
from urllib.parse import urlparse

from psycopg2.extensions import connection
from psycopg2.pool import ThreadedConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_env_float(value: str | None, fallback: float) -> float:
    """Parse float threshold from environment."""
    if value is None:
        return fallback
    try:
        return float(value)
    except ValueError:
        logger.warning(
            "Invalid DB pool usage threshold value '%s'; using fallback %s",
            value,
            fallback,
        )
        return fallback


POOL_USAGE_WARN_THRESHOLD = _parse_env_float(
    value=os.environ.get("DB_POOL_USAGE_WARN_THRESHOLD"),
    fallback=0.8,
)


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
        pool = BaseDatabaseManager._pool
        assert pool is not None, "Connection pool not initialized"
        conn = pool.getconn()
        logger.debug("Fetched DB connection %s from pool", id(conn))
        self._log_pool_usage(pool=pool, action="checkout")
        try:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            pool.putconn(conn)
            logger.debug("Returned DB connection %s to pool", id(conn))
            self._log_pool_usage(pool=pool, action="return")

    @staticmethod
    def _log_pool_usage(*, pool: ThreadedConnectionPool, action: str) -> None:
        """Log pool usage to detect spikes."""
        used, idle, max_conn, ratio = BaseDatabaseManager._calculate_pool_usage(pool=pool)
        if ratio >= POOL_USAGE_WARN_THRESHOLD:
            logger.warning(
                "DB pool high usage (%s/%s used, %s idle) during %s",
                used,
                max_conn,
                idle,
                action,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "DB pool usage (%s/%s used, %s idle) during %s",
                used,
                max_conn,
                idle,
                action,
            )

    @staticmethod
    def _calculate_pool_usage(*, pool: ThreadedConnectionPool) -> Tuple[int, int, int, float]:
        """Return (used, idle, max, ratio) for the given pool."""
        used_connections = len(getattr(pool, "_used", []))
        idle_connections = len(getattr(pool, "_pool", []))
        max_connections = getattr(pool, "maxconn", used_connections + idle_connections)
        usage_ratio = used_connections / max_connections if max_connections else 0.0
        return used_connections, idle_connections, max_connections, usage_ratio
