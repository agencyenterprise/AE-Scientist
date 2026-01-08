import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import ORJSONResponse, StreamingResponse

from app.api.research_pipeline_stream import register_stream_queue, unregister_stream_queue
from app.middleware.auth import get_current_user
from app.models import (
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
    ResearchRunCodeExecution,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunStageSkipWindow,
    ResearchRunStreamEvent,
    ResearchRunSubstageEvent,
    ResearchRunSubstageSummary,
    TreeVizItem,
)
from app.models.sse import ResearchRunInitialEventData
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import (
    ResearchPipelineRun,
    ResearchPipelineRunEvent,
)

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)

SSE_HEARTBEAT_INTERVAL_SECONDS = 30.0
RUN_ACTIVE_STATUSES = {"pending", "running"}
RUN_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}

INT64_MIN = -(2**63)
INT64_MAX = (2**63) - 1


def _sanitize_orjson_value(*, value: object) -> object:
    if isinstance(value, int):
        if value < INT64_MIN or value > INT64_MAX:
            return str(value)
        return value
    if isinstance(value, list):
        return [_sanitize_orjson_value(value=item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_orjson_value(value=item) for item in value]
    if isinstance(value, dict):
        sanitized: dict[object, object] = {}
        for raw_key, raw_value in value.items():
            key = _sanitize_orjson_value(value=raw_key)
            if not isinstance(key, str):
                key = str(key)
            sanitized[key] = _sanitize_orjson_value(value=raw_value)
        return sanitized
    return value


def _parse_iso_timestamp(*, timestamp: str | None) -> datetime | None:
    if timestamp is None:
        return None
    value = timestamp.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_decimal(*, value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return Decimal(stripped)
        except InvalidOperation:
            return None
    return None


def _extract_total_amount_usd(*, metadata: dict[str, Any]) -> Decimal | None:
    for key in (
        "total_amount_usd",
        "totalAmountUsd",
        "totalAmountUSD",
        "amount",
        "total_amount",
    ):
        amount = _coerce_decimal(value=metadata.get(key))
        if amount is not None:
            return amount
    records = metadata.get("records")
    if isinstance(records, list):
        total = Decimal("0")
        found_amount = False
        for record in records:
            if not isinstance(record, dict):
                continue
            record_amount = _coerce_decimal(value=record.get("amount"))
            if record_amount is None:
                continue
            total += record_amount
            found_amount = True
        if found_amount:
            return total
    return None


def _extract_actual_cost_cents(*, metadata: dict[str, Any]) -> int | None:
    cents_value = _coerce_decimal(value=metadata.get("actual_cost_cents"))
    if cents_value is not None:
        return int(
            cents_value.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
    amount_usd = _extract_total_amount_usd(metadata=metadata)
    if amount_usd is None:
        return None
    return usd_to_cents(value_usd=float(amount_usd))


def _build_hw_actual_cost_payload_from_metadata(
    *,
    metadata: dict[str, Any],
    occurred_at: datetime | None,
) -> dict[str, object] | None:
    if occurred_at is None:
        return None
    cost_cents = _extract_actual_cost_cents(metadata=metadata)
    if cost_cents is None:
        return None
    return {
        "hw_actual_cost_cents": cost_cents,
        "hw_actual_cost_updated_at": occurred_at.isoformat(),
        "billing_summary": metadata,
    }


def _build_hw_actual_cost_payload_from_events(
    *,
    events: list[ResearchPipelineRunEvent],
) -> dict[str, object] | None:
    for event in reversed(events):
        if event.event_type != "pod_billing_summary":
            continue
        metadata_candidate: object = event.metadata
        if not isinstance(metadata_candidate, dict):
            continue
        metadata: dict[str, Any] = metadata_candidate
        return _build_hw_actual_cost_payload_from_metadata(
            metadata=metadata,
            occurred_at=event.occurred_at,
        )
    return None


def _build_hw_actual_cost_payload_from_run_event(
    *,
    run_event: dict[str, Any],
) -> dict[str, object] | None:
    metadata_candidate = run_event.get("metadata")
    if not isinstance(metadata_candidate, dict):
        return None
    metadata: dict[str, Any] = metadata_candidate
    occurred_at = _parse_iso_timestamp(timestamp=run_event.get("occurred_at"))
    return _build_hw_actual_cost_payload_from_metadata(
        metadata=metadata,
        occurred_at=occurred_at,
    )


def _extract_terminal_transition_time_from_events(
    *,
    events: list[ResearchPipelineRunEvent],
) -> datetime | None:
    for event in reversed(events):
        if event.event_type != "status_changed":
            continue
        metadata_candidate: object = event.metadata
        if not isinstance(metadata_candidate, dict):
            continue
        metadata: dict[str, Any] = metadata_candidate
        to_status = metadata.get("to_status")
        if isinstance(to_status, str) and to_status in RUN_TERMINAL_STATUSES:
            return event.occurred_at
    return None


def _extract_terminal_transition_time_from_run_event(
    *,
    run_event: dict[str, Any],
) -> datetime | None:
    metadata = run_event.get("metadata")
    if not isinstance(metadata, dict):
        return None
    to_status = metadata.get("to_status")
    if not isinstance(to_status, str):
        return None
    if to_status not in RUN_TERMINAL_STATUSES:
        return None
    return _parse_iso_timestamp(timestamp=run_event.get("occurred_at"))


async def _get_authorized_run_context(
    *,
    conversation_id: int,
    run_id: str,
    request: Request,
) -> tuple[DatabaseManager, ResearchPipelineRun]:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    user = get_current_user(request)
    db = get_database()
    conversation = await db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    run = await db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    return db, run


def _format_stream_event(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def usd_to_cents(*, value_usd: float) -> int:
    cents = (Decimal(str(value_usd)) * Decimal("100")).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(cents)


def _run_cost_per_hour_cents(run: ResearchPipelineRun | None) -> int:
    if run is None:
        return 0
    cost = getattr(run, "cost", None)
    if cost is None:
        return 0
    try:
        return usd_to_cents(value_usd=float(cost))
    except (TypeError, ValueError):
        return 0


def _build_hw_cost_estimate_event_data(
    *,
    now: datetime,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
    stopped_running_at: datetime | None,
) -> dict[str, object] | None:
    if started_running_at is None or cost_per_hour_cents <= 0:
        return None
    end_reference = stopped_running_at if stopped_running_at is not None else now
    if stopped_running_at is not None:
        end_reference = min(stopped_running_at, now)
    elapsed_seconds = (end_reference - started_running_at).total_seconds()
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


async def _build_initial_stream_payload(
    *,
    db: DatabaseManager,
    run_id: str,
    conversation_id: int,
    current_run: ResearchPipelineRun,
) -> dict:
    raw_run_events = await db.list_research_pipeline_run_events(run_id=run_id)
    stage_events = [
        ResearchRunStageProgress.from_db_record(event).model_dump()
        for event in await db.list_stage_progress_events(run_id=run_id)
    ]
    log_events = [
        ResearchRunLogEntry.from_db_record(event).model_dump()
        for event in await db.list_run_log_events(run_id=run_id)
    ]
    substage_events = [
        ResearchRunSubstageEvent.from_db_record(event).model_dump()
        for event in await db.list_substage_completed_events(run_id=run_id)
    ]
    substage_summary_records = await db.list_substage_summary_events(run_id=run_id)
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
        for artifact in await db.list_run_artifacts(run_id=run_id)
    ]
    tree_viz = [
        TreeVizItem.from_db_record(record).model_dump()
        for record in await db.list_tree_viz_for_run(run_id=run_id)
    ]
    paper_gen_events = [
        ResearchRunPaperGenerationProgress.from_db_record(event).model_dump()
        for event in await db.list_paper_generation_events(run_id=run_id)
    ]
    run_events = [ResearchRunEvent.from_db_record(event).model_dump() for event in raw_run_events]
    best_node_payload = [
        ResearchRunBestNodeSelection.from_db_record(event).model_dump()
        for event in await db.list_best_node_reasoning_events(run_id=run_id)
    ]
    latest_code_execution = await db.get_latest_code_execution_event(run_id=run_id)
    code_execution_snapshot = (
        ResearchRunCodeExecution.from_db_record(latest_code_execution).model_dump()
        if latest_code_execution
        else None
    )
    stage_skip_windows = [
        ResearchRunStageSkipWindow.from_db_record(record).model_dump()
        for record in await db.list_stage_skip_windows(run_id=run_id)
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
        "code_execution": code_execution_snapshot,
        "stage_skip_windows": stage_skip_windows,
        "hw_cost_estimate": _build_hw_cost_event_payload(
            started_running_at=current_run.started_running_at,
            cost_per_hour_cents=_run_cost_per_hour_cents(current_run),
            stopped_running_at=_extract_terminal_transition_time_from_events(
                events=raw_run_events,
            ),
        ),
        "hw_cost_actual": _build_hw_actual_cost_payload_from_events(events=raw_run_events),
    }


def _build_hw_cost_event_payload(
    *,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
    stopped_running_at: datetime | None,
) -> dict[str, object] | None:
    return _build_hw_cost_estimate_event_data(
        now=datetime.now(timezone.utc),
        started_running_at=started_running_at,
        cost_per_hour_cents=cost_per_hour_cents,
        stopped_running_at=stopped_running_at,
    )


def _build_hw_cost_stream_event(
    *,
    started_running_at: datetime | None,
    cost_per_hour_cents: int,
    stopped_running_at: datetime | None,
) -> dict[str, object] | None:
    payload = _build_hw_cost_event_payload(
        started_running_at=started_running_at,
        cost_per_hour_cents=cost_per_hour_cents,
        stopped_running_at=stopped_running_at,
    )
    if payload is None:
        return None
    return {"type": "hw_cost_estimate", "data": payload}


def _build_hw_cost_actual_stream_event(
    *,
    payload: dict[str, object],
) -> dict[str, object]:
    return {"type": "hw_cost_actual", "data": payload}


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
    db, run = await _get_authorized_run_context(
        conversation_id=conversation_id,
        run_id=run_id,
        request=request,
    )
    hw_started_running_at = run.started_running_at
    hw_cost_per_hour_cents = _run_cost_per_hour_cents(run)
    hw_stopped_running_at: datetime | None = None
    hw_cost_actual_payload: dict[str, object] | None = None
    hw_cost_actual_dirty = False
    if run.status not in RUN_ACTIVE_STATUSES:
        completed_run_events = await db.list_research_pipeline_run_events(run_id=run_id)
        hw_stopped_running_at = _extract_terminal_transition_time_from_events(
            events=completed_run_events,
        )
        hw_cost_actual_payload = _build_hw_actual_cost_payload_from_events(
            events=completed_run_events,
        )
        hw_cost_actual_dirty = hw_cost_actual_payload is not None

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal hw_started_running_at
        nonlocal hw_cost_per_hour_cents
        nonlocal hw_stopped_running_at
        nonlocal hw_cost_actual_payload
        nonlocal hw_cost_actual_dirty
        queue = register_stream_queue(run_id=run_id)
        current_run = await db.get_research_pipeline_run(run_id)
        if current_run is None:
            yield _format_stream_event(event={"type": "error", "data": "Run not found"})
            return

        try:
            if hw_cost_actual_dirty and hw_cost_actual_payload is not None:
                yield _format_stream_event(
                    event=_build_hw_cost_actual_stream_event(payload=hw_cost_actual_payload),
                )
                hw_cost_actual_dirty = False
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream for run %s", run_id)
                    break

                if hw_started_running_at is None:
                    refreshed_run = await db.get_research_pipeline_run(run_id=run_id)
                    if refreshed_run is not None:
                        hw_started_running_at = refreshed_run.started_running_at
                if hw_cost_per_hour_cents is None or hw_cost_per_hour_cents <= 0:
                    refreshed_run = await db.get_research_pipeline_run(run_id=run_id)
                    if refreshed_run is not None:
                        hw_cost_per_hour_cents = _run_cost_per_hour_cents(refreshed_run)

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
                        stopped_running_at=hw_stopped_running_at,
                    )
                    if hw_cost_event is not None:
                        yield _format_stream_event(event=hw_cost_event)
                    if hw_cost_actual_dirty and hw_cost_actual_payload is not None:
                        yield _format_stream_event(
                            event=_build_hw_cost_actual_stream_event(
                                payload=hw_cost_actual_payload,
                            ),
                        )
                        hw_cost_actual_dirty = False
                    continue
                except RuntimeError as exc:
                    logger.exception("Runtime error while reading stream queue for run %s", run_id)
                    yield _format_stream_event(event={"type": "error", "data": str(exc)})
                    break

                yield _format_stream_event(event=event)

                if event.get("type") == "run_event":
                    run_event_payload = event.get("data")
                    if isinstance(run_event_payload, dict):
                        transition_time = _extract_terminal_transition_time_from_run_event(
                            run_event=run_event_payload,
                        )
                        if transition_time is not None:
                            hw_stopped_running_at = transition_time
                        actual_cost_payload = _build_hw_actual_cost_payload_from_run_event(
                            run_event=run_event_payload,
                        )
                        if actual_cost_payload is not None:
                            hw_cost_actual_payload = actual_cost_payload
                            hw_cost_actual_dirty = True

                hw_cost_event = _build_hw_cost_stream_event(
                    started_running_at=hw_started_running_at,
                    cost_per_hour_cents=hw_cost_per_hour_cents,
                    stopped_running_at=hw_stopped_running_at,
                )
                if hw_cost_event is not None:
                    yield _format_stream_event(event=hw_cost_event)
                if hw_cost_actual_dirty and hw_cost_actual_payload is not None:
                    yield _format_stream_event(
                        event=_build_hw_cost_actual_stream_event(payload=hw_cost_actual_payload),
                    )
                    hw_cost_actual_dirty = False

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


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/snapshot",
    response_model=ResearchRunInitialEventData,
)
async def get_research_run_snapshot(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> ORJSONResponse:
    db, current_run = await _get_authorized_run_context(
        conversation_id=conversation_id,
        run_id=run_id,
        request=request,
    )

    initial_payload = await _build_initial_stream_payload(
        db=db,
        run_id=run_id,
        conversation_id=conversation_id,
        current_run=current_run,
    )
    return ORJSONResponse(content=_sanitize_orjson_value(value=initial_payload))
