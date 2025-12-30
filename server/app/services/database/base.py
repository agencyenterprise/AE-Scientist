"""
Base database functionality.

Provides common database connection and initialization logic.
"""

import asyncio
import logging
import os
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager
from typing import Any, AsyncContextManager, AsyncIterator, Iterator, Tuple

from psycopg import AsyncConnection, Connection, conninfo
from psycopg_pool import AsyncConnectionPool, ConnectionPool

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
    def _get_connection(self) -> AbstractContextManager[Connection]:
        raise NotImplementedError

    def aget_connection(self) -> AsyncContextManager[AsyncConnection[Any]]:
        raise NotImplementedError("aget_connection must be implemented by subclasses")


class BaseDatabaseManager(ConnectionProvider):
    """Base database manager with pooled connection logic."""

    _pool: ConnectionPool | None = None
    _async_pool: AsyncConnectionPool | None = None
    _async_pool_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize database manager."""
        self._conninfo = self._build_conninfo()
        self._skip_db_connections = os.environ.get("SKIP_DB_CONNECTION", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if self._skip_db_connections:
            logger.info("Skipping database connection (SKIP_DB_CONNECTION=true)")
            return

        if BaseDatabaseManager._pool is None:
            min_conn, max_conn = self._pool_bounds()
            BaseDatabaseManager._pool = ConnectionPool(
                conninfo=self._conninfo,
                min_size=min_conn,
                max_size=max_conn,
            )

    @contextmanager
    def _get_connection(self) -> Iterator[Connection]:
        """Context manager that provides a pooled PostgreSQL connection."""
        pool = BaseDatabaseManager._pool
        assert pool is not None, "Connection pool not initialized"
        conn = pool.getconn()
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
            self._log_pool_usage(pool=pool, action="return")

    def aget_connection(self) -> AsyncContextManager[AsyncConnection[Any]]:
        """Async context manager that provides a pooled PostgreSQL connection."""

        @asynccontextmanager
        async def _manager() -> AsyncIterator[AsyncConnection[Any]]:
            pool = await self._get_async_pool()
            conn = await pool.getconn()
            self._log_async_pool_usage(pool=pool, action="checkout")
            try:
                try:
                    yield conn
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
            finally:
                await pool.putconn(conn)
                self._log_async_pool_usage(pool=pool, action="return")

        return _manager()

    async def _get_async_pool(self) -> AsyncConnectionPool:
        if getattr(self, "_skip_db_connections", False):
            raise RuntimeError("Database connections are disabled via SKIP_DB_CONNECTION")

        pool = BaseDatabaseManager._async_pool
        if pool is not None:
            return pool

        async with BaseDatabaseManager._async_pool_lock:
            pool = BaseDatabaseManager._async_pool
            if pool is None:
                min_conn, max_conn = self._pool_bounds()
                BaseDatabaseManager._async_pool = AsyncConnectionPool(
                    conninfo=self._conninfo,
                    min_size=min_conn,
                    max_size=max_conn,
                )
                pool = BaseDatabaseManager._async_pool

        assert pool is not None, "Async connection pool not initialized"
        return pool

    @staticmethod
    def _pool_bounds() -> Tuple[int, int]:
        min_conn = int(os.environ.get("DB_POOL_MIN_CONN", "1"))
        max_conn = int(os.environ.get("DB_POOL_MAX_CONN", "10"))
        return min_conn, max_conn

    @staticmethod
    def _build_conninfo() -> str:
        if settings.DATABASE_URL:
            return settings.DATABASE_URL
        return conninfo.make_conninfo(
            host=settings.POSTGRES_HOST,
            port=str(settings.POSTGRES_PORT),
            dbname=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )

    @staticmethod
    def _log_pool_usage(*, pool: ConnectionPool, action: str) -> None:
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

    @staticmethod
    def _calculate_pool_usage(*, pool: ConnectionPool) -> Tuple[int, int, int, float]:
        """Return (used, idle, max, ratio) for the given pool."""
        used_connections = len(getattr(pool, "_used", []))
        idle_connections = len(getattr(pool, "_pool", []))
        max_connections = getattr(pool, "maxconn", used_connections + idle_connections)
        usage_ratio = used_connections / max_connections if max_connections else 0.0
        return used_connections, idle_connections, max_connections, usage_ratio

    @staticmethod
    def _log_async_pool_usage(*, pool: AsyncConnectionPool, action: str) -> None:
        stats = pool.get_stats()
        checked_out = getattr(stats, "checked_out", 0) if stats else 0
        max_size = (
            getattr(stats, "max_size", getattr(pool, "max_size", 0))
            if stats
            else getattr(pool, "max_size", 0)
        )
        idle_estimate = max(
            (
                getattr(stats, "available", max_size - checked_out)
                if stats
                else max_size - checked_out
            ),
            0,
        )
        ratio = checked_out / max_size if max_size else 0.0
        if ratio >= POOL_USAGE_WARN_THRESHOLD:
            logger.warning(
                "Async DB pool high usage (%s/%s used, %s idle) during %s",
                checked_out,
                max_size,
                idle_estimate,
                action,
            )

    @classmethod
    async def close_all_pools(cls) -> None:
        """Close both sync and async pools."""
        if cls._pool is not None:
            cls._pool.close()
            cls._pool = None
            logger.info("Closed synchronous DB connection pool")

        if cls._async_pool is not None:
            await cls._async_pool.close()
            cls._async_pool = None
            logger.info("Closed async DB connection pool")
