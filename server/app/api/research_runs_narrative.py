"""
Narrator SSE Endpoint

Streams timeline events and state updates to frontend.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import settings
from app.middleware.auth import get_current_user
from app.models.narrator_state import ResearchRunState
from app.services.database import DatabaseManager, get_database

from .narrator_stream import register_narrator_queue, unregister_narrator_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research-runs", tags=["narrator"])


def _serialize_for_json(
    obj: Union[datetime, dict, list, tuple],
) -> Union[str, dict, list, tuple]:
    """
    Recursively serialize objects for JSON, handling datetime objects.

    This is needed because model_dump(mode="json") converts Pydantic models
    to dicts but doesn't serialize datetime objects to strings.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_serialize_for_json(item) for item in obj)


@router.get("/{run_id}/narrative-state", response_model=ResearchRunState)
async def get_narrative_state(
    run_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_database),
) -> ResearchRunState:
    """
    Get the current narrator state for a research run.

    This endpoint exists primarily to ensure ResearchRunState and TimelineEvent
    types are properly exported to the OpenAPI schema and generated in frontend types.

    Returns the complete state including timeline events.

    Args:
        run_id: Research run ID
        request: FastAPI request object (for auth)
        db: Database manager

    Returns:
        ResearchRunState with full timeline
    """
    # Authenticate user
    get_current_user(request)
    # Get state from database
    state = await db.get_research_run_state(run_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"No narrator state found for run_id={run_id}")

    return state


@router.get("/{run_id}/narrative-stream")
async def narrative_stream(
    run_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_database),
) -> StreamingResponse:
    """
    SSE endpoint that streams narrator timeline events and state updates.

    Event Types:
    - "state_snapshot": Complete state snapshot (sent on connect)
    - "timeline_event": Individual timeline event (sent on connect + live)
    - "state_delta": Partial state update with only changed fields (live)
    - "ping": Keepalive ping (every 30s)

    Args:
        run_id: Research run ID
        request: FastAPI request object (for auth)
        db: Database manager

    Returns:
        StreamingResponse streaming narrator events
    """
    # Authenticate user
    get_current_user(request)

    def _format_sse_event(event_type: str, data: str) -> str:
        """Format event in SSE protocol format."""
        return f"event: {event_type}\ndata: {data}\n\n"

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = register_narrator_queue(run_id)

        try:
            # Send initial state snapshot (without timeline - we'll send events separately)
            state = await db.get_research_run_state(run_id)
            if state:
                # Extract timeline events before sending state
                timeline_events = state.timeline

                # Send state without timeline (empty array)
                state_dict = state.model_dump(mode="json")
                state_dict["timeline"] = []  # Empty - events sent separately
                yield _format_sse_event("state_snapshot", json.dumps(state_dict))

                # Now send each timeline event separately (from the state we just fetched)
                for event in timeline_events:
                    yield _format_sse_event(
                        "timeline_event", json.dumps(event.model_dump(mode="json"))
                    )

            # Stream live events
            while True:
                try:
                    # Wait for next event with timeout (for keepalive)
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # payload is {"type": str, "data": Dict[str, Any]}
                    event_type = str(payload["type"])
                    event_data = payload["data"]

                    # Serialize datetime objects before JSON encoding
                    serialized_data = _serialize_for_json(event_data)
                    yield _format_sse_event(event_type, json.dumps(serialized_data))
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield _format_sse_event("ping", "keepalive")

        except asyncio.CancelledError:
            logger.info("Narrator stream: Client disconnected for run_id=%s", run_id)

        finally:
            unregister_narrator_queue(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
