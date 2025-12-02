import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.services import get_database
from app.services.research_pipeline import terminate_pod

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
    run_id: str
    event: StageProgressEvent


class ExperimentNodeCompletedEvent(BaseModel):
    stage: str
    node_id: Optional[str] = None
    summary: Dict[str, Any]


class ExperimentNodeCompletedPayload(BaseModel):
    run_id: str
    event: ExperimentNodeCompletedEvent


class RunStartedPayload(BaseModel):
    run_id: str


class RunFinishedPayload(BaseModel):
    run_id: str
    success: bool
    message: Optional[str] = None


class HeartbeatPayload(BaseModel):
    run_id: str


def _verify_bearer_token(authorization: str = Header(...)) -> None:
    expected_token = settings.TELEMETRY_WEBHOOK_TOKEN
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not configured to accept research pipeline events.",
        )
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
        )


@router.post("/stage-progress", status_code=status.HTTP_204_NO_CONTENT)
def ingest_stage_progress(
    payload: StageProgressPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    logger.info(
        "RP stage progress: run=%s stage=%s iteration=%s/%s progress=%.3f",
        payload.run_id,
        event.stage,
        event.iteration,
        event.max_iterations,
        event.progress,
    )


@router.post("/experiment-node-completed", status_code=status.HTTP_204_NO_CONTENT)
def ingest_experiment_node_completed(
    payload: ExperimentNodeCompletedPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    summary_keys = ", ".join(event.summary.keys())
    logger.info(
        "RP node completed: run=%s stage=%s node_id=%s summary_keys=[%s]",
        payload.run_id,
        event.stage,
        event.node_id,
        summary_keys,
    )


@router.post("/run-started", status_code=status.HTTP_204_NO_CONTENT)
def ingest_run_started(
    payload: RunStartedPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    now = datetime.now(timezone.utc)
    new_deadline = now + timedelta(minutes=5)
    db.update_research_pipeline_run(
        run_id=payload.run_id,
        status="running",
        last_heartbeat_at=now,
        heartbeat_failures=0,
        start_deadline_at=new_deadline,
    )
    db.insert_research_pipeline_run_event(
        run_id=payload.run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "running",
            "reason": "pipeline_event_start",
            "start_deadline_at": new_deadline.isoformat(),
        },
        occurred_at=now,
    )
    logger.info("RP run started: run=%s", payload.run_id)


@router.post("/run-finished", status_code=status.HTTP_204_NO_CONTENT)
def ingest_run_finished(
    payload: RunFinishedPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    new_status = "completed" if payload.success else "failed"
    now = datetime.now(timezone.utc)
    db.update_research_pipeline_run(
        run_id=payload.run_id,
        status=new_status,
        error_message=payload.message,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
    db.insert_research_pipeline_run_event(
        run_id=payload.run_id,
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

    if run.pod_id:
        try:
            logger.info(
                "Run %s finished (success=%s, message=%s); terminating pod %s.",
                payload.run_id,
                payload.success,
                payload.message,
                run.pod_id,
            )
            terminate_pod(pod_id=run.pod_id)
            logger.info("Terminated pod %s for run %s", run.pod_id, payload.run_id)
        except RuntimeError as exc:
            logger.warning("Failed to terminate pod %s: %s", run.pod_id, exc)


@router.post("/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def ingest_heartbeat(
    payload: HeartbeatPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        logger.warning(
            "Received heartbeat for unknown run_id=%s; ignoring but returning 204.",
            payload.run_id,
        )
        return
    now = datetime.now(timezone.utc)
    db.update_research_pipeline_run(
        run_id=payload.run_id,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
    logger.debug("RP heartbeat received for run=%s", payload.run_id)
