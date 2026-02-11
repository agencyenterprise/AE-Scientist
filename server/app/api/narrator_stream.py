"""
Narrator Stream Infrastructure

Cross-worker pub/sub for narrator timeline events using Redis Streams.

Events published to Redis can be consumed by any worker's SSE connections,
solving the multi-worker deployment issue where webhooks and SSE connections
may be handled by different workers.
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional

from app.services import redis_streams

logger = logging.getLogger(__name__)


async def publish_narrator_event(run_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Publish a narrator event to the Redis stream.

    Args:
        run_id: Research run ID
        event_type: Type of event ("timeline_event", "state_snapshot", or "state_delta")
        data: Event payload (serialized Pydantic model)
    """
    try:
        await redis_streams.publish_event(
            stream_type="narrator",
            run_id=run_id,
            event_type=event_type,
            data=data,
        )
    except Exception as exc:
        logger.error(
            "Failed to publish narrator event: run_id=%s type=%s error=%s",
            run_id,
            event_type,
            exc,
        )


async def read_narrator_events(
    run_id: str,
    last_id: str = "0",
    block_ms: int = 30000,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Read narrator events from the Redis stream.

    This is an async generator for use in SSE endpoints.

    Args:
        run_id: Research run ID
        last_id: Last seen message ID ("0" for all events, "$" for new only)
        block_ms: How long to block waiting for new events

    Yields:
        Dict with "type", "data", and "id" keys
    """
    async for event in redis_streams.read_events(
        stream_type="narrator",
        run_id=run_id,
        last_id=last_id,
        block_ms=block_ms,
    ):
        yield event


async def get_narrator_events(
    run_id: str,
    start_id: str = "-",
    end_id: str = "+",
    count: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """
    Get all narrator events from the stream (non-blocking).

    Useful for fetching initial state when SSE connection is established.

    Args:
        run_id: Research run ID
        start_id: Start ID ("-" for beginning)
        end_id: End ID ("+" for end)
        count: Max events to return

    Returns:
        List of events with "type", "data", and "id" keys
    """
    return await redis_streams.get_all_events(
        stream_type="narrator",
        run_id=run_id,
        start_id=start_id,
        end_id=end_id,
        count=count,
    )
