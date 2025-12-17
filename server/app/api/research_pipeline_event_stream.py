import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.research_pipeline_stream import register_stream_queue, unregister_stream_queue
from app.middleware.auth import get_current_user
from app.models import (
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunStreamEvent,
    ResearchRunSubstageEvent,
    ResearchRunSubstageSummary,
    TreeVizItem,
)
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)

SSE_HEARTBEAT_INTERVAL_SECONDS = 30.0


def _format_stream_event(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def usd_to_cents(*, value_usd: float) -> int:
    cents = (Decimal(str(value_usd)) * Decimal("100")).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(cents)


def _build_hw_cost_estimate_event_data(
    *,
    now: datetime,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
) -> dict[str, object] | None:
    if started_running_at is None or cost_per_hour_cents <= 0:
        return None
    elapsed_seconds = (now - started_running_at).total_seconds()
    elapsed_seconds = max(elapsed_seconds, 0)
    cents = (
        Decimal(cost_per_hour_cents) * Decimal(str(elapsed_seconds)) / Decimal("3600")
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    estimate_cents = int(cents)
    return {
        "hw_estimated_cost_cents": estimate_cents,
        "hw_cost_per_hour_cents": int(cost_per_hour_cents),
        "hw_started_running_at": started_running_at.isoformat(),
    }


def _build_initial_stream_payload(
    *,
    db: DatabaseManager,
    run_id: str,
    conversation_id: int,
    current_run: ResearchPipelineRun,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
) -> dict:
    stage_events = [
        ResearchRunStageProgress.from_db_record(event).model_dump()
        for event in db.list_stage_progress_events(run_id=run_id)
    ]
    log_events = [
        ResearchRunLogEntry.from_db_record(event).model_dump()
        for event in db.list_run_log_events(run_id=run_id)
    ]
    substage_events = [
        ResearchRunSubstageEvent.from_db_record(event).model_dump()
        for event in db.list_substage_completed_events(run_id=run_id)
    ]
    substage_summary_records = db.list_substage_summary_events(run_id=run_id)
    substage_summaries = [
        ResearchRunSubstageSummary.from_db_record(event).model_dump()
        for event in substage_summary_records
    ]
    artifacts = [
        ResearchRunArtifactMetadata.from_db_record(
            artifact=artifact,
            conversation_id=conversation_id,
            run_id=run_id,
        ).model_dump()
        for artifact in db.list_run_artifacts(run_id=run_id)
    ]
    tree_viz = [
        TreeVizItem.from_db_record(record).model_dump()
        for record in db.list_tree_viz_for_run(run_id=run_id)
    ]
    paper_gen_events = [
        ResearchRunPaperGenerationProgress.from_db_record(event).model_dump()
        for event in db.list_paper_generation_events(run_id=run_id)
    ]
    run_events = [
        ResearchRunEvent.from_db_record(event).model_dump()
        for event in db.list_research_pipeline_run_events(run_id=run_id)
    ]
    best_node_payload = [
        ResearchRunBestNodeSelection.from_db_record(event).model_dump()
        for event in db.list_best_node_reasoning_events(run_id=run_id)
    ]

    return {
        "run": ResearchRunInfo.from_db_record(current_run).model_dump(),
        "stage_progress": stage_events,
        "logs": log_events,
        "substage_events": substage_events,
        "substage_summaries": substage_summaries,
        "artifacts": artifacts,
        "tree_viz": tree_viz,
        "events": run_events,
        "paper_generation_progress": paper_gen_events,
        "best_node_selections": best_node_payload,
        "hw_cost_estimate": _build_hw_cost_event_payload(
            started_running_at=started_running_at,
            cost_per_hour_cents=cost_per_hour_cents,
        ),
    }


def _build_hw_cost_event_payload(
    *,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
) -> dict[str, object] | None:
    return _build_hw_cost_estimate_event_data(
        now=datetime.now(timezone.utc),
        started_running_at=started_running_at,
        cost_per_hour_cents=cost_per_hour_cents,
    )


def _build_hw_cost_stream_event(
    *,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
) -> dict[str, object] | None:
    payload = _build_hw_cost_event_payload(
        started_running_at=started_running_at,
        cost_per_hour_cents=cost_per_hour_cents,
    )
    if payload is None:
        return None
    return {"type": "hw_cost_estimate", "data": payload}


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/events",
    response_model=ResearchRunStreamEvent,
    responses={
        200: {
            "description": "Research pipeline progress events",
            "content": {
                "text/event-stream": {
                    "schema": {"$ref": "#/components/schemas/ResearchRunStreamEvent"}
                }
            },
        }
    },
)
async def stream_research_run_events(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> StreamingResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")
    user = get_current_user(request)
    db = get_database()
    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    run = db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    hw_started_running_at = run.started_running_at
    hw_cost_per_hour_cents = run.cost_per_hour_cents

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal hw_started_running_at, hw_cost_per_hour_cents
        queue = register_stream_queue(run_id=run_id)
        initial_sent = False
        current_run = db.get_research_pipeline_run(run_id)
        if current_run is None:
            yield _format_stream_event(event={"type": "error", "data": "Run not found"})
            return

        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream for run %s", run_id)
                    break

                if not initial_sent:
                    initial_data = _build_initial_stream_payload(
                        db=db,
                        run_id=run_id,
                        conversation_id=conversation_id,
                        current_run=current_run,
                        started_running_at=hw_started_running_at,
                        cost_per_hour_cents=hw_cost_per_hour_cents,
                    )
                    yield _format_stream_event(event={"type": "initial", "data": initial_data})
                    initial_sent = True
                    continue

                if hw_started_running_at is None:
                    run = db.get_research_pipeline_run(run_id=run_id)
                    if run is not None:
                        hw_started_running_at = run.started_running_at
                if hw_cost_per_hour_cents is None or hw_cost_per_hour_cents <= 0:
                    run = db.get_research_pipeline_run(run_id=run_id)
                    if run is not None:
                        hw_cost_per_hour_cents = run.cost_per_hour_cents

                try:
                    event = await asyncio.wait_for(
                        fut=queue.get(),
                        timeout=SSE_HEARTBEAT_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        logger.info("Client disconnected from SSE stream for run %s", run_id)
                        break
                    yield _format_stream_event(event={"type": "heartbeat", "data": None})
                    hw_cost_event = _build_hw_cost_stream_event(
                        started_running_at=hw_started_running_at,
                        cost_per_hour_cents=hw_cost_per_hour_cents,
                    )
                    if hw_cost_event is not None:
                        yield _format_stream_event(event=hw_cost_event)
                    continue
                except RuntimeError as exc:
                    logger.exception("Runtime error while reading stream queue for run %s", run_id)
                    yield _format_stream_event(event={"type": "error", "data": str(exc)})
                    break

                yield _format_stream_event(event=event)

                hw_cost_event = _build_hw_cost_stream_event(
                    started_running_at=hw_started_running_at,
                    cost_per_hour_cents=hw_cost_per_hour_cents,
                )
                if hw_cost_event is not None:
                    yield _format_stream_event(event=hw_cost_event)

                if event.get("type") == "complete":
                    break
        finally:
            unregister_stream_queue(run_id=run_id, queue=queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
