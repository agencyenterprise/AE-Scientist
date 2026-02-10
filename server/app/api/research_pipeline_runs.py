import asyncio
import gzip
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol, Union, cast
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.api.research_pipeline.utils import extract_user_first_name, generate_run_webhook_token
from app.api.research_pipeline_stream import publish_stream_event
from app.config import settings
from app.middleware.auth import get_current_user
from app.models import (
    ArtifactPresignedUrlResponse,
    ChildConversationInfo,
    LlmReviewNotFoundResponse,
    LlmReviewResponse,
    ResearchRunArtifactMetadata,
    ResearchRunDetailsResponse,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageEvent,
    ResearchRunStageProgress,
    ResearchRunStageSkipWindow,
    ResearchRunStageSummary,
    TreeVizItem,
)
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.timeline_events import StageId
from app.services import get_database
from app.services.billing_guard import enforce_minimum_balance
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import PodUpdateInfo
from app.services.narrator.event_types import RunFinishedEventData
from app.services.narrator.narrator_service import ingest_narration_event, initialize_run_state
from app.services.research_pipeline.pod_termination_worker import (
    notify_termination_requested,
    publish_termination_status_event,
)
from app.services.research_pipeline.runpod import (
    CONTAINER_DISK_GB,
    POD_READY_POLL_INTERVAL_SECONDS,
    WORKSPACE_DISK_GB,
    PodLaunchInfo,
    RunPodError,
    TerminationConflictError,
    TerminationNotFoundError,
    TerminationRequestError,
    fetch_pod_ready_metadata,
    get_gpu_display_info,
    get_gpu_type_prices,
    get_pipeline_startup_grace_seconds,
    get_supported_gpu_types,
    launch_research_pipeline_run,
    request_stage_skip_via_ssh,
    send_execution_feedback_via_ssh,
)
from app.services.s3_service import get_s3_service

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)


def _get_fake_runpod_base_url() -> str | None:
    value = settings.runpod.fake_base_url
    return value.strip() if value else None


async def _post_fake_runpod(
    *,
    base_url: str,
    path: str,
    payload: dict[str, object],
    timeout_seconds: float,
) -> tuple[int, str]:
    endpoint = f"{base_url.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, json=payload)
    body = response.text.strip() if response.text else ""
    return response.status_code, body


class PodLaunchError(Exception):
    """Error launching pod"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _get_user_friendly_runpod_error(exc: RunPodError) -> str:
    """Convert a RunPod API error into a user-friendly message."""
    error_str = str(exc).lower()

    if "no instances currently available" in error_str:
        return (
            "No GPU instances are currently available for the selected GPU type. "
            "Please try again later or select a different GPU type."
        )

    if exc.status == 401 or "unauthorized" in error_str:
        return "Authentication error with GPU provider. Please contact support."

    if exc.status == 429 or "rate limit" in error_str:
        return "Too many requests to GPU provider. Please wait a moment and try again."

    if exc.status >= 500:
        return "The GPU provider is experiencing issues. Please try again later."

    # Fallback for unknown errors
    return "Failed to provision GPU instance. Please try again or select a different GPU type."


class ResearchRunAcceptedResponse(BaseModel):
    status: str = "ok"
    run_id: str
    pod_id: str
    pod_name: str
    gpu_type: str
    cost: float


class LaunchResearchRunRequest(BaseModel):
    gpu_type: str


class GpuTypeListResponse(BaseModel):
    gpu_types: list[str]
    gpu_prices: dict[str, float | None]
    gpu_display_names: dict[str, str]
    gpu_vram_gb: dict[str, int | None]


@router.get(
    "/research/gpu-types",
    response_model=GpuTypeListResponse,
)
async def list_research_gpu_types() -> GpuTypeListResponse:
    gpu_types = get_supported_gpu_types()
    prices = await get_gpu_type_prices(gpu_types=gpu_types)
    display_info = await get_gpu_display_info(gpu_types=gpu_types)
    # Sort GPU types by price (cheapest first), with unknown prices at the end
    sorted_gpu_types = sorted(
        gpu_types,
        key=lambda gpu: (prices.get(gpu) is None, prices.get(gpu) or float("inf")),
    )
    return GpuTypeListResponse(
        gpu_types=sorted_gpu_types,
        gpu_prices={gpu_type: prices.get(gpu_type) for gpu_type in sorted_gpu_types},
        gpu_display_names={
            gpu_type: display_info[gpu_type].display_name for gpu_type in sorted_gpu_types
        },
        gpu_vram_gb={
            gpu_type: display_info[gpu_type].memory_in_gb for gpu_type in sorted_gpu_types
        },
    )


class ResearchRunStopResponse(BaseModel):
    run_id: str
    status: str
    message: str


class TerminateExecutionRequest(BaseModel):
    payload: str


class TerminateExecutionResponse(BaseModel):
    execution_id: str
    status: Literal["terminating"]


class SkipStageRequest(BaseModel):
    stage: StageId | None = None
    reason: str | None = None


class SkipStageResponse(BaseModel):
    status: Literal["pending"]
    message: str


class IdeaPayloadSource(Protocol):
    idea_id: int
    version_id: int
    version_number: int
    title: str
    idea_markdown: str


async def _notify_pod_ready_failure(
    *,
    db: DatabaseManager,
    run_id: str,
    pod_info: PodLaunchInfo,
    event_type: str,
    reason: str,
    metadata: dict[str, object],
) -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "pod_id": pod_info.pod_id,
        "pod_name": pod_info.pod_name,
        "gpu_type": pod_info.gpu_type,
        "reason": reason,
        **metadata,
    }
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type=event_type,
        metadata=payload,
        occurred_at=now,
    )
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run_id,
        event_type=event_type,
        metadata=payload,
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )


async def _wait_for_pod_ready(db: DatabaseManager, pod_info: PodLaunchInfo, run_id: str) -> None:
    logger.info(
        "Waiting for pod readiness for run_id=%s (pod_id=%s, pod_name=%s)",
        run_id,
        pod_info.pod_id,
        pod_info.pod_name,
    )
    poll_interval_seconds = POD_READY_POLL_INTERVAL_SECONDS
    startup_grace_seconds = get_pipeline_startup_grace_seconds()
    max_attempts = max(1, math.ceil(startup_grace_seconds / poll_interval_seconds))
    try:
        ready_metadata = await fetch_pod_ready_metadata(
            pod_id=pod_info.pod_id,
        )
    except asyncio.CancelledError:
        raise
    except RunPodError as exc:
        logger.warning(
            "Pod readiness timed out for run_id=%s (pod_id=%s): %s",
            run_id,
            pod_info.pod_id,
            exc,
        )
        await _notify_pod_ready_failure(
            db=db,
            run_id=run_id,
            pod_info=pod_info,
            event_type="pod_ready_timeout",
            reason="pod_ready_timeout",
            metadata={
                "error_message": str(exc),
                "poll_interval_seconds": poll_interval_seconds,
                "max_attempts": max_attempts,
                "timeout_seconds": poll_interval_seconds * max_attempts,
            },
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error while fetching pod readiness for run_id=%s (pod_id=%s)",
            run_id,
            pod_info.pod_id,
        )
        await _notify_pod_ready_failure(
            db=db,
            run_id=run_id,
            pod_info=pod_info,
            event_type="pod_ready_error",
            reason="pod_ready_error",
            metadata={
                "error_message": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        return
    logger.info(
        "Pod ready for run_id=%s (pod_id=%s). public_ip=%s ssh_port=%s host_id=%s",
        run_id,
        pod_info.pod_id,
        ready_metadata.public_ip,
        ready_metadata.ssh_port,
        ready_metadata.pod_host_id,
    )
    await db.update_research_pipeline_run(
        run_id=run_id,
        pod_update_info=PodUpdateInfo(
            pod_id=pod_info.pod_id,
            pod_name=pod_info.pod_name,
            gpu_type=pod_info.gpu_type,
            cost=pod_info.cost,
            public_ip=ready_metadata.public_ip,
            ssh_port=ready_metadata.ssh_port,
            pod_host_id=ready_metadata.pod_host_id,
        ),
    )
    logger.info(
        "Updated research_pipeline_runs row for run_id=%s with ip=%s port=%s host_id=%s",
        run_id,
        ready_metadata.public_ip,
        ready_metadata.ssh_port,
        ready_metadata.pod_host_id,
    )
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="pod_info_updated",
        metadata={
            "pod_id": pod_info.pod_id,
            "pod_name": pod_info.pod_name,
            "gpu_type": pod_info.gpu_type,
            "cost_per_hr": pod_info.cost,
            "public_ip": ready_metadata.public_ip,
            "ssh_port": ready_metadata.ssh_port,
            "pod_host_id": ready_metadata.pod_host_id,
        },
        occurred_at=datetime.now(timezone.utc),
    )
    logger.info(
        "Recorded pod_info_updated event for run_id=%s with public_ip=%s ssh_port=%s",
        run_id,
        ready_metadata.public_ip,
        ready_metadata.ssh_port,
    )


async def create_and_launch_research_run(
    *,
    idea_data: IdeaPayloadSource,
    requested_by_first_name: str,
    gpu_types: list[str],
    conversation_id: int,
    parent_run_id: str | None,
) -> tuple[str, PodLaunchInfo]:
    db = get_database()
    if not gpu_types:
        raise PodLaunchError("At least one GPU type must be provided.")

    run_id = f"rp-{uuid4().hex[:10]}"
    webhook_token, webhook_token_hash = generate_run_webhook_token()
    config_name = f"{run_id}_config.yaml"

    # Try to launch the pod FIRST, before creating any DB records.
    # This avoids creating orphaned "failed" records when GPU instances are unavailable.
    try:
        logger.info("Launching research pipeline pod for run_id=%s", run_id)
        pod_info = await launch_research_pipeline_run(
            title=idea_data.title,
            idea=idea_data.idea_markdown,
            config_name=config_name,
            run_id=run_id,
            requested_by_first_name=requested_by_first_name,
            gpu_types=gpu_types,
            parent_run_id=parent_run_id,
            webhook_token=webhook_token,
        )
    except RunPodError as exc:
        logger.warning("Failed to launch pod for run_id=%s: %s", run_id, exc)
        raise PodLaunchError(_get_user_friendly_runpod_error(exc)) from None
    except (FileNotFoundError, ValueError, RuntimeError):
        logger.exception("Failed to launch research pipeline run.")
        raise PodLaunchError(
            "Failed to prepare research run. Please try again or contact support."
        ) from None

    # Pod created successfully - now create the DB record
    startup_grace_seconds = get_pipeline_startup_grace_seconds()
    await db.create_research_pipeline_run(
        run_id=run_id,
        idea_id=idea_data.idea_id,
        idea_version_id=idea_data.version_id,
        status="initializing",
        start_deadline_at=datetime.now(timezone.utc) + timedelta(seconds=startup_grace_seconds),
        cost=pod_info.cost,
        last_billed_at=datetime.now(timezone.utc),
        container_disk_gb=CONTAINER_DISK_GB,
        volume_disk_gb=WORKSPACE_DISK_GB,
        webhook_token_hash=webhook_token_hash,
        pod_id=pod_info.pod_id,
        pod_name=pod_info.pod_name,
        gpu_type=pod_info.gpu_type,
    )

    await initialize_run_state(
        db=db,
        run_id=run_id,
        conversation_id=conversation_id,
        idea_title=idea_data.title,
        gpu_type=pod_info.gpu_type,
        cost_per_hour_cents=int(pod_info.cost * 100) if pod_info.cost else None,
    )

    await db.update_research_pipeline_run(
        run_id=run_id,
        initialization_status="Downloading container image",
    )

    asyncio.create_task(_wait_for_pod_ready(db=db, pod_info=pod_info, run_id=run_id))
    return run_id, pod_info


@router.post(
    "/{conversation_id}/idea/research-run",
    response_model=ResearchRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_idea_for_research(
    conversation_id: int,
    request: Request,
    payload: LaunchResearchRunRequest,
) -> ResearchRunAcceptedResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    user = get_current_user(request)
    db = get_database()

    conversation = await db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    # Get parent run ID if this conversation is seeded from a previous run
    parent_run_id = await db.get_conversation_parent_run_id(conversation_id)

    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if idea_data is None or idea_data.version_id is None:
        raise HTTPException(status_code=400, detail="Conversation does not have an active idea")

    await enforce_minimum_balance(
        user_id=user.id,
        required_cents=settings.billing_limits.min_balance_cents_for_research_pipeline,
        action="research_pipeline",
    )

    requester_first_name = extract_user_first_name(full_name=user.name)
    available_gpu_types = get_supported_gpu_types()
    if payload.gpu_type not in available_gpu_types:
        raise HTTPException(status_code=400, detail="Selected GPU type is not supported.")
    try:
        run_id, pod_info = await create_and_launch_research_run(
            idea_data=cast(IdeaPayloadSource, idea_data),
            requested_by_first_name=requester_first_name,
            gpu_types=[payload.gpu_type],
            conversation_id=conversation_id,
            parent_run_id=parent_run_id,
        )
        return ResearchRunAcceptedResponse(
            run_id=run_id,
            pod_id=pod_info.pod_id,
            pod_name=pod_info.pod_name,
            gpu_type=pod_info.gpu_type,
            cost=pod_info.cost,
        )
    except PodLaunchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}",
    response_model=ResearchRunDetailsResponse,
)
async def get_research_run_details(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> ResearchRunDetailsResponse:
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

    stage_progress_events = [
        ResearchRunStageProgress.from_db_record(event)
        for event in await db.list_stage_progress_events(run_id=run_id)
    ]
    stage_events = [
        ResearchRunStageEvent.from_db_record(event)
        for event in await db.list_stage_completed_events(run_id=run_id)
    ]
    stage_summaries = [
        ResearchRunStageSummary.from_db_record(event)
        for event in await db.list_stage_summary_events(run_id=run_id)
    ]
    artifacts = [
        ResearchRunArtifactMetadata.from_db_record(
            artifact=artifact,
            conversation_id=conversation_id,
            run_id=run_id,
        )
        for artifact in await db.list_run_artifacts(run_id=run_id)
    ]
    run_events = [
        ResearchRunEvent.from_db_record(event)
        for event in await db.list_research_pipeline_run_events(run_id=run_id)
    ]
    paper_gen_events = [
        ResearchRunPaperGenerationProgress.from_db_record(event)
        for event in await db.list_paper_generation_events(run_id=run_id)
    ]
    stage_skip_windows = [
        ResearchRunStageSkipWindow.from_db_record(record)
        for record in await db.list_stage_skip_windows(run_id=run_id)
    ]
    termination = await db.get_research_pipeline_run_termination(run_id=run_id)

    # Get child conversations seeded from this run
    child_convs = await db.list_child_conversations_by_run_id(run_id=run_id)
    child_conversations = [
        ChildConversationInfo(
            conversation_id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            status=c.status,
        )
        for c in child_convs
    ]

    return ResearchRunDetailsResponse(
        run=ResearchRunInfo.from_db_record(
            run=run, termination=termination, parent_run_id=conversation.parent_run_id
        ),
        stage_progress=stage_progress_events,
        stage_events=stage_events,
        stage_summaries=stage_summaries,
        events=run_events,
        artifacts=artifacts,
        paper_generation_progress=paper_gen_events,
        stage_skip_windows=stage_skip_windows,
        child_conversations=child_conversations,
    )


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/review",
    response_model=Union[LlmReviewResponse, LlmReviewNotFoundResponse],
)
async def get_research_run_review(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> Union[LlmReviewResponse, LlmReviewNotFoundResponse]:
    """Fetch LLM review data for a research run."""
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

    review = await db.get_review_by_run_id(run_id)
    if review is None:
        return LlmReviewNotFoundResponse(
            run_id=run_id,
            exists=False,
            message="No evaluation available for this research run",
        )

    return LlmReviewResponse(
        id=review.id,
        run_id=review.run_id,
        summary=review.summary,
        strengths=review.strengths or [],
        weaknesses=review.weaknesses or [],
        originality=review.originality,
        quality=review.quality,
        clarity=review.clarity,
        significance=review.significance,
        questions=review.questions or [],
        limitations=review.limitations or [],
        ethical_concerns=review.ethical_concerns,
        soundness=review.soundness,
        presentation=review.presentation,
        contribution=review.contribution,
        overall=review.overall,
        confidence=review.confidence,
        decision=review.decision,
        source_path=review.source_path,
        created_at=review.created_at.isoformat(),
    )


@router.post(
    "/{conversation_id}/idea/research-run/{run_id}/executions/{execution_id}/terminate",
    response_model=TerminateExecutionResponse,
)
async def terminate_code_execution(
    conversation_id: int,
    run_id: str,
    execution_id: str,
    payload: TerminateExecutionRequest,
    request: Request,
) -> TerminateExecutionResponse:
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
    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Research run is already {run.status}; cannot terminate execution.",
        )

    feedback_payload = payload.payload
    logger.info(
        "Termination requested by user_id=%s run_id=%s execution_id=%s payload_len=%s",
        user.id,
        run_id,
        execution_id,
        len(feedback_payload),
    )
    try:
        fake_runpod_base_url = _get_fake_runpod_base_url()
        if fake_runpod_base_url is not None:
            status_code, body = await _post_fake_runpod(
                base_url=fake_runpod_base_url,
                path=f"/terminate/{execution_id}",
                payload={"payload": feedback_payload},
                timeout_seconds=60.0,
            )
            if status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Execution {execution_id} not found on fake RunPod "
                        f"(response: {body or 'no body'})"
                    ),
                )
            if status_code == 409:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Execution {execution_id} already completed or terminating "
                        f"(response: {body or 'no body'})"
                    ),
                )
            if status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Unexpected termination response for execution {execution_id}: "
                        f"status={status_code} body={body or '<empty>'}"
                    ),
                )
        else:
            if not run.public_ip or not run.ssh_port:
                raise HTTPException(
                    status_code=409,
                    detail="Run pod is not reachable; SSH endpoint unavailable for termination.",
                )
            send_execution_feedback_via_ssh(
                host=run.public_ip,
                port=run.ssh_port,
                execution_id=execution_id,
                payload=feedback_payload,
            )
    except TerminationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TerminationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TerminationRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="termination_requested",
        metadata={
            "execution_id": execution_id,
            "payload_length": len(feedback_payload),
        },
        occurred_at=now,
    )
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run_id,
        event_type="termination_requested",
        metadata={
            "execution_id": execution_id,
            "payload_length": len(feedback_payload),
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
    logger.info(
        "Termination request forwarded successfully for run_id=%s execution_id=%s",
        run_id,
        execution_id,
    )

    return TerminateExecutionResponse(execution_id=execution_id, status="terminating")


@router.post(
    "/{conversation_id}/idea/research-run/{run_id}/skip-stage",
    response_model=SkipStageResponse,
)
async def skip_active_stage(
    conversation_id: int,
    run_id: str,
    payload: SkipStageRequest,
    request: Request,
) -> SkipStageResponse:
    """Request the running pipeline to skip the current stage."""
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
    if run.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Run is {run.status}; skipping stages is only available while running.",
        )

    reason = payload.reason or (
        f"Skip stage requested via dashboard (stage={payload.stage or 'active'})"
    )
    try:
        fake_runpod_base_url = _get_fake_runpod_base_url()
        if fake_runpod_base_url is not None:
            status_code, body = await _post_fake_runpod(
                base_url=fake_runpod_base_url,
                path="/skip-stage",
                payload={"run_id": run_id, "reason": reason},
                timeout_seconds=30.0,
            )
            if status_code != 200:
                raise RuntimeError(
                    f"Stage skip request rejected by fake RunPod: status={status_code} body={body or '<empty>'}"
                )
        else:
            if not run.public_ip or not run.ssh_port:
                raise HTTPException(
                    status_code=409,
                    detail="Run is missing management server access details.",
                )
            request_stage_skip_via_ssh(host=run.public_ip, port=run.ssh_port, reason=reason)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="stage_skip_requested",
        metadata={
            "requested_by": user.email,
            "stage": payload.stage,
            "reason": reason,
        },
        occurred_at=now,
    )

    logger.info("User %s requested stage skip for run %s", user.email, run_id)

    return SkipStageResponse(status="pending", message="Stage skip request sent to pipeline.")


@router.post(
    "/{conversation_id}/idea/research-run/{run_id}/stop",
    response_model=ResearchRunStopResponse,
)
async def stop_research_run(conversation_id: int, run_id: str) -> ResearchRunStopResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    db = get_database()

    conversation = await db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run = await db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    now = datetime.now(timezone.utc)

    termination = await db.enqueue_research_pipeline_run_termination(
        run_id=run_id,
        trigger="user_stop",
    )
    publish_termination_status_event(run_id=run_id, termination=termination)
    notify_termination_requested()

    # Idempotent stop: if already terminal, do not error—just return and (best-effort) push SSE so UI updates.
    if run.status not in ("pending", "initializing", "running"):
        message = run.error_message or f"Research run is already {run.status}."
        return ResearchRunStopResponse(
            run_id=run_id,
            status="stopped",
            message=message,
        )

    stop_message = "Research run was stopped by the user."
    await db.update_research_pipeline_run(
        run_id=run_id, status="failed", error_message=stop_message
    )
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "failed",
            "reason": "user_stop",
            "error_message": stop_message,
        },
        occurred_at=now,
    )
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "failed",
            "reason": "user_stop",
            "error_message": stop_message,
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

    await ingest_narration_event(
        db,
        run_id=run_id,
        event_type="run_finished",
        event_data=RunFinishedEventData(
            success=False,
            status="cancelled",
            message=stop_message,
            reason="user_cancelled",
        ),
    )

    return ResearchRunStopResponse(
        run_id=run_id,
        status="stopped",
        message=stop_message,
    )


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/artifacts/{artifact_id}/download",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def download_research_run_artifact(
    conversation_id: int,
    run_id: str,
    artifact_id: int,
    request: Request,
) -> Response:
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
    artifact = await db.get_run_artifact(artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    s3 = get_s3_service()
    try:
        download_url = s3.generate_download_url(artifact.s3_key, expires_in=3600)
    except Exception as exc:  # pragma: no cover - S3 errors already logged upstream
        logger.exception("Failed to generate download URL for artifact %s", artifact_id)
        raise HTTPException(status_code=500, detail="Failed to generate download URL") from exc
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header.lower():
        return JSONResponse({"url": download_url})

    return RedirectResponse(url=download_url)


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/artifacts/{artifact_id}/presign",
    response_model=ArtifactPresignedUrlResponse,
)
async def get_artifact_presigned_url(
    conversation_id: int,
    run_id: str,
    artifact_id: int,
    request: Request,
) -> ArtifactPresignedUrlResponse:
    """Generate presigned S3 URL for artifact download."""

    # Validation
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    # Auth & ownership checks (same as download endpoint)
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

    artifact = await db.get_run_artifact(artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Generate presigned URL
    s3 = get_s3_service()
    expires_in = 3600
    try:
        download_url = s3.generate_download_url(artifact.s3_key, expires_in=expires_in)
    except Exception as exc:
        logger.exception("Failed to generate presigned URL for artifact %s", artifact_id)
        raise HTTPException(status_code=500, detail="Failed to generate download URL") from exc

    return ArtifactPresignedUrlResponse(
        url=download_url,
        expires_in=expires_in,
        artifact_id=artifact.id,
        filename=artifact.filename,
    )


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/tree-viz",
    response_model=list[TreeVizItem],
)
async def list_tree_viz(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> Response:
    """List stored tree visualizations for a run with gzip compression support."""
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
    records = await db.list_tree_viz_for_run(run_id=run_id)
    tree_viz = [TreeVizItem.from_db_record(record).model_dump() for record in records]

    json_bytes = json.dumps(tree_viz, separators=(",", ":")).encode("utf-8")

    accept_encoding = request.headers.get("accept-encoding", "")
    if "gzip" in accept_encoding.lower():
        compressed = gzip.compress(json_bytes, compresslevel=6)
        return Response(
            content=compressed,
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "Vary": "Accept-Encoding",
            },
        )

    return Response(content=json_bytes, media_type="application/json")


# New run-tree router for endpoints not scoped to a conversation
run_tree_router = APIRouter(prefix="/research-runs", tags=["research-pipeline"])


class RunTreeNodeResponse(BaseModel):
    """A single node in the run tree."""

    run_id: str
    idea_title: str
    status: str
    created_at: str | None
    parent_run_id: str | None
    conversation_id: int
    is_current: bool


class RunTreeResponse(BaseModel):
    """Response containing the full tree of runs."""

    nodes: list[RunTreeNodeResponse]


@run_tree_router.get(
    "/{run_id}/tree",
    response_model=RunTreeResponse,
)
async def get_run_tree(
    run_id: str,
    request: Request,
) -> RunTreeResponse:
    """
    Get the full tree of runs (ancestors and descendants) for a given run.

    This returns all runs that are connected to the specified run through
    the parent-child seeding relationship, including:
    - All ancestor runs (runs that this run was seeded from, transitively)
    - All descendant runs (runs seeded from this run, transitively)
    - The current run itself

    The tree is ordered by creation time, oldest first.
    """
    user = get_current_user(request)
    db = get_database()

    # First verify the run exists and user has access
    run_conversation_id = await db.get_run_conversation_id(run_id)
    if run_conversation_id is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    conversation = await db.get_conversation_by_id(run_conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this run")

    # Get the full tree
    tree_nodes = await db.get_run_tree(run_id)

    return RunTreeResponse(
        nodes=[
            RunTreeNodeResponse(
                run_id=node["run_id"],
                idea_title=node["idea_title"],
                status=node["status"],
                created_at=node["created_at"],
                parent_run_id=node["parent_run_id"],
                conversation_id=node["conversation_id"],
                is_current=node["is_current"],
            )
            for node in tree_nodes
        ]
    )
