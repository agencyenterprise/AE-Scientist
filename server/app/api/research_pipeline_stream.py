"""
Research Pipeline Stream Infrastructure

Cross-worker pub/sub for research pipeline events using Redis Streams.

Events published to Redis can be consumed by any worker's SSE connections,
solving the multi-worker deployment issue where webhooks and SSE connections
may be handled by different workers.
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional, Union

from app.models.sse import ResearchRunAccessRestrictedEvent as SSEAccessRestrictedEvent
from app.models.sse import ResearchRunArtifactEvent as SSEArtifactEvent
from app.models.sse import ResearchRunCodeExecutionCompletedEvent as SSECodeExecutionCompletedEvent
from app.models.sse import ResearchRunCodeExecutionStartedEvent as SSECodeExecutionStartedEvent
from app.models.sse import ResearchRunCompleteEvent as SSECompleteEvent
from app.models.sse import ResearchRunInitializationStatusEvent as SSEInitializationStatusEvent
from app.models.sse import ResearchRunPaperGenerationEvent as SSEPaperGenerationEvent
from app.models.sse import ResearchRunReviewCompletedEvent as SSEReviewCompletedEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.sse import ResearchRunStageEventStream as SSEStageEvent
from app.models.sse import ResearchRunStageProgressEvent as SSEStageProgressEvent
from app.models.sse import ResearchRunStageSkipWindowEvent as SSEStageSkipWindowEvent
from app.models.sse import ResearchRunStageSummaryEvent as SSEStageSummaryEvent
from app.models.sse import ResearchRunTerminationStatusEvent as SSETerminationStatusEvent
from app.services import redis_streams

logger = logging.getLogger(__name__)

StreamEventModel = Union[
    SSEStageProgressEvent,
    SSEPaperGenerationEvent,
    SSEStageEvent,
    SSEStageSummaryEvent,
    SSERunEvent,
    SSEInitializationStatusEvent,
    SSECompleteEvent,
    SSETerminationStatusEvent,
    SSEArtifactEvent,
    SSEReviewCompletedEvent,
    SSECodeExecutionStartedEvent,
    SSECodeExecutionCompletedEvent,
    SSEStageSkipWindowEvent,
    SSEAccessRestrictedEvent,
]


async def publish_stream_event(run_id: str, event: StreamEventModel) -> None:
    """
    Publish a research pipeline event to the Redis stream.

    Args:
        run_id: Research run ID
        event: Event model to publish
    """
    try:
        # Pydantic model has .type attribute for the event type
        event_type = event.type
        # Serialize the event data
        data = event.model_dump()

        await redis_streams.publish_event(
            stream_type="pipeline",
            run_id=run_id,
            event_type=event_type,
            data=data,
        )
    except Exception as exc:
        logger.error(
            "Failed to publish pipeline event: run_id=%s type=%s error=%s",
            run_id,
            event.type,
            exc,
        )


async def read_pipeline_events(
    run_id: str,
    last_id: str = "0",
    block_ms: int = 30000,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Read pipeline events from the Redis stream.

    This is an async generator for use in SSE endpoints.

    Args:
        run_id: Research run ID
        last_id: Last seen message ID ("0" for all events, "$" for new only)
        block_ms: How long to block waiting for new events

    Yields:
        Dict with event data including "type" field
    """
    async for event in redis_streams.read_events(
        stream_type="pipeline",
        run_id=run_id,
        last_id=last_id,
        block_ms=block_ms,
    ):
        yield event


async def get_pipeline_events(
    run_id: str,
    start_id: str = "-",
    end_id: str = "+",
    count: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """
    Get all pipeline events from the stream (non-blocking).

    Useful for fetching initial state when SSE connection is established.

    Args:
        run_id: Research run ID
        start_id: Start ID ("-" for beginning)
        end_id: End ID ("+" for end)
        count: Max events to return

    Returns:
        List of events with event data
    """
    return await redis_streams.get_all_events(
        stream_type="pipeline",
        run_id=run_id,
        start_id=start_id,
        end_id=end_id,
        count=count,
    )
