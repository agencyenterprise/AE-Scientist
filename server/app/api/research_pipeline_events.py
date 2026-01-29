import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Protocol, Sequence, cast

import sentry_sdk
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.research_pipeline_runs import (
    REQUESTER_NAME_FALLBACK,
    IdeaPayloadSource,
    PodLaunchError,
    create_and_launch_research_run,
    extract_user_first_name,
)
from app.api.research_pipeline_stream import StreamEventModel, publish_stream_event
from app.models.research_pipeline import (
    LlmReviewResponse,
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
)
from app.models.research_pipeline import ResearchRunEvent as RPEvent
from app.models.research_pipeline import (
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
)
from app.models.research_pipeline import ResearchRunSubstageEvent as RPSubstageEvent
from app.models.research_pipeline import ResearchRunSubstageSummary, RunType
from app.models.sse import ResearchRunArtifactEvent as SSEArtifactEvent
from app.models.sse import ResearchRunBestNodeEvent as SSEBestNodeEvent
from app.models.sse import ResearchRunCodeExecutionCompletedData
from app.models.sse import ResearchRunCodeExecutionCompletedEvent as SSECodeExecutionCompletedEvent
from app.models.sse import ResearchRunCodeExecutionStartedData
from app.models.sse import ResearchRunCodeExecutionStartedEvent as SSECodeExecutionStartedEvent
from app.models.sse import ResearchRunInitializationStatusData
from app.models.sse import ResearchRunInitializationStatusEvent as SSEInitializationStatusEvent
from app.models.sse import ResearchRunLogEvent as SSELogEvent
from app.models.sse import ResearchRunPaperGenerationEvent as SSEPaperGenerationEvent
from app.models.sse import ResearchRunReviewCompletedEvent as SSEReviewCompletedEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.sse import ResearchRunStageProgressEvent as SSEStageProgressEvent
from app.models.sse import ResearchRunStageSkipWindowEvent as SSEStageSkipWindowEvent
from app.models.sse import ResearchRunStageSkipWindowUpdate, ResearchRunSubstageCompletedEvent
from app.models.sse import ResearchRunSubstageSummaryEvent as SSESubstageSummaryEvent
from app.services import DatabaseManager, get_database
from app.services.database.ideas import IdeaVersionData
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import PodUpdateInfo, ResearchPipelineRun
from app.services.database.users import UserData
from app.services.narrator.narrator_service import ingest_narration_event
from app.services.research_pipeline.pod_termination_worker import (
    notify_termination_requested,
    publish_termination_status_event,
)
from app.services.research_pipeline.runpod import get_supported_gpu_types
from app.services.research_pipeline.runpod.runpod_initialization import WORKSPACE_PATH
from app.services.s3_service import get_s3_service


class ResearchRunStore(Protocol):
    async def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]: ...

    async def get_run_webhook_token_hash(self, run_id: str) -> Optional[str]: ...

    async def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
        initialization_status: Optional[str] = None,
        pod_update_info: Optional[PodUpdateInfo] = None,
        error_message: Optional[str] = None,
        last_heartbeat_at: Optional[datetime] = None,
        heartbeat_failures: Optional[int] = None,
        start_deadline_at: Optional[datetime] = None,
        last_billed_at: Optional[datetime] = None,
        started_running_at: Optional[datetime] = None,
    ) -> None: ...

    async def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: Dict[str, object],
        occurred_at: datetime,
    ) -> None: ...

    async def enqueue_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        trigger: str,
    ) -> ResearchPipelineRunTermination: ...

    async def get_run_owner_user_id(self, run_id: str) -> Optional[int]: ...

    async def get_user_by_id(self, user_id: int) -> Optional[UserData]: ...

    async def get_idea_version_by_id(self, idea_version_id: int) -> Optional[IdeaVersionData]: ...

    async def get_conversation_parent_run_id(self, conversation_id: int) -> Optional[str]: ...


router = APIRouter(prefix="/research-pipeline/events", tags=["research-pipeline-events"])
logger = logging.getLogger(__name__)


class StageProgressEvent(BaseModel):
    stage: str
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str] = None
    eta_s: Optional[int] = None
    latest_iteration_time_s: Optional[int] = None


class StageProgressPayload(BaseModel):
    event: StageProgressEvent


class SubstageCompletedEvent(BaseModel):
    stage: str
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]


class SubstageCompletedPayload(BaseModel):
    event: SubstageCompletedEvent


class SubstageSummaryEvent(BaseModel):
    stage: str
    summary: Dict[str, Any]


class SubstageSummaryPayload(BaseModel):
    event: SubstageSummaryEvent


class RunStartedPayload(BaseModel):
    pass


class RunFinishedPayload(BaseModel):
    success: bool
    message: Optional[str] = None


class InitializationProgressPayload(BaseModel):
    message: str


class DiskUsagePartition(BaseModel):
    partition: str
    total_bytes: int
    used_bytes: int


class HardwareStatsPartition(BaseModel):
    partition: str
    used_bytes: int


class HeartbeatPayload(BaseModel):
    pass


class HardwareStatsPayload(BaseModel):
    partitions: List[HardwareStatsPartition] = Field(default_factory=list)


LOW_FREE_DISK_THRESHOLD_BYTES = 50 * 1024**3
BYTES_PER_GB = 1024**3


def _resolve_partition_capacity_bytes(
    *,
    run: ResearchPipelineRun,
    partition: str,
) -> Optional[int]:
    normalized = partition if partition == "/" else partition.rstrip("/")
    if not normalized:
        normalized = "/"
    if normalized == "/":
        capacity_gb = run.container_disk_gb
    elif normalized == WORKSPACE_PATH:
        capacity_gb = run.volume_disk_gb
    else:
        return None
    if capacity_gb is None:
        return None
    return int(capacity_gb) * BYTES_PER_GB


class GPUShortagePayload(BaseModel):
    required_gpus: int
    available_gpus: int
    message: Optional[str] = None


class PaperGenerationProgressEvent(BaseModel):
    step: str
    substep: Optional[str] = None
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]] = None


class PaperGenerationProgressPayload(BaseModel):
    event: PaperGenerationProgressEvent


class ArtifactUploadedEvent(BaseModel):
    artifact_type: str
    filename: str
    file_size: int
    file_type: str
    created_at: str


class ArtifactUploadedPayload(BaseModel):
    event: ArtifactUploadedEvent


class ReviewCompletedEvent(BaseModel):
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    originality: float
    quality: float
    clarity: float
    significance: float
    questions: List[str]
    limitations: List[str]
    ethical_concerns: bool
    soundness: float
    presentation: float
    contribution: float
    overall: float
    confidence: float
    decision: str
    source_path: Optional[str]
    created_at: str


class ReviewCompletedPayload(BaseModel):
    event: ReviewCompletedEvent


class BestNodeSelectionEvent(BaseModel):
    stage: str
    node_id: str
    reasoning: str


class BestNodeSelectionPayload(BaseModel):
    event: BestNodeSelectionEvent


class StageSkipWindowEventModel(BaseModel):
    stage: str
    state: Literal["opened", "closed"]
    timestamp: str
    reason: Optional[str] = None


class StageSkipWindowPayload(BaseModel):
    event: StageSkipWindowEventModel


class TreeVizStoredEvent(BaseModel):
    stage_id: str
    version: int
    viz: Dict[str, Any]


class TreeVizStoredPayload(BaseModel):
    event: TreeVizStoredEvent


class RunLogEvent(BaseModel):
    message: str
    level: str = "info"


class RunLogPayload(BaseModel):
    event: RunLogEvent


class CodexEventPayload(BaseModel):
    event: dict[str, Any]


class RunningCodeEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    code: str
    started_at: str
    run_type: RunType


class RunningCodePayload(BaseModel):
    event: RunningCodeEventPayload


class RunCompletedEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: str
    run_type: RunType


class RunCompletedPayload(BaseModel):
    event: RunCompletedEventPayload


class TokenUsageEvent(BaseModel):
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class TokenUsagePayload(BaseModel):
    event: TokenUsageEvent


class FigureReviewEvent(BaseModel):
    figure_name: str
    img_description: str
    img_review: str
    caption_review: str
    figrefs_review: str
    source_path: Optional[str] = None


class FigureReviewsEvent(BaseModel):
    """Event containing multiple figure reviews."""

    reviews: List[FigureReviewEvent]


class FigureReviewsPayload(BaseModel):
    event: FigureReviewsEvent


class PresignedUploadUrlRequest(BaseModel):
    artifact_type: str
    filename: str
    content_type: str
    file_size: int
    metadata: Optional[Dict[str, str]] = None


class PresignedUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int


class MultipartUploadInitRequest(BaseModel):
    """Request to initiate a multipart upload."""

    artifact_type: str
    filename: str
    content_type: str
    file_size: int
    part_size: int = Field(description="Size of each part in bytes")
    num_parts: int = Field(description="Total number of parts")
    metadata: Optional[Dict[str, str]] = None


class MultipartUploadPartUrl(BaseModel):
    """Presigned URL for uploading a single part."""

    part_number: int
    upload_url: str


class MultipartUploadInitResponse(BaseModel):
    """Response with multipart upload initiation details."""

    upload_id: str
    s3_key: str
    part_urls: List[MultipartUploadPartUrl]
    expires_in: int


class MultipartUploadPart(BaseModel):
    """Completed part information for multipart upload completion."""

    part_number: int = Field(alias="PartNumber")
    etag: str = Field(alias="ETag")

    class Config:
        populate_by_name = True


class MultipartUploadCompleteRequest(BaseModel):
    """Request to complete a multipart upload."""

    upload_id: str
    s3_key: str
    parts: List[MultipartUploadPart]
    artifact_type: str
    filename: str
    file_size: int
    content_type: str


class MultipartUploadCompleteResponse(BaseModel):
    """Response after completing a multipart upload."""

    s3_key: str
    success: bool


class MultipartUploadAbortRequest(BaseModel):
    """Request to abort a multipart upload."""

    upload_id: str
    s3_key: str


class ParentRunFileInfo(BaseModel):
    s3_key: str
    filename: str
    size: int
    download_url: str


class ParentRunFilesRequest(BaseModel):
    parent_run_id: str


class ParentRunFilesResponse(BaseModel):
    files: List[ParentRunFileInfo]
    expires_in: int


class DatasetFileInfo(BaseModel):
    s3_key: str
    relative_path: str
    size: int
    download_url: str


class ListDatasetsRequest(BaseModel):
    datasets_folder: str


class ListDatasetsResponse(BaseModel):
    files: List[DatasetFileInfo]
    expires_in: int


class DatasetUploadUrlRequest(BaseModel):
    datasets_folder: str
    relative_path: str
    content_type: str
    file_size: int


class DatasetUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int


async def _verify_run_token(run_id: str, token: str) -> None:
    """Verify the bearer token for a specific run.

    Validates against the per-run token hash stored in the database.
    """
    db = cast("ResearchRunStore", get_database())
    stored_hash = await db.get_run_webhook_token_hash(run_id)

    if stored_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token configured for this run.",
        )

    provided_hash = hashlib.sha256(token.encode()).hexdigest()
    if provided_hash != stored_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
        )


async def verify_run_auth(
    run_id: str,
    authorization: str = Header(...),
) -> None:
    """FastAPI dependency that extracts and verifies the bearer token for a run.

    This combines token extraction and verification into a single dependency,
    eliminating the need for separate _extract_bearer_token and _verify_run_token calls.

    Usage:
        @router.post("/{run_id}/endpoint")
        async def my_endpoint(
            run_id: str,
            _: None = Depends(verify_run_auth),
        ) -> None:
            ...
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format.",
        )
    await _verify_run_token(run_id, token)


async def _resolve_run_owner_first_name(*, db: "ResearchRunStore", run_id: str) -> str:
    owner_id = await db.get_run_owner_user_id(run_id=run_id)
    if owner_id is None:
        return REQUESTER_NAME_FALLBACK
    user = await db.get_user_by_id(user_id=owner_id)
    if user is None:
        return REQUESTER_NAME_FALLBACK
    return extract_user_first_name(full_name=user.name)


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
        eta_s=event.eta_s,
        latest_iteration_time_s=event.latest_iteration_time_s,
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
        event_data=event.model_dump(),
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
        eta_s=event.eta_s,
        latest_iteration_time_s=event.latest_iteration_time_s,
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
        event_data=event.model_dump(),
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
        event_data=event.model_dump(),
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


@router.post("/{run_id}/best-node-selection", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_best_node_selection(
    run_id: str,
    payload: BestNodeSelectionPayload,
    _: None = Depends(verify_run_auth),
    db: DatabaseManager = Depends(get_database),
) -> None:
    event = payload.event
    reasoning_preview = (
        event.reasoning if len(event.reasoning) <= 200 else f"{event.reasoning[:197]}..."
    )
    logger.debug(
        "RP best-node selection: run=%s stage=%s node=%s reasoning=%s",
        run_id,
        event.stage,
        event.node_id,
        reasoning_preview,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    best_node = ResearchRunBestNodeSelection(
        id=_next_stream_event_id(),
        stage=event.stage,
        node_id=event.node_id,
        reasoning=event.reasoning,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=run_id,
        event=SSEBestNodeEvent(
            type="best_node_selection",
            data=best_node,
        ),
    )

    # Narrator: Ingest event for timeline
    await ingest_narration_event(
        db,
        run_id=run_id,
        event_type="best_node_selection",
        event_data=event.model_dump(),
    )

    # Persist to database
    await db.insert_best_node_reasoning_event(
        run_id=run_id,
        stage=event.stage,
        node_id=event.node_id,
        reasoning=event.reasoning,
    )


@router.post("/{run_id}/stage-skip-window", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_stage_skip_window(
    run_id: str,
    payload: StageSkipWindowPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast("ResearchRunStore", get_database())
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
    payload: "TreeVizStoredPayload",
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
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    logger.debug(
        "RP log event received: run=%s level=%s message=%s",
        run_id,
        payload.event.level,
        payload.event.message,
    )
    now = datetime.now(timezone.utc)
    publish_stream_event(
        run_id=run_id,
        event=SSELogEvent(
            type="log",
            data=ResearchRunLogEntry(
                id=_next_stream_event_id(),
                level=payload.event.level,
                message=payload.event.message,
                created_at=now.isoformat(),
            ),
        ),
    )

    # Persist to database
    await cast(DatabaseManager, db).insert_run_log_event(
        run_id=run_id,
        level=payload.event.level,
        message=payload.event.message,
        created_at=now,
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
    db = cast("ResearchRunStore", get_database())
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
        event_data=event.model_dump(),
    )

    # Persist to database (status defaults to "running")
    await cast(DatabaseManager, db).upsert_code_execution_event(
        run_id=run_id,
        execution_id=event.execution_id,
        stage_name=event.stage_name,
        run_type=event.run_type,
        code=event.code,
        started_at=datetime.fromisoformat(event.started_at.replace("Z", "+00:00")),
    )


@router.post("/{run_id}/run-completed", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_completed(
    run_id: str,
    payload: RunCompletedPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast("ResearchRunStore", get_database())
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
        event_data=event.model_dump(),
    )

    # Persist to database (updates the existing record with completion data)
    await cast(DatabaseManager, db).upsert_code_execution_event(
        run_id=run_id,
        execution_id=event.execution_id,
        stage_name=event.stage_name,
        run_type=event.run_type,
        status=event.status,
        exec_time=event.exec_time,
        completed_at=datetime.fromisoformat(event.completed_at.replace("Z", "+00:00")),
    )


@router.post("/{run_id}/run-started", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_run_started(
    run_id: str,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast("ResearchRunStore", get_database())
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
        event_data={
            "started_running_at": now.isoformat(),
            "gpu_type": run.gpu_type,
            "cost_per_hour_cents": int(run.cost * 100) if run.cost else None,
        },
    )

    logger.debug("RP run started: run=%s", run_id)


@router.post("/{run_id}/initialization-progress", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_initialization_progress(
    run_id: str,
    payload: InitializationProgressPayload,
    _: None = Depends(verify_run_auth),
) -> None:
    db = cast("ResearchRunStore", get_database())
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
    db = cast("ResearchRunStore", get_database())
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
        event_data={
            "success": payload.success,
            "status": new_status,
            "message": payload.message,
        },
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
    db = cast("ResearchRunStore", get_database())
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
    db = cast("ResearchRunStore", get_database())
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
        total_bytes = _resolve_partition_capacity_bytes(
            run=run,
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
    await _record_disk_usage_event(
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
) -> None:
    db = cast("ResearchRunStore", get_database())
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
    await db.update_research_pipeline_run(
        run_id=run_id,
        status="failed",
        error_message=failure_reason,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
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
    await _retry_run_after_gpu_shortage(db=db, failed_run=run)


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

    # Insert into database
    await db.create_llm_token_usage(
        conversation_id=conversation_id,
        provider=event.provider,
        model=event.model,
        input_tokens=event.input_tokens,
        cached_input_tokens=event.cached_input_tokens,
        output_tokens=event.output_tokens,
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


async def _record_disk_usage_event(
    *,
    db: ResearchRunStore,
    run_id: str,
    partitions: Sequence[DiskUsagePartition],
    occurred_at: datetime,
    event_type: str,
) -> None:
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


async def _retry_run_after_gpu_shortage(
    *, db: "ResearchRunStore", failed_run: ResearchPipelineRun
) -> None:
    version_id = failed_run.idea_version_id
    idea_version = await db.get_idea_version_by_id(version_id)
    if idea_version is None:
        logger.warning(
            "Cannot retry run %s after GPU shortage: idea version %s not found.",
            failed_run.run_id,
            version_id,
        )
        return
    idea_payload = RetryIdeaPayload(
        idea_id=idea_version.idea_id,
        version_id=idea_version.version_id,
        version_number=idea_version.version_number,
        title=idea_version.title,
        idea_markdown=idea_version.idea_markdown,
    )
    requester_first_name = await _resolve_run_owner_first_name(db=db, run_id=failed_run.run_id)
    retry_gpu_types = _build_retry_gpu_preferences(
        failed_run_gpu_type=failed_run.gpu_type, run_id=failed_run.run_id
    )

    # Get parent run ID if this conversation is seeded from a previous run
    parent_run_id = await db.get_conversation_parent_run_id(idea_version.conversation_id)

    try:
        new_run_id, _pod_info = await create_and_launch_research_run(
            idea_data=idea_payload,
            requested_by_first_name=requester_first_name,
            gpu_types=retry_gpu_types,
            conversation_id=idea_version.conversation_id,
            parent_run_id=parent_run_id,
        )
        logger.debug(
            "Scheduled retry run %s after GPU shortage on run %s.",
            new_run_id,
            failed_run.run_id,
        )
        await db.insert_research_pipeline_run_event(
            run_id=failed_run.run_id,
            event_type="gpu_shortage_retry",
            metadata={
                "retry_run_id": new_run_id,
                "reason": "gpu_shortage",
            },
            occurred_at=datetime.now(timezone.utc),
        )
    except PodLaunchError:
        logger.exception(
            "Failed to schedule retry run after GPU shortage for run %s", failed_run.run_id
        )
        return


def _build_retry_gpu_preferences(
    *, failed_run_gpu_type: str | None, run_id: str | None
) -> list[str]:
    """Return a GPU preference list that reuses the user's original choice when possible."""
    supported_gpu_types = get_supported_gpu_types()
    if not failed_run_gpu_type:
        logger.debug(
            "GPU shortage retry for run %s: no prior GPU recorded; using default list %s.",
            run_id,
            supported_gpu_types,
        )
        return supported_gpu_types

    if failed_run_gpu_type in supported_gpu_types:
        logger.debug(
            "GPU shortage retry for run %s: reusing original GPU type %s.",
            run_id,
            failed_run_gpu_type,
        )
        return [failed_run_gpu_type]

    # If the GPU has been removed from the supported list, still try it first before falling back.
    logger.debug(
        (
            "GPU shortage retry for run %s: requested GPU %s no longer in supported list; "
            "trying it first, then falling back to %s."
        ),
        run_id,
        failed_run_gpu_type,
        supported_gpu_types,
    )
    return [failed_run_gpu_type, *supported_gpu_types]


@dataclass(frozen=True)
class RetryIdeaPayload(IdeaPayloadSource):
    idea_id: int
    version_id: int
    version_number: int
    title: str
    idea_markdown: str


def _coerce_list(value: object) -> List[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


PRESIGNED_URL_EXPIRES_IN_SECONDS = 3600


@router.post("/{run_id}/presigned-upload-url", response_model=PresignedUploadUrlResponse)
async def get_presigned_upload_url(
    run_id: str,
    payload: PresignedUploadUrlRequest,
    _: None = Depends(verify_run_auth),
) -> PresignedUploadUrlResponse:
    """Generate a presigned URL for uploading an artifact to S3."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_key = f"research-pipeline/{run_id}/{payload.artifact_type}/{payload.filename}"

    metadata = {
        "run_id": run_id,
        "artifact_type": payload.artifact_type,
    }
    if payload.metadata:
        metadata.update(payload.metadata)

    s3_service = get_s3_service()
    upload_url = s3_service.generate_upload_url(
        s3_key=s3_key,
        content_type=payload.content_type,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        metadata=metadata,
    )

    logger.debug(
        "Generated presigned upload URL: run=%s type=%s filename=%s",
        run_id,
        payload.artifact_type,
        payload.filename,
    )

    return PresignedUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/multipart-upload-init", response_model=MultipartUploadInitResponse)
async def init_multipart_upload(
    run_id: str,
    payload: MultipartUploadInitRequest,
    _: None = Depends(verify_run_auth),
) -> MultipartUploadInitResponse:
    """Initiate a multipart upload for large files."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_key = f"research-pipeline/{run_id}/{payload.artifact_type}/{payload.filename}"

    metadata = {
        "run_id": run_id,
        "artifact_type": payload.artifact_type,
    }
    if payload.metadata:
        metadata.update(payload.metadata)

    s3_service = get_s3_service()

    # Create multipart upload
    upload_id = s3_service.create_multipart_upload(
        s3_key=s3_key,
        content_type=payload.content_type,
        metadata=metadata,
    )

    # Generate presigned URLs for all parts
    part_urls = []
    for part_num in range(1, payload.num_parts + 1):
        part_url = s3_service.generate_multipart_part_url(
            s3_key=s3_key,
            upload_id=upload_id,
            part_number=part_num,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        part_urls.append(MultipartUploadPartUrl(part_number=part_num, upload_url=part_url))

    logger.info(
        "Initiated multipart upload: run=%s type=%s filename=%s parts=%d upload_id=%s",
        run_id,
        payload.artifact_type,
        payload.filename,
        payload.num_parts,
        upload_id,
    )

    return MultipartUploadInitResponse(
        upload_id=upload_id,
        s3_key=s3_key,
        part_urls=part_urls,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/multipart-upload-complete", response_model=MultipartUploadCompleteResponse)
async def complete_multipart_upload(
    run_id: str,
    payload: MultipartUploadCompleteRequest,
    _: None = Depends(verify_run_auth),
) -> MultipartUploadCompleteResponse:
    """Complete a multipart upload."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()

    # Convert parts to format expected by S3
    parts: List[Dict[str, str | int]] = [
        {"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts
    ]

    try:
        s3_service.complete_multipart_upload(
            s3_key=payload.s3_key,
            upload_id=payload.upload_id,
            parts=parts,
        )
    except Exception as e:
        logger.error(
            "Failed to complete multipart upload: run=%s s3_key=%s error=%s",
            run_id,
            payload.s3_key,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete multipart upload: {str(e)}",
        ) from e

    logger.info(
        "Completed multipart upload: run=%s type=%s filename=%s size=%d",
        run_id,
        payload.artifact_type,
        payload.filename,
        payload.file_size,
    )

    return MultipartUploadCompleteResponse(
        s3_key=payload.s3_key,
        success=True,
    )


@router.post("/{run_id}/multipart-upload-abort", status_code=status.HTTP_204_NO_CONTENT)
async def abort_multipart_upload(
    run_id: str,
    payload: MultipartUploadAbortRequest,
    _: None = Depends(verify_run_auth),
) -> None:
    """Abort a multipart upload."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()

    s3_service.abort_multipart_upload(
        s3_key=payload.s3_key,
        upload_id=payload.upload_id,
    )

    logger.info(
        "Aborted multipart upload: run=%s s3_key=%s upload_id=%s",
        run_id,
        payload.s3_key,
        payload.upload_id,
    )


@router.post("/{run_id}/parent-run-files", response_model=ParentRunFilesResponse)
async def get_parent_run_files(
    run_id: str,
    payload: ParentRunFilesRequest,
    _: None = Depends(verify_run_auth),
) -> ParentRunFilesResponse:
    """List files from a parent run and return presigned download URLs."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()
    prefix = f"research-pipeline/{payload.parent_run_id}/"

    objects = s3_service.list_objects(prefix=prefix)

    files: List[ParentRunFileInfo] = []
    for obj in objects:
        s3_key = str(obj["key"])
        filename = s3_key.split("/")[-1]
        download_url = s3_service.generate_download_url(
            s3_key=s3_key,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        files.append(
            ParentRunFileInfo(
                s3_key=s3_key,
                filename=filename,
                size=int(obj["size"]),
                download_url=download_url,
            )
        )

    logger.debug(
        "Listed parent run files: run=%s parent_run=%s count=%d",
        run_id,
        payload.parent_run_id,
        len(files),
    )

    return ParentRunFilesResponse(
        files=files,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


MAX_DATASET_FILES = 2000


@router.post("/{run_id}/list-datasets", response_model=ListDatasetsResponse)
async def list_datasets(
    run_id: str,
    payload: ListDatasetsRequest,
    _: None = Depends(verify_run_auth),
) -> ListDatasetsResponse:
    """List files in a datasets folder and return presigned download URLs."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()
    folder = payload.datasets_folder.strip("/")
    prefix = f"{folder}/" if folder else ""

    objects = s3_service.list_objects(prefix=prefix)

    files: List[DatasetFileInfo] = []
    for obj in objects:
        if len(files) >= MAX_DATASET_FILES:
            break
        s3_key = str(obj["key"])
        # Skip "directory" entries (keys ending with / and size 0)
        if s3_key.endswith("/") and obj["size"] == 0:
            continue
        relative_path = s3_key[len(prefix) :] if s3_key.startswith(prefix) else s3_key
        download_url = s3_service.generate_download_url(
            s3_key=s3_key,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        files.append(
            DatasetFileInfo(
                s3_key=s3_key,
                relative_path=relative_path,
                size=int(obj["size"]),
                download_url=download_url,
            )
        )

    logger.debug(
        "Listed datasets: run=%s folder=%s count=%d",
        run_id,
        payload.datasets_folder,
        len(files),
    )

    return ListDatasetsResponse(
        files=files,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/dataset-upload-url", response_model=DatasetUploadUrlResponse)
async def get_dataset_upload_url(
    run_id: str,
    payload: DatasetUploadUrlRequest,
    _: None = Depends(verify_run_auth),
) -> DatasetUploadUrlResponse:
    """Generate a presigned URL for uploading a file to the datasets folder."""
    db = cast("ResearchRunStore", get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    folder = payload.datasets_folder.strip("/")
    relative = payload.relative_path.lstrip("/")
    s3_key = f"{folder}/{relative}" if folder else relative

    s3_service = get_s3_service()
    upload_url = s3_service.generate_upload_url(
        s3_key=s3_key,
        content_type=payload.content_type,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        metadata={"run_id": run_id, "type": "dataset"},
    )

    logger.debug(
        "Generated dataset upload URL: run=%s key=%s",
        run_id,
        s3_key,
    )

    return DatasetUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )
