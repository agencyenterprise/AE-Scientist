"""
Redis Streams Service for SSE Event Broadcasting

Provides cross-worker event streaming using Redis Streams. Each SSE endpoint
reads from a Redis stream, allowing events published by any worker to be
received by any other worker's SSE connections.

Key Features:
- Events are persisted in Redis streams (with configurable MAXLEN and TTL)
- Built-in ID tracking for resumable connections
- Automatic stream cleanup via TTL
- Connection pooling and automatic reconnection

Usage:
    # Publishing events (from webhook handlers, background tasks, etc.)
    await redis_streams.publish_event(
        stream_type="narrator",
        run_id="run-123",
        event_type="timeline_event",
        data={"key": "value"}
    )

    # Consuming events (from SSE endpoints)
    async for event in redis_streams.read_events("narrator", "run-123", last_id="0"):
        yield format_sse(event)
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Literal, Optional

from redis.asyncio import ConnectionPool, Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Stream types for different SSE endpoints
StreamType = Literal["narrator", "pipeline"]

# Global Redis connection pool
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def _get_stream_key(stream_type: StreamType, run_id: str) -> str:
    """Generate Redis key for a stream."""
    return f"sse:{stream_type}:{run_id}"


async def init_redis() -> None:
    """
    Initialize Redis connection pool.

    Should be called once on app startup.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        logger.warning("Redis already initialized")
        return

    try:
        _redis_pool = ConnectionPool.from_url(
            settings.redis.url,
            decode_responses=True,
            max_connections=20,
        )
        _redis_client = Redis(connection_pool=_redis_pool)

        # Test connection
        await _redis_client.ping()  # type: ignore[misc]
        logger.info("Redis connection established: %s", settings.redis.url)
    except Exception as exc:
        logger.error("Failed to connect to Redis: %s", exc)
        raise


async def close_redis() -> None:
    """
    Close Redis connection pool.

    Should be called on app shutdown.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None

    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None

    logger.info("Redis connection closed")


def get_redis() -> Redis:
    """Get the Redis client instance."""
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def publish_event(
    stream_type: StreamType,
    run_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> str:
    """
    Publish an event to a Redis stream.

    Args:
        stream_type: Type of stream ("narrator" or "pipeline")
        run_id: Research run ID
        event_type: Type of event (e.g., "timeline_event", "stage_progress")
        data: Event payload (will be JSON-serialized)

    Returns:
        The Redis stream message ID
    """
    client = get_redis()
    stream_key = _get_stream_key(stream_type, run_id)

    # Serialize event data
    event = {
        "type": event_type,
        "data": json.dumps(data),
    }

    # Add to stream with approximate maxlen (more efficient than exact)
    message_id: str = await client.xadd(
        stream_key,
        event,  # type: ignore[arg-type]
        maxlen=settings.redis.stream_maxlen,
        approximate=True,
    )

    # Set TTL on the stream key if configured
    if settings.redis.stream_ttl_seconds > 0:
        await client.expire(stream_key, settings.redis.stream_ttl_seconds)

    logger.debug(
        "Published event to %s: type=%s, id=%s",
        stream_key,
        event_type,
        message_id,
    )

    return message_id


async def read_events(
    stream_type: StreamType,
    run_id: str,
    last_id: str = "0",
    block_ms: int = 30000,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Read events from a Redis stream.

    This is an async generator that yields events as they arrive.
    Use in SSE endpoints to stream events to clients.

    Args:
        stream_type: Type of stream ("narrator" or "pipeline")
        run_id: Research run ID
        last_id: Last seen message ID (use "0" to read from beginning, "$" for new only)
        block_ms: How long to block waiting for new events (milliseconds)

    Yields:
        Dict with "type", "data", and "id" keys
    """
    client = get_redis()
    stream_key = _get_stream_key(stream_type, run_id)
    current_id = last_id

    while True:
        try:
            # XREAD with blocking - returns when new events arrive or timeout
            result = await client.xread(
                {stream_key: current_id},
                block=block_ms,
                count=100,  # Batch size for efficiency
            )

            if not result:
                # Timeout - yield None to signal keepalive opportunity
                yield {"type": "keepalive", "data": None, "id": current_id}
                continue

            # Process messages from the stream
            for stream_name, messages in result:
                for message_id, fields in messages:
                    current_id = message_id

                    # Parse the event data
                    event_type = fields.get("type", "unknown")
                    data_str = fields.get("data", "{}")

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse event data: %s", data_str)
                        data = {}

                    yield {
                        "type": event_type,
                        "data": data,
                        "id": message_id,
                    }

        except asyncio.CancelledError:
            logger.debug("Stream reader cancelled for %s", stream_key)
            raise
        except Exception as exc:
            logger.error("Error reading from stream %s: %s", stream_key, exc)
            # Brief pause before retry to avoid tight loop on persistent errors
            await asyncio.sleep(1)


async def get_stream_length(stream_type: StreamType, run_id: str) -> int:
    """
    Get the number of messages in a stream.

    Args:
        stream_type: Type of stream
        run_id: Research run ID

    Returns:
        Number of messages in the stream
    """
    client = get_redis()
    stream_key = _get_stream_key(stream_type, run_id)

    try:
        length = await client.xlen(stream_key)
        return int(length)
    except Exception:
        return 0


async def get_all_events(
    stream_type: StreamType,
    run_id: str,
    start_id: str = "-",
    end_id: str = "+",
    count: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """
    Get all events from a stream (non-blocking).

    Useful for fetching initial state when SSE connection is established.

    Args:
        stream_type: Type of stream
        run_id: Research run ID
        start_id: Start ID (use "-" for beginning)
        end_id: End ID (use "+" for end)
        count: Max number of events to return

    Returns:
        List of events with "type", "data", and "id" keys
    """
    client = get_redis()
    stream_key = _get_stream_key(stream_type, run_id)

    try:
        messages = await client.xrange(stream_key, start_id, end_id, count=count)
    except Exception as exc:
        logger.error("Error fetching events from %s: %s", stream_key, exc)
        return []

    events = []
    for message_id, fields in messages:
        event_type = fields.get("type", "unknown")
        data_str = fields.get("data", "{}")

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = {}

        events.append(
            {
                "type": event_type,
                "data": data,
                "id": message_id,
            }
        )

    return events


async def delete_stream(stream_type: StreamType, run_id: str) -> bool:
    """
    Delete a stream (for cleanup/testing).

    Args:
        stream_type: Type of stream
        run_id: Research run ID

    Returns:
        True if stream was deleted
    """
    client = get_redis()
    stream_key = _get_stream_key(stream_type, run_id)

    try:
        result = await client.delete(stream_key)
        return bool(result)
    except Exception as exc:
        logger.error("Error deleting stream %s: %s", stream_key, exc)
        return False
