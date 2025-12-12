import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, Optional, Protocol, Sequence, Union, cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import (
    ArtifactPresignedUrlResponse,
    LlmReviewNotFoundResponse,
    LlmReviewResponse,
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
    ResearchRunDetailsResponse,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunSubstageEvent,
    TreeVizItem,
)
from app.services import get_database
from app.services.billing_guard import enforce_minimum_credits
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import (
    ResearchPipelineRun,
    ResearchPipelineRunEvent,
)
from app.services.database.rp_artifacts import ResearchPipelineArtifact
from app.services.database.rp_events import (
    BestNodeReasoningEvent,
    PaperGenerationEvent,
    RunLogEvent,
    StageProgressEvent,
    SubstageCompletedEvent,
)
from app.services.database.rp_tree_viz import TreeVizRecord
from app.services.research_pipeline.runpod_manager import (
    RunPodError,
    fetch_pod_billing_summary,
    launch_research_pipeline_run,
    terminate_pod,
    upload_runpod_log_via_ssh,
)
from app.services.s3_service import get_s3_service

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)

REQUESTER_NAME_FALLBACK = "Scientist"


def extract_first_name(*, full_name: str) -> str:
    """Return a cleaned first-name token suitable for pod naming."""
    stripped = full_name.strip()
    if not stripped:
        return REQUESTER_NAME_FALLBACK
    token = stripped.split()[0]
    alnum_only = "".join(char for char in token if char.isalnum())
    if not alnum_only:
        return REQUESTER_NAME_FALLBACK
    return f"{alnum_only[0].upper()}{alnum_only[1:]}"


_launch_cancel_events: dict[str, threading.Event] = {}
_launch_cancel_lock = threading.Lock()


class ResearchRunAcceptedResponse(BaseModel):
    run_id: str
    status: str = "ok"


class ResearchRunStopResponse(BaseModel):
    run_id: str
    status: str
    message: str


def _record_pod_billing_event(
    db: DatabaseManager,
    *,
    run_id: str,
    pod_id: str,
    context: str,
) -> None:
    try:
        summary = fetch_pod_billing_summary(pod_id=pod_id)
    except (RuntimeError, RunPodError) as exc:
        logger.warning("Failed to fetch billing summary for pod %s: %s", pod_id, exc)
        return
    if summary is None:
        return
    metadata = dict(summary)
    metadata["context"] = context
    db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=datetime.now(timezone.utc),
    )


def _upload_pod_log_if_possible(run: ResearchPipelineRun) -> None:
    host = run.public_ip
    port = run.ssh_port
    if not host or not port:
        logger.info("Run %s missing SSH info; skipping log upload.", run.run_id)
        return
    try:
        upload_runpod_log_via_ssh(host=host, port=port, run_id=run.run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to upload pod log via SSH for run %s: %s", run.run_id, exc)


class IdeaPayloadSource(Protocol):
    idea_id: int
    version_id: int
    version_number: int
    title: str
    short_hypothesis: str
    related_work: str
    abstract: str
    experiments: Sequence[Any]
    expected_outcome: str
    risk_factors_and_limitations: Sequence[Any]


def _idea_version_to_payload(idea_data: IdeaPayloadSource) -> Dict[str, object]:
    experiments = idea_data.experiments or []
    risks = idea_data.risk_factors_and_limitations or []
    return {
        "Name": f"idea_{idea_data.idea_id}_v{idea_data.version_number}",
        "Title": idea_data.title or "",
        "Short Hypothesis": idea_data.short_hypothesis or "",
        "Related Work": idea_data.related_work or "",
        "Abstract": idea_data.abstract or "",
        "Experiments": experiments if isinstance(experiments, list) else [],
        "Expected Outcome": idea_data.expected_outcome or "",
        "Risk Factors and Limitations": risks if isinstance(risks, list) else [],
    }


def _create_and_launch_research_run(
    *,
    idea_data: IdeaPayloadSource,
    requested_by_first_name: str,
    background_tasks: BackgroundTasks | None = None,
) -> str:
    db = get_database()
    run_id = f"rp-{uuid4().hex[:10]}"
    db.create_research_pipeline_run(
        run_id=run_id,
        idea_id=idea_data.idea_id,
        idea_version_id=idea_data.version_id,
        status="pending",
        start_deadline_at=None,
        cost=0.0,
        last_billed_at=datetime.now(timezone.utc),
    )
    idea_payload = _idea_version_to_payload(idea_data)
    cancel_event = threading.Event()
    with _launch_cancel_lock:
        _launch_cancel_events[run_id] = cancel_event

    if background_tasks is not None:
        background_tasks.add_task(
            _launch_research_pipeline_job,
            run_id=run_id,
            idea_payload=idea_payload,
            requested_by_first_name=requested_by_first_name,
            cancel_event=cancel_event,
        )
    else:
        thread = threading.Thread(
            target=_launch_research_pipeline_job,
            kwargs={
                "run_id": run_id,
                "idea_payload": idea_payload,
                "requested_by_first_name": requested_by_first_name,
                "cancel_event": cancel_event,
            },
            daemon=True,
        )
        thread.start()
    return run_id


def _extract_cost_per_hour(pod_info: Dict[str, Any], run_id: str) -> float:
    try:
        value = pod_info["costPerHr"]
    except KeyError:
        logger.warning(
            "Run %s pod response missing costPerHr. Full payload: %s",
            run_id,
            pod_info,
        )
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Run %s pod response costPerHr is invalid (%s); payload=%s",
            run_id,
            value,
            pod_info,
        )
        return 0.0


def _launch_research_pipeline_job(
    *,
    run_id: str,
    idea_payload: Dict[str, object],
    requested_by_first_name: str,
    cancel_event: threading.Event | None = None,
) -> None:
    """Background task that launches the RunPod job and updates DB state."""
    db = get_database()
    config_name = f"{run_id}_config.yaml"
    try:
        logger.info("Launching research pipeline job in background for run_id=%s", run_id)

        if cancel_event and cancel_event.is_set():
            logger.info("Launch for run_id=%s cancelled before contacting RunPod.", run_id)
            return

        startup_grace_seconds = int(os.environ.get("PIPELINE_MONITOR_STARTUP_GRACE_SECONDS", "600"))
        db.update_research_pipeline_run(
            run_id=run_id,
            start_deadline_at=datetime.now(timezone.utc) + timedelta(seconds=startup_grace_seconds),
        )

        pod_info = launch_research_pipeline_run(
            idea=idea_payload,
            config_name=config_name,
            run_id=run_id,
            requested_by_first_name=requested_by_first_name,
        )

        if cancel_event and cancel_event.is_set():
            logger.info(
                "Launch for run_id=%s cancelled after pod creation; terminating pod.",
                run_id,
            )
            pod_id = pod_info.get("pod_id")
            if pod_id:
                try:
                    terminate_pod(pod_id=pod_id)
                except RuntimeError as exc:
                    logger.warning(
                        "Failed to terminate pod %s for cancelled run %s: %s",
                        pod_id,
                        run_id,
                        exc,
                    )
            return

        db.update_research_pipeline_run(
            run_id=run_id,
            pod_info=pod_info,
            cost=_extract_cost_per_hour(pod_info, run_id),
        )
        db.insert_research_pipeline_run_event(
            run_id=run_id,
            event_type="pod_info_updated",
            metadata={
                "pod_id": pod_info.get("pod_id"),
                "pod_name": pod_info.get("pod_name"),
                "gpu_type": pod_info.get("gpu_type"),
                "public_ip": pod_info.get("public_ip"),
                "ssh_port": pod_info.get("ssh_port"),
                "cost_per_hr": pod_info.get("costPerHr"),
            },
            occurred_at=datetime.now(timezone.utc),
        )
    except (RunPodError, FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.exception("Failed to launch research pipeline run.")
        run_before = db.get_research_pipeline_run(run_id)
        db.update_research_pipeline_run(run_id=run_id, status="failed", error_message=str(exc))
        db.insert_research_pipeline_run_event(
            run_id=run_id,
            event_type="status_changed",
            metadata={
                "from_status": run_before.status if run_before else None,
                "to_status": "failed",
                "reason": "launch_error",
                "error_message": str(exc),
            },
            occurred_at=datetime.now(timezone.utc),
        )
    else:
        logger.info("Background launch complete for run_id=%s", run_id)
    finally:
        if cancel_event:
            with _launch_cancel_lock:
                existing = _launch_cancel_events.get(run_id)
                if existing is cancel_event:
                    _launch_cancel_events.pop(run_id, None)


def _run_to_info(run: ResearchPipelineRun) -> ResearchRunInfo:
    return ResearchRunInfo(
        run_id=run.run_id,
        status=run.status,
        idea_id=run.idea_id,
        idea_version_id=run.idea_version_id,
        pod_id=run.pod_id,
        pod_name=run.pod_name,
        gpu_type=run.gpu_type,
        cost=run.cost,
        public_ip=run.public_ip,
        ssh_port=run.ssh_port,
        pod_host_id=run.pod_host_id,
        error_message=run.error_message,
        last_heartbeat_at=run.last_heartbeat_at.isoformat() if run.last_heartbeat_at else None,
        heartbeat_failures=run.heartbeat_failures,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        start_deadline_at=run.start_deadline_at.isoformat() if run.start_deadline_at else None,
    )


def _stage_event_to_model(event: StageProgressEvent) -> ResearchRunStageProgress:
    return ResearchRunStageProgress(
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
        created_at=event.created_at.isoformat(),
    )


def _log_event_to_model(event: RunLogEvent) -> ResearchRunLogEntry:
    return ResearchRunLogEntry(
        id=event.id,
        level=event.level,
        message=event.message,
        created_at=event.created_at.isoformat(),
    )


def _run_event_to_model(event: ResearchPipelineRunEvent) -> ResearchRunEvent:
    return ResearchRunEvent(
        id=event.id,
        run_id=event.run_id,
        event_type=event.event_type,
        metadata=event.metadata,
        occurred_at=event.occurred_at.isoformat(),
    )


def _node_event_to_model(event: SubstageCompletedEvent) -> ResearchRunSubstageEvent:
    return ResearchRunSubstageEvent(
        id=event.id,
        stage=event.stage,
        node_id=None,
        summary=event.summary,
        created_at=event.created_at.isoformat(),
    )


def _best_node_event_to_model(
    event: BestNodeReasoningEvent,
) -> ResearchRunBestNodeSelection:
    return ResearchRunBestNodeSelection(
        id=event.id,
        stage=event.stage,
        node_id=event.node_id,
        reasoning=event.reasoning,
        created_at=event.created_at.isoformat(),
    )


def _paper_generation_event_to_model(
    event: PaperGenerationEvent,
) -> ResearchRunPaperGenerationProgress:
    return ResearchRunPaperGenerationProgress(
        id=event.id,
        run_id=event.run_id,
        step=event.step,
        substep=event.substep,
        progress=event.progress,
        step_progress=event.step_progress,
        details=event.details,
        created_at=event.created_at.isoformat(),
    )


def _artifact_to_model(
    artifact: ResearchPipelineArtifact, conversation_id: int, run_id: str
) -> ResearchRunArtifactMetadata:
    return ResearchRunArtifactMetadata(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        filename=artifact.filename,
        file_size=artifact.file_size,
        file_type=artifact.file_type,
        created_at=artifact.created_at.isoformat(),
        download_path=(
            f"/api/conversations/{conversation_id}/idea/research-run/{run_id}/artifacts/{artifact.id}/download"
        ),
    )


def _tree_viz_to_model(record: TreeVizRecord) -> TreeVizItem:
    return TreeVizItem(
        id=record.id,
        run_id=record.run_id,
        stage_id=record.stage_id,
        version=record.version,
        viz=record.viz,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.post(
    "/{conversation_id}/idea/research-run",
    response_model=ResearchRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_idea_for_research(
    conversation_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ResearchRunAcceptedResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    user = get_current_user(request)
    db = get_database()

    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    idea_data = db.get_idea_by_conversation_id(conversation_id)
    if idea_data is None or idea_data.version_id is None:
        raise HTTPException(status_code=400, detail="Conversation does not have an active idea")

    enforce_minimum_credits(
        user_id=user.id,
        required=settings.MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE,
        action="research_pipeline",
    )

    requester_first_name = extract_first_name(full_name=user.name)
    run_id = _create_and_launch_research_run(
        idea_data=cast(IdeaPayloadSource, idea_data),
        requested_by_first_name=requester_first_name,
        background_tasks=background_tasks,
    )
    return ResearchRunAcceptedResponse(run_id=run_id)


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}",
    response_model=ResearchRunDetailsResponse,
)
def get_research_run_details(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> ResearchRunDetailsResponse:
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

    stage_events = [
        _stage_event_to_model(event) for event in db.list_stage_progress_events(run_id=run_id)
    ]
    log_events = [_log_event_to_model(event) for event in db.list_run_log_events(run_id=run_id)]
    substage_events = [
        _node_event_to_model(event) for event in db.list_substage_completed_events(run_id=run_id)
    ]
    best_node_selections = [
        _best_node_event_to_model(event)
        for event in db.list_best_node_reasoning_events(run_id=run_id)
    ]
    artifacts = [
        _artifact_to_model(
            artifact=artifact,
            conversation_id=conversation_id,
            run_id=run_id,
        )
        for artifact in db.list_run_artifacts(run_id=run_id)
    ]
    run_events = [
        _run_event_to_model(event) for event in db.list_research_pipeline_run_events(run_id=run_id)
    ]
    tree_viz = [_tree_viz_to_model(record) for record in db.list_tree_viz_for_run(run_id=run_id)]
    paper_gen_events = [
        _paper_generation_event_to_model(event)
        for event in db.list_paper_generation_events(run_id=run_id)
    ]

    return ResearchRunDetailsResponse(
        run=_run_to_info(run),
        stage_progress=stage_events,
        logs=log_events,
        substage_events=substage_events,
        best_node_selections=best_node_selections,
        events=run_events,
        artifacts=artifacts,
        paper_generation_progress=paper_gen_events,
        tree_viz=tree_viz,
    )


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/review",
    response_model=Union[LlmReviewResponse, LlmReviewNotFoundResponse],
)
def get_research_run_review(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> Union[LlmReviewResponse, LlmReviewNotFoundResponse]:
    """Fetch LLM review data for a research run."""
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

    review = db.get_review_by_run_id(run_id)
    if review is None:
        return LlmReviewNotFoundResponse(
            run_id=run_id,
            exists=False,
            message="No evaluation available for this research run",
        )

    return LlmReviewResponse(
        id=review["id"],
        run_id=review["run_id"],
        summary=review["summary"],
        strengths=review["strengths"] or [],
        weaknesses=review["weaknesses"] or [],
        originality=float(review["originality"]),
        quality=float(review["quality"]),
        clarity=float(review["clarity"]),
        significance=float(review["significance"]),
        questions=review["questions"] or [],
        limitations=review["limitations"] or [],
        ethical_concerns=review["ethical_concerns"],
        soundness=float(review["soundness"]),
        presentation=float(review["presentation"]),
        contribution=float(review["contribution"]),
        overall=float(review["overall"]),
        confidence=float(review["confidence"]),
        decision=review["decision"],
        source_path=review["source_path"],
        created_at=review["created_at"].isoformat(),
    )


@router.post(
    "/{conversation_id}/idea/research-run/{run_id}/stop",
    response_model=ResearchRunStopResponse,
)
def stop_research_run(conversation_id: int, run_id: str) -> ResearchRunStopResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    db = get_database()

    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run = db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Research run is already {run.status}; cannot stop.",
        )

    with _launch_cancel_lock:
        cancel_event = _launch_cancel_events.get(run_id)
        if cancel_event:
            cancel_event.set()

    pod_id = run.pod_id
    if pod_id:
        _upload_pod_log_if_possible(run)
        try:
            terminate_pod(pod_id=pod_id)
        except RunPodError as exc:
            logger.exception("Failed to terminate pod %s for run %s", pod_id, run_id)
            raise HTTPException(
                status_code=502, detail="Failed to terminate the research run pod."
            ) from exc
        finally:
            _record_pod_billing_event(
                db,
                run_id=run_id,
                pod_id=pod_id,
                context="user_stop",
            )
    else:
        logger.info("Run %s has no pod_id; marking as stopped without pod termination.", run_id)

    stop_message = "Research run was stopped by the user."
    db.update_research_pipeline_run(
        run_id=run_id,
        status="failed",
        error_message=stop_message,
    )
    db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "failed",
            "reason": "user_stop",
            "error_message": stop_message,
        },
        occurred_at=datetime.now(timezone.utc),
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
def download_research_run_artifact(
    conversation_id: int,
    run_id: str,
    artifact_id: int,
    request: Request,
) -> RedirectResponse:
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
    artifact = db.get_run_artifact(artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    s3 = get_s3_service()
    try:
        download_url = s3.generate_download_url(artifact.s3_key)
    except Exception as exc:  # pragma: no cover - S3 errors already logged upstream
        logger.exception("Failed to generate download URL for artifact %s", artifact_id)
        raise HTTPException(status_code=500, detail="Failed to generate download URL") from exc
    return RedirectResponse(url=download_url)


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/artifacts/{artifact_id}/presign",
    response_model=ArtifactPresignedUrlResponse,
)
def get_artifact_presigned_url(
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

    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    run = db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    artifact = db.get_run_artifact(artifact_id)
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
def list_tree_viz(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> list[TreeVizItem]:
    """List stored tree visualizations for a run."""
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
    records = db.list_tree_viz_for_run(run_id=run_id)
    return [_tree_viz_to_model(record) for record in records]


@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/tree-viz/{stage_id}",
    response_model=TreeVizItem,
)
def get_tree_viz(
    conversation_id: int,
    run_id: str,
    stage_id: str,
    request: Request,
) -> TreeVizItem:
    """Fetch tree viz payload for a specific stage."""
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
    record = db.get_tree_viz(run_id=run_id, stage_id=stage_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tree viz not found")
    return _tree_viz_to_model(record)


SSE_POLL_INTERVAL_SECONDS = 2.0
SSE_HEARTBEAT_INTERVAL_SECONDS = 30.0


def _is_meaningful_progress_change(
    prev: Optional[StageProgressEvent], curr: StageProgressEvent
) -> bool:
    """Check if the progress change is meaningful enough to emit an SSE event."""
    if prev is None:
        return True
    if prev.stage != curr.stage:
        return True
    prev_bucket = int(prev.progress * 10)
    curr_bucket = int(curr.progress * 10)
    if curr_bucket > prev_bucket:
        return True
    if prev.best_metric != curr.best_metric and curr.best_metric is not None:
        return True
    return False


@router.get("/{conversation_id}/idea/research-run/{run_id}/events")
async def stream_research_run_events(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> StreamingResponse:
    """Stream server-sent events for research run progress."""
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

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events until the run completes or client disconnects."""
        last_progress_event: Optional[StageProgressEvent] = None
        last_paper_gen_event: Optional[PaperGenerationEvent] = None
        last_heartbeat = datetime.now(timezone.utc)
        initial_sent = False
        last_run_event_id: Optional[int] = None
        last_best_node_event_id: Optional[int] = None

        while True:
            # Check if client is still connected
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE stream for run %s", run_id)
                break

            try:
                # Fetch current run state
                current_run = db.get_research_pipeline_run(run_id)
                if current_run is None:
                    yield f"data: {json.dumps({'type': 'error', 'data': 'Run not found'})}\n\n"
                    break

                # Send initial data on first iteration
                if not initial_sent:
                    stage_events = [
                        _stage_event_to_model(e).model_dump()
                        for e in db.list_stage_progress_events(run_id=run_id)
                    ]
                    log_events = [
                        _log_event_to_model(e).model_dump()
                        for e in db.list_run_log_events(run_id=run_id)
                    ]
                    substage_events = [
                        _node_event_to_model(e).model_dump()
                        for e in db.list_substage_completed_events(run_id=run_id)
                    ]
                    artifacts = [
                        _artifact_to_model(a, conversation_id, run_id).model_dump()
                        for a in db.list_run_artifacts(run_id=run_id)
                    ]
                    tree_viz = [
                        _tree_viz_to_model(record).model_dump()
                        for record in db.list_tree_viz_for_run(run_id=run_id)
                    ]
                    paper_gen_events = [
                        _paper_generation_event_to_model(e).model_dump()
                        for e in db.list_paper_generation_events(run_id=run_id)
                    ]
                    run_events_raw = db.list_research_pipeline_run_events(run_id=run_id)
                    run_events = [_run_event_to_model(e).model_dump() for e in run_events_raw]
                    if run_events_raw:
                        last_run_event_id = max(event.id for event in run_events_raw)
                    best_node_events = db.list_best_node_reasoning_events(run_id=run_id)
                    best_node_payload = [
                        _best_node_event_to_model(event).model_dump() for event in best_node_events
                    ]
                    if best_node_events:
                        last_best_node_event_id = max(event.id for event in best_node_events)
                    initial_data = {
                        "run": _run_to_info(current_run).model_dump(),
                        "stage_progress": stage_events,
                        "logs": log_events,
                        "substage_events": substage_events,
                        "artifacts": artifacts,
                        "tree_viz": tree_viz,
                        "events": run_events,
                        "paper_generation_progress": paper_gen_events,
                        "best_node_selections": best_node_payload,
                    }
                    yield f"data: {json.dumps({'type': 'initial', 'data': initial_data})}\n\n"
                    initial_sent = True

                # Check if run is complete
                if current_run.status in ("completed", "failed", "cancelled"):
                    # Emit final status event
                    yield f"data: {json.dumps({'type': 'complete', 'data': {'status': current_run.status}})}\n\n"
                    break

                # Check and emit progress events if meaningful changes
                all_progress = db.list_stage_progress_events(run_id=run_id)
                if all_progress:
                    curr_progress = all_progress[-1]  # Get most recent (ordered ASC)
                    if _is_meaningful_progress_change(last_progress_event, curr_progress):
                        progress_data = _stage_event_to_model(curr_progress)
                        yield f"data: {json.dumps({'type': 'stage_progress', 'data': progress_data.model_dump()})}\n\n"
                        last_progress_event = curr_progress

                run_events_raw = db.list_research_pipeline_run_events(run_id=run_id)
                if run_events_raw:
                    new_events = (
                        [
                            e
                            for e in run_events_raw
                            if last_run_event_id is None or e.id > last_run_event_id
                        ]
                        if last_run_event_id is not None
                        else run_events_raw
                    )
                    for event in new_events:
                        yield f"data: {json.dumps({'type': 'run_event', 'data': _run_event_to_model(event).model_dump()})}\n\n"
                        last_run_event_id = event.id

                best_node_events = db.list_best_node_reasoning_events(run_id=run_id)
                if best_node_events:
                    new_best_nodes = (
                        [
                            best_event
                            for best_event in best_node_events
                            if last_best_node_event_id is None
                            or best_event.id > last_best_node_event_id
                        ]
                        if last_best_node_event_id is not None
                        else best_node_events
                    )
                    for best_event in new_best_nodes:
                        payload = _best_node_event_to_model(best_event).model_dump()
                        yield f"data: {json.dumps({'type': 'best_node_selection', 'data': payload})}\n\n"
                        last_best_node_event_id = best_event.id

                # Check and emit paper generation progress events
                all_paper_gen = db.list_paper_generation_events(run_id=run_id)
                if all_paper_gen:
                    curr_paper_gen = all_paper_gen[-1]  # Most recent
                    if curr_paper_gen != last_paper_gen_event:
                        paper_gen_data = _paper_generation_event_to_model(curr_paper_gen)
                        yield f"data: {json.dumps({'type': 'paper_generation_progress', 'data': paper_gen_data.model_dump()})}\n\n"
                        last_paper_gen_event = curr_paper_gen

                # Emit heartbeat every SSE_HEARTBEAT_INTERVAL_SECONDS
                now = datetime.now(timezone.utc)
                if (now - last_heartbeat).total_seconds() >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    last_heartbeat = now

                # Wait before polling again
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)

            except Exception as exc:
                logger.exception("Error in SSE event generation for run %s", run_id)
                yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
