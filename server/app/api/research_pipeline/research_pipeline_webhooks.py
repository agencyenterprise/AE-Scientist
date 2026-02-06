"""Event webhook endpoints for research pipeline: stage progress, heartbeats, status changes."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Sequence, cast

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.llm_providers import extract_model_name_and_provider
from app.api.research_pipeline.utils import generate_run_webhook_token
from app.api.research_pipeline_stream import StreamEventModel, publish_stream_event
from app.models.research_pipeline import LlmReviewResponse, ResearchRunArtifactMetadata
from app.models.research_pipeline import ResearchRunEvent as RPEvent
from app.models.research_pipeline import (
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
)
from app.models.research_pipeline import ResearchRunSubstageEvent as RPSubstageEvent
from app.models.research_pipeline import ResearchRunSubstageSummary
from app.models.sse import ResearchRunArtifactEvent as SSEArtifactEvent
from app.models.sse import ResearchRunCodeExecutionCompletedData
from app.models.sse import ResearchRunCodeExecutionCompletedEvent as SSECodeExecutionCompletedEvent
from app.models.sse import ResearchRunCodeExecutionStartedData
from app.models.sse import ResearchRunCodeExecutionStartedEvent as SSECodeExecutionStartedEvent
from app.models.sse import ResearchRunInitializationStatusData
from app.models.sse import ResearchRunInitializationStatusEvent as SSEInitializationStatusEvent
from app.models.sse import ResearchRunPaperGenerationEvent as SSEPaperGenerationEvent
from app.models.sse import ResearchRunReviewCompletedEvent as SSEReviewCompletedEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.sse import ResearchRunStageProgressEvent as SSEStageProgressEvent
from app.models.sse import ResearchRunStageSkipWindowEvent as SSEStageSkipWindowEvent
from app.models.sse import ResearchRunStageSkipWindowUpdate, ResearchRunSubstageCompletedEvent
from app.models.sse import ResearchRunSubstageSummaryEvent as SSESubstageSummaryEvent
from app.services import DatabaseManager, get_database
from app.services.billing_guard import charge_for_llm_usage
from app.services.narrator.event_types import RunFinishedEventData, RunStartedEventData
from app.services.narrator.narrator_service import ingest_narration_event
from app.services.research_pipeline.pod_restart import attempt_pod_restart
from app.services.research_pipeline.pod_termination_worker import (
    notify_termination_requested,
    publish_termination_status_event,
)
from app.services.research_pipeline.runpod import get_supported_gpu_types
from app.services.research_pipeline.runpod.runpod_initialization import WORKSPACE_PATH

from .auth import ResearchRunStore, verify_run_auth
from .schemas import (
    ArtifactUploadedPayload,
    CodexEventPayload,
    DiskUsagePartition,
    FigureReviewsPayload,
    GPUShortagePayload,
    HardwareStatsPayload,
    InitializationProgressPayload,
    PaperGenerationProgressPayload,
    ReviewCompletedPayload,
    RunCompletedPayload,
    RunFinishedPayload,
    RunLogPayload,
    RunningCodePayload,
    StageProgressPayload,
    StageSkipWindowPayload,
    SubstageCompletedPayload,
    SubstageSummaryPayload,
    TokenUsagePayload,
    TreeVizStoredPayload,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Disk Usage Helpers
# -----------------------------------------------------------------------------

LOW_FREE_DISK_THRESHOLD_BYTES = 50 * 1024**3
BYTES_PER_GB = 1024**3


def resolve_partition_capacity_bytes(
    *,
    container_disk_gb: int | None,
    volume_disk_gb: int | None,
    partition: str,
) -> int | None:
    """Resolve the total capacity in bytes for a given partition."""
    normalized = partition if partition == "/" else partition.rstrip("/")
    if not normalized:
        normalized = "/"
    if normalized == "/":
        capacity_gb = container_disk_gb
    elif normalized == WORKSPACE_PATH:
        capacity_gb = volume_disk_gb
    else:
        return None
    if capacity_gb is None:
        return None
    return int(capacity_gb) * BYTES_PER_GB


async def record_disk_usage_event(
    *,
    db: ResearchRunStore,
    run_id: str,
    partitions: Sequence[DiskUsagePartition],
    occurred_at: datetime,
    event_type: str,
) -> None:
    """Record disk usage event and warn on low disk space."""
    if not partitions:
        return
    partitions_payload = []
    low_free_partitions: list[tuple[str, int]] = []
    for partition in partitions:
        free_bytes = max(partition.total_bytes - partition.used_bytes, 0)
        partitions_payload.append(
            {
                "partition": partition.partition,
                "total_bytes": partition.total_bytes,
                "used_bytes": partition.used_bytes,
                "free_bytes": free_bytes,
            }
        )
        if free_bytes < LOW_FREE_DISK_THRESHOLD_BYTES:
            low_free_partitions.append((partition.partition, free_bytes))
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type=event_type,
        metadata={"partitions": partitions_payload},
        occurred_at=occurred_at,
    )
    if low_free_partitions:
        details = ", ".join(
            f"{name}={free_bytes / (1024**3):.1f} GiB free"
            for name, free_bytes in low_free_partitions
        )
        message = f"Low disk space detected for run {run_id}: {details}"
        logger.warning(message)
        sentry_sdk.capture_message(message, level="warning")


# -----------------------------------------------------------------------------
# Webhook Endpoints
# -----------------------------------------------------------------------------


def _next_stream_event_id() -> int:
    return int(time.time() * 1000)


@router.post("/{run_id}/stage-progress", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_stage_progress(
    run_id: str,
    payload: StageProgressPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    logger.debug(
        "RP stage progress: run=%s stage=%s iteration=%s/%s progress=%.3f",
        run_id,
        event.stage,
        event.iteration,
        event.max_iterations,
        event.progress,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    progress = ResearchRunStageProgress(
        stage=event.stage,
        iteration=event.iteration,
        max_iterations=event.max_iterations,
        progress=event.progress,
        total_nodes=event.total_nodes,
        buggy_nodes=event.buggy_nodes,
        good_nodes=event.good_nodes,
        best_metric=event.best_metric,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=run_id,
        event=SSEStageProgressEvent(
            type="stage_progress",
            data=progress,
        ),
    )

    # Narrator: Ingest event for timeline
    await ingest_narration_event(
        db,
        run_id=run_id,
        event_type="stage_progress",
        event_data=event,
    )

    # Persist to database
    await db.insert_stage_progress_event(
        run_id=run_id,
        stage=event.stage,
        iteration=event.iteration,
        max_iterations=event.max_iterations,
        progress=event.progress,
        total_nodes=event.total_nodes,
        buggy_nodes=event.buggy_nodes,
        good_nodes=event.good_nodes,
        best_metric=event.best_metric,
        is_seed_node=event.is_seed_node,
    )


@router.post("/{run_id}/substage-completed", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_substage_completed(
    run_id: str,
    payload: SubstageCompletedPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    logger.debug(
        "RP sub-stage completed: run=%s stage=%s reason=%s",
        run_id,
        event.stage,
        event.reason,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    summary = dict(event.summary)
    summary.setdefault("main_stage_number", event.main_stage_number)
    summary.setdefault("reason", event.reason)
    substage_event = RPSubstageEvent(
        id=_next_stream_event_id(),
        stage=event.stage,
        node_id=None,
        summary=summary,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=run_id,
        event=cast(
            StreamEventModel,
            ResearchRunSubstageCompletedEvent(
                type="substage_completed",
                data=substage_event,
            ),
        ),
    )

    # Narrator: Ingest event for timeline
    await ingest_narration_event(
        db,
        run_id=run_id,
        event_type="substage_completed",
        event_data=event,
    )

    # Persist to database (summary already contains main_stage_number and reason)
    await db.insert_substage_completed_event(
        run_id=run_id,
        stage=event.stage,
        summary=summary,
    )


@router.post("/{run_id}/paper-generation-progress", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_paper_generation_progress(
    run_id: str,
    payload: PaperGenerationProgressPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    logger.debug(
        "Paper generation progress: run=%s step=%s substep=%s progress=%.1f%% step_progress=%.1f%%",
        run_id,
        event.step,
        event.substep or "N/A",
        event.progress * 100,
        event.step_progress * 100,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    paper_event = ResearchRunPaperGenerationProgress(
        id=_next_stream_event_id(),
        run_id=run_id,
        step=event.step,
        substep=event.substep,
        progress=event.progress,
        step_progress=event.step_progress,
        details=event.details,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=run_id,
        event=SSEPaperGenerationEvent(
            type="paper_generation_progress",
            data=paper_event,
        ),
    )

    # Narrator: Ingest event for timeline
    await ingest_narration_event(
        db,
        run_id=run_id,
        event_type="paper_generation_progress",
        event_data=event,
    )

    # Persist to database
    await db.insert_paper_generation_event(
        run_id=run_id,
        step=event.step,
        substep=event.substep,
        progress=event.progress,
        step_progress=event.step_progress,
        details=event.details,
    )


@router.post("/{run_id}/artifact-uploaded", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_artifact_uploaded(
    run_id: str,
    payload: ArtifactUploadedPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event

    # Reconstruct s3_key (same pattern as in artifact_manager.py)
    s3_key = f"research-pipeline/{run_id}/{event.artifact_type}/{event.filename}"

    # Persist to database (upsert based on s3_key)
    created_at_dt = datetime.fromisoformat(event.created_at.replace("Z", "+00:00"))
    artifact_id, db_created_at = await db.upsert_artifact(
        run_id=run_id,
        artifact_type=event.artifact_type,
        filename=event.filename,
        file_size=event.file_size,
        file_type=event.file_type,
        s3_key=s3_key,
        source_path=None,  # Not included in webhook payload
        created_at=created_at_dt,
    )

    logger.debug(
        "Artifact uploaded: run=%s type=%s filename=%s size=%d artifact_id=%d",
        run_id,
        event.artifact_type,
        event.filename,
        event.file_size,
        artifact_id,
    )

    artifact_metadata = ResearchRunArtifactMetadata(
        id=artifact_id,
        artifact_type=event.artifact_type,
        filename=event.filename,
        file_size=event.file_size,
        file_type=event.file_type,
        created_at=event.created_at,
        run_id=run_id,
        conversation_id=None,
    )
    publish_stream_event(
        run_id=run_id,
        event=SSEArtifactEvent(
            type="artifact",
            data=artifact_metadata,
        ),
    )


@router.post("/{run_id}/review-completed", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_review_completed(
    run_id: str,
    payload: ReviewCompletedPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event

    logger.debug(
        "Review completed: run=%s decision=%s overall=%.2f",
        run_id,
        event.decision,
        event.overall,
    )

    # Persist to database first to get the database-generated review_id
    review_id = await db.insert_llm_review(
        run_id=run_id,
        summary=event.summary,
        strengths=event.strengths,
        weaknesses=event.weaknesses,
        originality=event.originality,
        quality=event.quality,
        clarity=event.clarity,
        significance=event.significance,
        questions=event.questions,
        limitations=event.limitations,
        ethical_concerns=event.ethical_concerns,
        soundness=event.soundness,
        presentation=event.presentation,
        contribution=event.contribution,
        overall=event.overall,
        confidence=event.confidence,
        decision=event.decision,
        source_path=event.source_path,
        created_at=datetime.fromisoformat(event.created_at.replace("Z", "+00:00")),
    )

    # Create LlmReviewResponse for SSE using database-generated review_id
    review_data = LlmReviewResponse(
        id=review_id,
        run_id=run_id,
        summary=event.summary,
        strengths=event.strengths,
        weaknesses=event.weaknesses,
        originality=event.originality,
        quality=event.quality,
        clarity=event.clarity,
        significance=event.significance,
        questions=event.questions,
        limitations=event.limitations,
        ethical_concerns=event.ethical_concerns,
        soundness=event.soundness,
        presentation=event.presentation,
        contribution=event.contribution,
        overall=event.overall,
        confidence=event.confidence,
        decision=event.decision,
        source_path=event.source_path,
        created_at=event.created_at,
    )

    publish_stream_event(
        run_id=run_id,
        event=SSEReviewCompletedEvent(
            type="review_completed",
            data=review_data,
        ),
    )


@router.post("/{run_id}/substage-summary", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_substage_summary(
    run_id: str,
    payload: SubstageSummaryPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    logger.debug(
        "RP sub-stage summary: run=%s stage=%s",
        run_id,
        event.stage,
    )
    now = datetime.now(timezone.utc)
    created_at = now.isoformat()
    summary_model = ResearchRunSubstageSummary(
        id=_next_stream_event_id(),
        stage=event.stage,
        summary=event.summary,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=run_id,
        event=SSESubstageSummaryEvent(
            type="substage_summary",
            data=summary_model,
        ),
    )

    # Persist to database
    await db.insert_substage_summary_event(
        run_id=run_id,
        stage=event.stage,
        summary=event.summary,
        created_at=now,
    )


@router.post("/{run_id}/stage-skip-window", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_stage_skip_window(
    run_id: str,
    payload: StageSkipWindowPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event = payload.event
    logger.debug(
        "RP stage skip window event: run=%s stage=%s state=%s reason=%s",
        run_id,
        event.stage,
        event.state,
        event.reason,
    )
    publish_stream_event(
        run_id=run_id,
        event=cast(
            StreamEventModel,
            SSEStageSkipWindowEvent(
                type="stage_skip_window",
                data=ResearchRunStageSkipWindowUpdate(
                    stage=event.stage,
                    state=event.state,
                    timestamp=event.timestamp,
                    reason=event.reason,
                ),
            ),
        ),
    )

    # Persist to database
    await cast(DatabaseManager, db).upsert_stage_skip_window(
        run_id=run_id,
        stage=event.stage,
        state=event.state,
        timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
        reason=event.reason,
    )


@router.post("/{run_id}/tree-viz-stored", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_tree_viz_stored(
    run_id: str,
    payload: TreeVizStoredPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event

    # Persist to database
    tree_viz_id = await db.upsert_tree_viz(
        run_id=run_id,
        stage_id=event.stage_id,
        viz=event.viz,
        version=event.version,
    )

    logger.debug(
        "Tree viz stored: run=%s stage=%s tree_viz_id=%s version=%s",
        run_id,
        event.stage_id,
        tree_viz_id,
        event.version,
    )
    created_at = datetime.now(timezone.utc).isoformat()

    # Create run event for SSE streaming
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=run_id,
        event_type="tree_viz_stored",
        metadata={
            "stage_id": event.stage_id,
            "tree_viz_id": tree_viz_id,
            "version": event.version,
        },
        occurred_at=created_at,
    )

    # Publish to SSE stream
    publish_stream_event(
        run_id=run_id,
        event=SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )


@router.post("/{run_id}/run-log", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_log(
    run_id: str,
    payload: RunLogPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    logger.debug(
        "RP log event received: run=%s level=%s message=%s",
        run_id,
        payload.event.level,
        payload.event.message,
    )
    # Persist to database
    await cast(DatabaseManager, db).insert_run_log_event(
        run_id=run_id,
        level=payload.event.level,
        message=payload.event.message,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/{run_id}/codex-event", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_codex_event(
    run_id: str,
    payload: CodexEventPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    logger.debug("RP codex event received: run=%s event=%s", run_id, payload.event)

    # Persist to database
    event_data = payload.event
    await db.insert_codex_event(
        run_id=run_id,
        stage=event_data.get("stage", ""),
        node=event_data.get("node", 0),
        event_type=event_data.get("event_type", ""),
        event_content=event_data,
    )


@router.post("/{run_id}/running-code", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_running_code(
    run_id: str,
    payload: RunningCodePayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event = payload.event
    publish_stream_event(
        run_id=run_id,
        event=cast(
            StreamEventModel,
            SSECodeExecutionStartedEvent(
                type="code_execution_started",
                data=ResearchRunCodeExecutionStartedData(
                    execution_id=event.execution_id,
                    stage_name=event.stage_name,
                    run_type=event.run_type,
                    code=event.code,
                    started_at=event.started_at,
                ),
            ),
        ),
    )

    # Ingest into narrator
    await ingest_narration_event(
        cast(DatabaseManager, db),
        run_id=run_id,
        event_type="running_code",
        event_data=event,
    )

    # Persist to database (status defaults to "running")
    await cast(DatabaseManager, db).upsert_code_execution_event(
        run_id=run_id,
        execution_id=event.execution_id,
        stage_name=event.stage_name,
        run_type=event.run_type,
        execution_type=event.execution_type.value,
        code=event.code,
        started_at=datetime.fromisoformat(event.started_at.replace("Z", "+00:00")),
        node_index=event.node_index,
    )


@router.post("/{run_id}/run-completed", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_completed(
    run_id: str,
    payload: RunCompletedPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event = payload.event
    publish_stream_event(
        run_id=run_id,
        event=cast(
            StreamEventModel,
            SSECodeExecutionCompletedEvent(
                type="code_execution_completed",
                data=ResearchRunCodeExecutionCompletedData(
                    execution_id=event.execution_id,
                    stage_name=event.stage_name,
                    run_type=event.run_type,
                    status=event.status,
                    exec_time=event.exec_time,
                    completed_at=event.completed_at,
                ),
            ),
        ),
    )

    # Ingest into narrator
    await ingest_narration_event(
        cast(DatabaseManager, db),
        run_id=run_id,
        event_type="run_completed",
        event_data=event,
    )

    # Persist to database (updates the existing record with completion data)
    await cast(DatabaseManager, db).upsert_code_execution_event(
        run_id=run_id,
        execution_id=event.execution_id,
        stage_name=event.stage_name,
        run_type=event.run_type,
        execution_type=event.execution_type.value,
        status=event.status,
        exec_time=event.exec_time,
        completed_at=datetime.fromisoformat(event.completed_at.replace("Z", "+00:00")),
        node_index=event.node_index,
    )


@router.post("/{run_id}/run-started", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_started(
    run_id: str,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    now = datetime.now(timezone.utc)
    new_deadline = now + timedelta(minutes=5)
    await db.update_research_pipeline_run(
        run_id=run_id,
        status="running",
        initialization_status="running",
        last_heartbeat_at=now,
        heartbeat_failures=0,
        start_deadline_at=new_deadline,
        started_running_at=now,
    )
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "running",
            "reason": "pipeline_event_start",
            "start_deadline_at": new_deadline.isoformat(),
        },
        occurred_at=now,
    )
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "running",
            "reason": "pipeline_event_start",
            "start_deadline_at": new_deadline.isoformat(),
        },
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )

    # Ingest into narrator to update state with started_running_at
    await ingest_narration_event(
        cast(DatabaseManager, db),
        run_id=run_id,
        event_type="run_started",
        event_data=RunStartedEventData(
            started_running_at=now.isoformat(),
            gpu_type=run.gpu_type,
            cost_per_hour_cents=int(run.cost * 100) if run.cost else None,
        ),
    )

    logger.debug("RP run started: run=%s", run_id)


@router.post("/{run_id}/initialization-progress", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_initialization_progress(
    run_id: str,
    payload: InitializationProgressPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    now = datetime.now(timezone.utc)
    message = payload.message.strip()
    await db.update_research_pipeline_run(
        run_id=run_id,
        initialization_status=message,
    )
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="initialization_progress",
        metadata={"initialization_status": message},
        occurred_at=now,
    )
    publish_stream_event(
        run_id,
        SSEInitializationStatusEvent(
            type="initialization_status",
            data=ResearchRunInitializationStatusData(
                initialization_status=message,
                updated_at=now.isoformat(),
            ),
        ),
    )
    logger.debug("RP initialization progress: run=%s status=%s", run_id, message)


@router.post("/{run_id}/run-finished", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_finished(
    run_id: str,
    payload: RunFinishedPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    new_status = "completed" if payload.success else "failed"
    now = datetime.now(timezone.utc)
    await db.update_research_pipeline_run(
        run_id=run_id,
        status=new_status,
        error_message=payload.message,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": new_status,
            "reason": "pipeline_event_finish",
            "success": payload.success,
            "message": payload.message,
        },
        occurred_at=now,
    )
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": new_status,
            "reason": "pipeline_event_finish",
            "success": payload.success,
            "message": payload.message,
        },
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )

    # Ingest into narrator for timeline and queue cleanup
    await ingest_narration_event(
        cast(DatabaseManager, db),
        run_id=run_id,
        event_type="run_finished",
        event_data=RunFinishedEventData(
            success=payload.success,
            status=new_status,
            message=payload.message,
            reason="pipeline_event_finish",
        ),
    )

    termination = await db.enqueue_research_pipeline_run_termination(
        run_id=run_id,
        trigger="pipeline_event_finish",
    )
    publish_termination_status_event(run_id=run_id, termination=termination)
    notify_termination_requested()


@router.post("/{run_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_heartbeat(
    run_id: str,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        logger.warning(
            "Received heartbeat for unknown run_id=%s; ignoring but returning 204.",
            run_id,
        )
        return
    now = datetime.now(timezone.utc)
    await db.update_research_pipeline_run(
        run_id=run_id,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
    logger.debug("RP heartbeat received for run=%s", run_id)


@router.post("/{run_id}/hw-stats", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_hw_stats(
    run_id: str,
    payload: HardwareStatsPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        logger.warning(
            "Received hardware stats for unknown run_id=%s; ignoring but returning 204.",
            run_id,
        )
        return
    now = datetime.now(timezone.utc)
    resolved_partitions: list[DiskUsagePartition] = []
    for partition in payload.partitions:
        total_bytes = resolve_partition_capacity_bytes(
            container_disk_gb=run.container_disk_gb,
            volume_disk_gb=run.volume_disk_gb,
            partition=partition.partition,
        )
        if total_bytes is None:
            logger.debug(
                "Skipping hw_stats partition without capacity mapping: run=%s partition=%s",
                run_id,
                partition.partition,
            )
            continue
        resolved_partitions.append(
            DiskUsagePartition(
                partition=partition.partition,
                total_bytes=total_bytes,
                used_bytes=partition.used_bytes,
            )
        )
    if not resolved_partitions:
        logger.debug(
            "No recognized partitions in hw_stats payload for run=%s; skipping record.",
            run_id,
        )
        return
    await record_disk_usage_event(
        db=db,
        run_id=run_id,
        partitions=resolved_partitions,
        occurred_at=now,
        event_type="hw_stats",
    )
    logger.debug("RP hardware stats received for run=%s", run_id)


@router.post("/{run_id}/gpu-shortage", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_gpu_shortage(
    run_id: str,
    payload: GPUShortagePayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    failure_reason = (
        payload.message
        or f"Pipeline aborted: requires {payload.required_gpus} GPU(s) but detected {payload.available_gpus}."
    )
    now = datetime.now(timezone.utc)
    logger.warning(
        "RP GPU shortage: run=%s required=%s available=%s",
        run_id,
        payload.required_gpus,
        payload.available_gpus,
    )

    # Record the GPU shortage event
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="gpu_shortage",
        metadata={
            "required_gpus": payload.required_gpus,
            "available_gpus": payload.available_gpus,
            "message": failure_reason,
        },
        occurred_at=now,
    )

    # Attempt to restart with any available GPU type
    webhook_token, webhook_token_hash = generate_run_webhook_token()
    restarted = await attempt_pod_restart(
        db=db,
        run=run,
        reason="gpu_shortage",
        gpu_types=get_supported_gpu_types(),
        webhook_token=webhook_token,
        webhook_token_hash=webhook_token_hash,
    )

    if not restarted:
        # Max restart attempts exceeded - fail the run permanently
        await db.update_research_pipeline_run(
            run_id=run_id,
            status="failed",
            error_message=f"{failure_reason} (after {run.restart_count} restart attempt(s))",
            last_heartbeat_at=now,
            heartbeat_failures=0,
        )
        await db.insert_research_pipeline_run_event(
            run_id=run_id,
            event_type="status_changed",
            metadata={
                "from_status": run.status,
                "to_status": "failed",
                "reason": "gpu_shortage",
                "message": failure_reason,
            },
            occurred_at=now,
        )
        termination = await db.enqueue_research_pipeline_run_termination(
            run_id=run_id,
            trigger="gpu_shortage",
        )
        publish_termination_status_event(run_id=run_id, termination=termination)
        notify_termination_requested()


@router.post("/{run_id}/token-usage", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_token_usage(
    run_id: str,
    payload: TokenUsagePayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    logger.debug(
        "Token usage: run=%s model=%s input=%s output=%s",
        run_id,
        event.model,
        event.input_tokens,
        event.output_tokens,
    )

    # Look up conversation_id from run_id
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        logger.warning(
            "Cannot track token usage: run_id=%s not found",
            run_id,
        )
        return
    # Get conversation_id via idea_id
    idea_version = await db.get_idea_version_by_id(run.idea_version_id)
    if idea_version is None:
        logger.warning(
            "Cannot track token usage: idea_version_id=%s not found",
            run.idea_version_id,
        )
        return
    conversation_id = idea_version.conversation_id

    model_name, provider = extract_model_name_and_provider(event.model)

    # Insert into database
    await db.create_llm_token_usage(
        conversation_id=conversation_id,
        provider=provider,
        model=model_name,
        input_tokens=event.input_tokens,
        cached_input_tokens=event.cached_input_tokens,
        output_tokens=event.output_tokens,
        run_id=run_id,
    )

    # Charge user for LLM usage (separate from GPU costs)
    user_id = await db.get_run_owner_user_id(run_id)
    if user_id:
        await charge_for_llm_usage(
            conversation_id=conversation_id,
            provider=provider,
            model=model_name,
            input_tokens=event.input_tokens,
            cached_input_tokens=event.cached_input_tokens,
            output_tokens=event.output_tokens,
            user_id=user_id,
            description=f"Research run {run_id}",
            run_id=run_id,
        )


@router.post("/{run_id}/figure-reviews", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_figure_reviews(
    run_id: str,
    payload: FigureReviewsPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    logger.debug(
        "Figure reviews: run=%s count=%s",
        run_id,
        len(payload.event.reviews),
    )

    # Convert pydantic models to dicts for database insertion
    reviews_data = [
        {
            "figure_name": review.figure_name,
            "img_description": review.img_description,
            "img_review": review.img_review,
            "caption_review": review.caption_review,
            "figrefs_review": review.figrefs_review,
            "source_path": review.source_path,
        }
        for review in payload.event.reviews
    ]

    # Insert into database
    await db.insert_vlm_figure_reviews(
        run_id=run_id,
        reviews=reviews_data,
    )
