import asyncio
import logging
from typing import Any, Dict, Set, Union

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
]

_RUN_STREAM_SUBSCRIBERS: Dict[str, Set[asyncio.Queue[Dict[str, Any]]]] = {}


def register_stream_queue(run_id: str) -> asyncio.Queue[Dict[str, Any]]:
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)
    subscribers = _RUN_STREAM_SUBSCRIBERS.setdefault(run_id, set())
    subscribers.add(queue)
    return queue


def unregister_stream_queue(run_id: str, queue: asyncio.Queue[Dict[str, Any]]) -> None:
    subscribers = _RUN_STREAM_SUBSCRIBERS.get(run_id)
    if not subscribers:
        return
    subscribers.discard(queue)
    if not subscribers:
        _RUN_STREAM_SUBSCRIBERS.pop(run_id, None)


def publish_stream_event(run_id: str, event: StreamEventModel) -> None:
    subscribers = _RUN_STREAM_SUBSCRIBERS.get(run_id)
    if not subscribers:
        return
    payload = event.model_dump()
    stale: list[asyncio.Queue[Dict[str, Any]]] = []
    for queue in list(subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                "Dropping stream event type=%s for run_id=%s due to full queue; unsubscribing consumer",
                event.type,
                run_id,
            )
            stale.append(queue)
    for queue in stale:
        subscribers.discard(queue)
    if not subscribers:
        _RUN_STREAM_SUBSCRIBERS.pop(run_id, None)
