"""
Narrator Stream Infrastructure

Parallel pub/sub system for narrator timeline events.
Separate from research_pipeline_stream to avoid interference.
"""

import asyncio
import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)

# Type for queue payloads
QueuePayload = Dict[str, Any]

# Separate subscriber dict for narrator streams
_NARRATOR_STREAM_SUBSCRIBERS: Dict[str, Set[asyncio.Queue[QueuePayload]]] = {}


def register_narrator_queue(run_id: str) -> asyncio.Queue[QueuePayload]:
    """Register a new narrator stream subscriber for a run."""
    queue: asyncio.Queue[QueuePayload] = asyncio.Queue(maxsize=1000)
    subscribers = _NARRATOR_STREAM_SUBSCRIBERS.setdefault(run_id, set())
    subscribers.add(queue)
    logger.info("Narrator stream: Registered subscriber for run_id=%s", run_id)
    return queue


def unregister_narrator_queue(run_id: str, queue: asyncio.Queue[QueuePayload]) -> None:
    """Unregister a narrator stream subscriber."""
    subscribers = _NARRATOR_STREAM_SUBSCRIBERS.get(run_id)
    if not subscribers:
        return
    subscribers.discard(queue)
    logger.info("Narrator stream: Unregistered subscriber for run_id=%s", run_id)
    if not subscribers:
        _NARRATOR_STREAM_SUBSCRIBERS.pop(run_id, None)
        logger.info("Narrator stream: No more subscribers for run_id=%s", run_id)


def publish_narrator_event(run_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Publish a narrator event to all subscribers for a run.

    Args:
        run_id: Research run ID
        event_type: Type of event ("timeline_event", "state_snapshot", or "state_delta")
        data: Event payload (serialized Pydantic model)
    """
    subscribers = _NARRATOR_STREAM_SUBSCRIBERS.get(run_id)
    if not subscribers:
        return

    payload: QueuePayload = {"type": event_type, "data": data}
    stale: list[asyncio.Queue[QueuePayload]] = []

    for queue in list(subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                "Narrator stream: Dropping event type=%s for run_id=%s due to full queue",
                event_type,
                run_id,
            )
            stale.append(queue)

    for queue in stale:
        subscribers.discard(queue)

    if not subscribers:
        _NARRATOR_STREAM_SUBSCRIBERS.pop(run_id, None)
