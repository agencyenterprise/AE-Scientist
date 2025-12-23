import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence, cast

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.api.research_pipeline_runs import (
    REQUESTER_NAME_FALLBACK,
    IdeaPayloadSource,
    PodLaunchError,
    create_and_launch_research_run,
    extract_user_first_name,
)
from app.api.research_pipeline_stream import StreamEventModel, publish_stream_event
from app.config import settings
from app.models.research_pipeline import ResearchRunBestNodeSelection
from app.models.research_pipeline import ResearchRunEvent as RPEvent
from app.models.research_pipeline import (
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
)
from app.models.research_pipeline import ResearchRunSubstageEvent as RPSubstageEvent
from app.models.research_pipeline import ResearchRunSubstageSummary
from app.models.sse import ResearchRunBestNodeEvent as SSEBestNodeEvent
from app.models.sse import ResearchRunCodeExecutionCompletedData
from app.models.sse import ResearchRunCodeExecutionCompletedEvent as SSECodeExecutionCompletedEvent
from app.models.sse import ResearchRunCodeExecutionStartedData
from app.models.sse import ResearchRunCodeExecutionStartedEvent as SSECodeExecutionStartedEvent
from app.models.sse import ResearchRunCompleteData
from app.models.sse import ResearchRunCompleteEvent as SSECompleteEvent
from app.models.sse import ResearchRunLogEvent as SSELogEvent
from app.models.sse import ResearchRunPaperGenerationEvent as SSEPaperGenerationEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.sse import ResearchRunStageProgressEvent as SSEStageProgressEvent
from app.models.sse import ResearchRunSubstageCompletedEvent
from app.models.sse import ResearchRunSubstageSummaryEvent as SSESubstageSummaryEvent
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline import (
    RunPodError,
    fetch_pod_billing_summary,
    terminate_pod,
    upload_runpod_artifacts_via_ssh,
)

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


class SubstageCompletedEvent(BaseModel):
    stage: str
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]


class SubstageCompletedPayload(BaseModel):
    run_id: str
    event: SubstageCompletedEvent


class SubstageSummaryEvent(BaseModel):
    stage: str
    summary: Dict[str, Any]


class SubstageSummaryPayload(BaseModel):
    run_id: str
    event: SubstageSummaryEvent


class RunStartedPayload(BaseModel):
    run_id: str


class RunFinishedPayload(BaseModel):
    run_id: str
    success: bool
    message: Optional[str] = None


class HeartbeatPayload(BaseModel):
    run_id: str


class GPUShortagePayload(BaseModel):
    run_id: str
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
    run_id: str
    event: PaperGenerationProgressEvent


class BestNodeSelectionEvent(BaseModel):
    stage: str
    node_id: str
    reasoning: str


class BestNodeSelectionPayload(BaseModel):
    run_id: str
    event: BestNodeSelectionEvent


class TreeVizStoredEvent(BaseModel):
    stage_id: str
    tree_viz_id: int
    version: int


class TreeVizStoredPayload(BaseModel):
    run_id: str
    event: TreeVizStoredEvent


class RunLogEvent(BaseModel):
    message: str
    level: str = "info"


class RunLogPayload(BaseModel):
    run_id: str
    event: RunLogEvent


class RunningCodeEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    code: str
    started_at: str
    run_type: str = "main_execution"


class RunningCodePayload(BaseModel):
    run_id: str
    event: RunningCodeEventPayload


class RunCompletedEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: str
    run_type: str = "main_execution"


class RunCompletedPayload(BaseModel):
    run_id: str
    event: RunCompletedEventPayload


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
    metadata = summary._asdict()
    metadata["records"] = [record._asdict() for record in summary.records]
    metadata["context"] = context
    db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=datetime.now(timezone.utc),
    )


def _upload_pod_artifacts_if_possible(run: ResearchPipelineRun) -> None:
    host = run.public_ip
    port = run.ssh_port
    if not host or not port:
        logger.info("Run %s missing SSH info; skipping log upload.", run.run_id)
        return
    upload_runpod_artifacts_via_ssh(host=host, port=port, run_id=run.run_id)


def _resolve_run_owner_first_name(*, db: DatabaseManager, run_id: str) -> str:
    owner_id = db.get_run_owner_user_id(run_id=run_id)
    if owner_id is None:
        return REQUESTER_NAME_FALLBACK
    user = db.get_user_by_id(user_id=owner_id)
    if user is None:
        return REQUESTER_NAME_FALLBACK
    return extract_user_first_name(full_name=user.name)


def _next_stream_event_id() -> int:
    return int(time.time() * 1000)


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
        run_id=payload.run_id,
        event=SSEStageProgressEvent(
            type="stage_progress",
            data=progress,
        ),
    )


@router.post("/substage-completed", status_code=status.HTTP_204_NO_CONTENT)
def ingest_substage_completed(
    payload: SubstageCompletedPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    logger.info(
        "RP sub-stage completed: run=%s stage=%s reason=%s",
        payload.run_id,
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
        run_id=payload.run_id,
        event=cast(
            StreamEventModel,
            ResearchRunSubstageCompletedEvent(
                type="substage_completed",
                data=substage_event,
            ),
        ),
    )


@router.post("/paper-generation-progress", status_code=status.HTTP_204_NO_CONTENT)
def ingest_paper_generation_progress(
    payload: PaperGenerationProgressPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    logger.info(
        "Paper generation progress: run=%s step=%s substep=%s progress=%.1f%% step_progress=%.1f%%",
        payload.run_id,
        event.step,
        event.substep or "N/A",
        event.progress * 100,
        event.step_progress * 100,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    paper_event = ResearchRunPaperGenerationProgress(
        id=_next_stream_event_id(),
        run_id=payload.run_id,
        step=event.step,
        substep=event.substep,
        progress=event.progress,
        step_progress=event.step_progress,
        details=event.details,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=payload.run_id,
        event=SSEPaperGenerationEvent(
            type="paper_generation_progress",
            data=paper_event,
        ),
    )


@router.post("/substage-summary", status_code=status.HTTP_204_NO_CONTENT)
def ingest_substage_summary(
    payload: SubstageSummaryPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    logger.info(
        "RP sub-stage summary: run=%s stage=%s",
        payload.run_id,
        event.stage,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    summary_model = ResearchRunSubstageSummary(
        id=_next_stream_event_id(),
        stage=event.stage,
        summary=event.summary,
        created_at=created_at,
    )
    publish_stream_event(
        run_id=payload.run_id,
        event=SSESubstageSummaryEvent(
            type="substage_summary",
            data=summary_model,
        ),
    )


@router.post("/best-node-selection", status_code=status.HTTP_204_NO_CONTENT)
def ingest_best_node_selection(
    payload: BestNodeSelectionPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    reasoning_preview = (
        event.reasoning if len(event.reasoning) <= 200 else f"{event.reasoning[:197]}..."
    )
    logger.info(
        "RP best-node selection: run=%s stage=%s node=%s reasoning=%s",
        payload.run_id,
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
        run_id=payload.run_id,
        event=SSEBestNodeEvent(
            type="best_node_selection",
            data=best_node,
        ),
    )


@router.post("/tree-viz-stored", status_code=status.HTTP_204_NO_CONTENT)
def ingest_tree_viz_stored(
    payload: "TreeVizStoredPayload",
    _: None = Depends(_verify_bearer_token),
) -> None:
    event = payload.event
    logger.info(
        "Tree viz stored: run=%s stage=%s tree_viz_id=%s version=%s",
        payload.run_id,
        event.stage_id,
        event.tree_viz_id,
        event.version,
    )
    created_at = datetime.now(timezone.utc).isoformat()

    # Create run event for SSE streaming
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=payload.run_id,
        event_type="tree_viz_stored",
        metadata={
            "stage_id": event.stage_id,
            "tree_viz_id": event.tree_viz_id,
            "version": event.version,
        },
        occurred_at=created_at,
    )

    # Publish to SSE stream
    publish_stream_event(
        run_id=payload.run_id,
        event=SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )


@router.post("/run-log", status_code=status.HTTP_204_NO_CONTENT)
def ingest_run_log(
    payload: RunLogPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    logger.debug(
        "RP log event received: run=%s level=%s message=%s",
        payload.run_id,
        payload.event.level,
        payload.event.message,
    )
    publish_stream_event(
        run_id=payload.run_id,
        event=SSELogEvent(
            type="log",
            data=ResearchRunLogEntry(
                id=_next_stream_event_id(),
                level=payload.event.level,
                message=payload.event.message,
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        ),
    )


@router.post("/running-code", status_code=status.HTTP_204_NO_CONTENT)
def ingest_running_code(
    payload: RunningCodePayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event = payload.event
    publish_stream_event(
        run_id=payload.run_id,
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


@router.post("/run-completed", status_code=status.HTTP_204_NO_CONTENT)
def ingest_run_completed(
    payload: RunCompletedPayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    event = payload.event
    publish_stream_event(
        run_id=payload.run_id,
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
        started_running_at=now,
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
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=payload.run_id,
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
        payload.run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
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
    run_event = RPEvent(
        id=_next_stream_event_id(),
        run_id=payload.run_id,
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
        payload.run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )
    publish_stream_event(
        payload.run_id,
        SSECompleteEvent(
            type="complete",
            data=ResearchRunCompleteData(
                status=new_status,  # type: ignore[arg-type]
                success=payload.success,
                message=payload.message,
            ),
        ),
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
        finally:
            _record_pod_billing_event(
                db,
                run_id=payload.run_id,
                pod_id=run.pod_id,
                context="pipeline_event_finish",
            )


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


@router.post("/gpu-shortage", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_gpu_shortage(
    payload: GPUShortagePayload,
    _: None = Depends(_verify_bearer_token),
) -> None:
    db = get_database()
    run = db.get_research_pipeline_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    failure_reason = (
        payload.message
        or f"Pipeline aborted: requires {payload.required_gpus} GPU(s) but detected {payload.available_gpus}."
    )
    now = datetime.now(timezone.utc)
    logger.warning(
        "RP GPU shortage: run=%s required=%s available=%s",
        payload.run_id,
        payload.required_gpus,
        payload.available_gpus,
    )
    db.update_research_pipeline_run(
        run_id=payload.run_id,
        status="failed",
        error_message=failure_reason,
        last_heartbeat_at=now,
        heartbeat_failures=0,
    )
    db.insert_research_pipeline_run_event(
        run_id=payload.run_id,
        event_type="gpu_shortage",
        metadata={
            "required_gpus": payload.required_gpus,
            "available_gpus": payload.available_gpus,
            "message": failure_reason,
        },
        occurred_at=now,
    )
    db.insert_research_pipeline_run_event(
        run_id=payload.run_id,
        event_type="status_changed",
        metadata={
            "from_status": run.status,
            "to_status": "failed",
            "reason": "gpu_shortage",
            "message": failure_reason,
        },
        occurred_at=now,
    )
    if run.pod_id:
        _upload_pod_artifacts_if_possible(run)
        try:
            terminate_pod(pod_id=run.pod_id)
            logger.info(
                "Terminated pod %s for run %s after GPU shortage.",
                run.pod_id,
                payload.run_id,
            )
        except RuntimeError as exc:
            logger.warning("Failed to terminate pod %s: %s", run.pod_id, exc)
        finally:
            _record_pod_billing_event(
                db,
                run_id=payload.run_id,
                pod_id=run.pod_id,
                context="gpu_shortage",
            )
    try:
        await _retry_run_after_gpu_shortage(db=db, failed_run=run)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to schedule retry run after GPU shortage for run %s",
            payload.run_id,
        )


async def _retry_run_after_gpu_shortage(
    *, db: DatabaseManager, failed_run: ResearchPipelineRun
) -> None:
    version_id = failed_run.idea_version_id
    idea_version = db.get_idea_version_by_id(version_id)
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
        short_hypothesis=idea_version.short_hypothesis,
        related_work=idea_version.related_work,
        abstract=idea_version.abstract,
        experiments=_coerce_list(idea_version.experiments),
        expected_outcome=idea_version.expected_outcome,
        risk_factors_and_limitations=_coerce_list(idea_version.risk_factors_and_limitations),
    )
    requester_first_name = _resolve_run_owner_first_name(db=db, run_id=failed_run.run_id)
    try:
        new_run_id, _pod_info = await create_and_launch_research_run(
            idea_data=idea_payload,
            requested_by_first_name=requester_first_name,
        )
        logger.info(
            "Scheduled retry run %s after GPU shortage on run %s.",
            new_run_id,
            failed_run.run_id,
        )
        db.insert_research_pipeline_run_event(
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


@dataclass(frozen=True)
class RetryIdeaPayload(IdeaPayloadSource):
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
