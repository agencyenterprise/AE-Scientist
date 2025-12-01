import logging
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import (
    ResearchRunArtifactMetadata,
    ResearchRunDetailsResponse,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunNodeEvent,
    ResearchRunStageProgress,
)
from app.services import get_database
from app.services.database.ideas import IdeaData
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.database.rp_artifacts import ResearchPipelineArtifact
from app.services.database.rp_events import ExperimentNodeEvent, RunLogEvent, StageProgressEvent
from app.services.research_pipeline.runpod_launcher import RunPodError, launch_research_pipeline_run
from app.services.s3_service import get_s3_service

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)


class ResearchRunAcceptedResponse(BaseModel):
    run_id: str
    status: str = "ok"


def _idea_version_to_payload(idea_data: IdeaData) -> Dict[str, object]:
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


def _launch_research_pipeline_job(*, run_id: str, idea_payload: Dict[str, object]) -> None:
    """Background task that launches the RunPod job and updates DB state."""
    db = get_database()
    config_name = f"{run_id}_config.yaml"
    try:
        logger.info("Launching research pipeline job in background for run_id=%s", run_id)
        pod_info = launch_research_pipeline_run(
            idea=idea_payload,
            config_name=config_name,
            run_id=run_id,
        )
        db.update_research_pipeline_run(run_id=run_id, pod_info=pod_info)
    except (RunPodError, FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.exception("Failed to launch research pipeline run.")
        db.update_research_pipeline_run(run_id=run_id, status="failed", error_message=str(exc))
    else:
        logger.info("Background launch complete for run_id=%s", run_id)


def _run_to_info(run: ResearchPipelineRun) -> ResearchRunInfo:
    return ResearchRunInfo(
        run_id=run.run_id,
        status=run.status,
        idea_id=run.idea_id,
        idea_version_id=run.idea_version_id,
        pod_id=run.pod_id,
        pod_name=run.pod_name,
        gpu_type=run.gpu_type,
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


def _node_event_to_model(event: ExperimentNodeEvent) -> ResearchRunNodeEvent:
    return ResearchRunNodeEvent(
        id=event.id,
        stage=event.stage,
        node_id=event.node_id,
        summary=event.summary,
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

    run_id = f"rp-{uuid4().hex[:10]}"
    db.create_research_pipeline_run(
        run_id=run_id,
        idea_id=idea_data.idea_id,
        idea_version_id=idea_data.version_id,
    )

    idea_payload = _idea_version_to_payload(idea_data)
    background_tasks.add_task(
        _launch_research_pipeline_job,
        run_id=run_id,
        idea_payload=idea_payload,
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

    stage_events = [_stage_event_to_model(event) for event in db.list_stage_progress_events(run_id)]
    log_events = [_log_event_to_model(event) for event in db.list_run_log_events(run_id)]
    node_events = [_node_event_to_model(event) for event in db.list_experiment_node_events(run_id)]
    artifacts = [
        _artifact_to_model(artifact, conversation_id, run_id)
        for artifact in db.list_run_artifacts(run_id)
    ]

    return ResearchRunDetailsResponse(
        run=_run_to_info(run),
        stage_progress=stage_events,
        logs=log_events,
        experiment_nodes=node_events,
        artifacts=artifacts,
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
