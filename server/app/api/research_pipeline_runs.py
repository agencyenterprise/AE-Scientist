import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Protocol, Sequence, Union, cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.research_pipeline_event_stream import usd_to_cents
from app.api.research_pipeline_stream import publish_stream_event
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
    ResearchRunSubstageSummary,
    TreeVizItem,
)
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.services import get_database
from app.services.billing_guard import enforce_minimum_credits
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun
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


def extract_user_first_name(*, full_name: str) -> str:
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
    actual_cost_cents: int | None = None
    amount = metadata.get("amount")
    if amount is not None:
        try:
            actual_cost_cents = usd_to_cents(value_usd=float(amount))
        except (TypeError, ValueError):
            pass
    if actual_cost_cents is not None:
        metadata["actual_cost_cents"] = actual_cost_cents
    now = datetime.now(timezone.utc)
    db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=now,
    )
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )


def _upload_pod_log_if_possible(run: ResearchPipelineRun) -> None:
    host = run.public_ip
    port = run.ssh_port
    if not host or not port:
        logger.info("Run %s missing SSH info; skipping log upload.", run.run_id)
        return
    upload_runpod_log_via_ssh(host=host, port=port, run_id=run.run_id)


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

        cost_per_hour = _extract_cost_per_hour(pod_info, run_id)
        db.update_research_pipeline_run(
            run_id=run_id,
            pod_info=pod_info,
            cost=cost_per_hour,
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
                "cost_per_hr": cost_per_hour,
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

    requester_first_name = extract_user_first_name(full_name=user.name)
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
        ResearchRunStageProgress.from_db_record(event)
        for event in db.list_stage_progress_events(run_id=run_id)
    ]
    log_events = [
        ResearchRunLogEntry.from_db_record(event) for event in db.list_run_log_events(run_id=run_id)
    ]
    substage_events = [
        ResearchRunSubstageEvent.from_db_record(event)
        for event in db.list_substage_completed_events(run_id=run_id)
    ]
    substage_summaries = [
        ResearchRunSubstageSummary.from_db_record(event)
        for event in db.list_substage_summary_events(run_id=run_id)
    ]
    best_node_selections = [
        ResearchRunBestNodeSelection.from_db_record(event)
        for event in db.list_best_node_reasoning_events(run_id=run_id)
    ]
    artifacts = [
        ResearchRunArtifactMetadata.from_db_record(
            artifact=artifact,
            conversation_id=conversation_id,
            run_id=run_id,
        )
        for artifact in db.list_run_artifacts(run_id=run_id)
    ]
    run_events = [
        ResearchRunEvent.from_db_record(event)
        for event in db.list_research_pipeline_run_events(run_id=run_id)
    ]
    tree_viz = [
        TreeVizItem.from_db_record(record) for record in db.list_tree_viz_for_run(run_id=run_id)
    ]
    paper_gen_events = [
        ResearchRunPaperGenerationProgress.from_db_record(event)
        for event in db.list_paper_generation_events(run_id=run_id)
    ]

    return ResearchRunDetailsResponse(
        run=ResearchRunInfo.from_db_record(run),
        stage_progress=stage_events,
        logs=log_events,
        substage_events=substage_events,
        substage_summaries=substage_summaries,
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
    return [TreeVizItem.from_db_record(record) for record in records]


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
    return TreeVizItem.from_db_record(record)
