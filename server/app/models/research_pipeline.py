"""
Pydantic models for research pipeline run APIs.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.conversations import ResearchRunSummary
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.database.research_pipeline_runs import (
    ResearchPipelineRunEvent as DBResearchRunEvent,
)
from app.services.database.rp_artifacts import ResearchPipelineArtifact
from app.services.database.rp_events import (
    BestNodeReasoningEvent,
    CodeExecutionEvent,
    PaperGenerationEvent,
    RunLogEvent,
    StageProgressEvent,
    StageSkipWindowRecord,
    SubstageCompletedEvent,
    SubstageSummaryEvent,
)
from app.services.database.rp_tree_viz import TreeVizRecord


class RunType(str, Enum):
    """Execution stream identifier for research pipeline code execution telemetry."""

    CODEX_EXECUTION = "codex_execution"
    RUNFILE_EXECUTION = "runfile_execution"


def parse_run_type(*, run_type: str) -> RunType:
    """
    Convert persisted run_type strings into the supported RunType enum.

    Notes:
    - Some older DB rows may contain legacy values like "main_execution".
    - Unknown values are mapped to RUNFILE_EXECUTION to avoid 500s while keeping the API stable.
    """
    normalized = run_type.strip().lower()
    if normalized == RunType.CODEX_EXECUTION.value:
        return RunType.CODEX_EXECUTION
    if normalized in (RunType.RUNFILE_EXECUTION.value, "main_execution"):
        return RunType.RUNFILE_EXECUTION
    return RunType.RUNFILE_EXECUTION


# ============================================================================
# List API Models
# ============================================================================


class ResearchRunListItem(BaseModel):
    """Item in the research runs list with enriched data from related tables."""

    run_id: str = Field(..., description="Unique identifier of the run")
    status: str = Field(..., description="Current status of the run")
    initialization_status: str = Field(
        ..., description="Initialization status message (pending/initializing/running)"
    )
    idea_title: str = Field(..., description="Title from the idea version")
    idea_hypothesis: Optional[str] = Field(
        None, description="Short hypothesis from the idea version"
    )
    current_stage: Optional[str] = Field(None, description="Latest stage from progress events")
    progress: Optional[float] = Field(
        None,
        description=(
            "Overall pipeline progress (0-1) computed as completed-stages-only buckets "
            "(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)."
        ),
    )
    gpu_type: Optional[str] = Field(None, description="GPU type used for the run")
    cost: float = Field(..., description="Hourly RunPod cost (USD) captured when the pod launched")
    best_metric: Optional[str] = Field(None, description="Best metric from latest progress event")
    created_by_name: str = Field(..., description="Name of the user who created the run")
    created_at: str = Field(..., description="ISO timestamp when the run was created")
    updated_at: str = Field(..., description="ISO timestamp when the run was last updated")
    artifacts_count: int = Field(0, description="Number of artifacts produced by this run")
    error_message: Optional[str] = Field(None, description="Error message if the run failed")
    conversation_id: int = Field(..., description="ID of the associated conversation")
    parent_run_id: Optional[str] = Field(
        None,
        description="Parent run ID if this run's conversation was seeded from a previous run",
    )


class ResearchRunListResponse(BaseModel):
    """Response model for the research runs list API."""

    items: List[ResearchRunListItem] = Field(
        default_factory=list, description="List of research runs"
    )
    total: int = Field(..., description="Total count of research runs")


class ResearchRunInfo(ResearchRunSummary):
    initialization_status: str = Field(
        ..., description="Initialization status message (pending/initializing/running)"
    )
    start_deadline_at: Optional[str] = Field(
        None, description="ISO timestamp representing the start deadline window"
    )
    termination_status: Literal["none", "requested", "in_progress", "terminated", "failed"] = Field(
        ...,
        description="Termination workflow status for the associated pod cleanup.",
    )
    termination_last_error: Optional[str] = Field(
        None,
        description="Last termination workflow error, if any.",
    )
    parent_run_id: Optional[str] = Field(
        None,
        description="Parent run ID if this run's conversation was seeded from a previous run",
    )
    restart_count: int = Field(
        0,
        description="Number of times this run has been restarted due to pod failures",
    )
    last_restart_at: Optional[str] = Field(
        None,
        description="ISO timestamp of the last pod restart",
    )
    last_restart_reason: Optional[str] = Field(
        None,
        description="Reason for the last restart (heartbeat_timeout or container_died)",
    )

    @staticmethod
    def from_db_record(
        *,
        run: ResearchPipelineRun,
        termination: ResearchPipelineRunTermination | None,
        parent_run_id: Optional[str] = None,
    ) -> "ResearchRunInfo":
        termination_status: Literal["none", "requested", "in_progress", "terminated", "failed"] = (
            "none"
        )
        termination_last_error: Optional[str] = None

        if termination is not None:
            if termination.status == "requested":
                termination_status = "requested"
            elif termination.status == "in_progress":
                termination_status = "in_progress"
            elif termination.status == "terminated":
                termination_status = "terminated"
            elif termination.status == "failed":
                termination_status = "failed"
            termination_last_error = termination.last_error

        return ResearchRunInfo(
            run_id=run.run_id,
            status=run.status,
            initialization_status=run.initialization_status,
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
            termination_status=termination_status,
            termination_last_error=termination_last_error,
            parent_run_id=parent_run_id,
            restart_count=run.restart_count,
            last_restart_at=run.last_restart_at.isoformat() if run.last_restart_at else None,
            last_restart_reason=run.last_restart_reason,
        )


class ResearchRunStageProgress(BaseModel):
    stage: str = Field(..., description="Stage identifier")
    iteration: int = Field(..., description="Current iteration number")
    max_iterations: int = Field(..., description="Maximum iterations for the stage")
    progress: float = Field(..., description="Progress percentage (0-1)")
    total_nodes: int = Field(..., description="Total nodes considered so far")
    buggy_nodes: int = Field(..., description="Number of buggy nodes")
    good_nodes: int = Field(..., description="Number of good nodes")
    best_metric: Optional[str] = Field(None, description="Best metric reported at this stage")
    eta_s: Optional[int] = Field(None, description="Estimated time remaining in seconds")
    latest_iteration_time_s: Optional[int] = Field(
        None, description="Duration of the latest iteration in seconds"
    )
    created_at: str = Field(..., description="ISO timestamp when the event was recorded")

    @staticmethod
    def from_db_record(event: StageProgressEvent) -> "ResearchRunStageProgress":
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


class ResearchRunLogEntry(BaseModel):
    id: int = Field(..., description="Unique identifier of the log event")
    level: str = Field(..., description="Log level (info, warn, error, ...)")
    message: str = Field(..., description="Log message")
    created_at: str = Field(..., description="ISO timestamp of the log event")

    @staticmethod
    def from_db_record(event: RunLogEvent) -> "ResearchRunLogEntry":
        return ResearchRunLogEntry(
            id=event.id,
            level=event.level,
            message=event.message,
            created_at=event.created_at.isoformat(),
        )


class ResearchRunEvent(BaseModel):
    id: int = Field(..., description="Unique identifier of the audit event")
    run_id: str = Field(..., description="Run identifier that produced the event")
    event_type: str = Field(..., description="Audit event type label")
    metadata: Dict[str, object] = Field(
        default_factory=dict,
        description="Structured metadata captured for the event",
    )
    occurred_at: str = Field(..., description="ISO timestamp when the event was recorded")

    @staticmethod
    def from_db_record(event: DBResearchRunEvent) -> "ResearchRunEvent":
        return ResearchRunEvent(
            id=event.id,
            run_id=event.run_id,
            event_type=event.event_type,
            metadata=event.metadata,
            occurred_at=event.occurred_at.isoformat(),
        )


class ResearchRunSubstageEvent(BaseModel):
    id: int = Field(..., description="Unique identifier of the sub-stage completion event")
    stage: str = Field(..., description="Stage identifier")
    node_id: Optional[str] = Field(
        None,
        description="Optional identifier associated with the sub-stage (reserved for future use)",
    )
    summary: dict = Field(..., description="Summary payload stored for this sub-stage")
    created_at: str = Field(..., description="ISO timestamp of the event")

    @staticmethod
    def from_db_record(event: SubstageCompletedEvent) -> "ResearchRunSubstageEvent":
        return ResearchRunSubstageEvent(
            id=event.id,
            stage=event.stage,
            node_id=None,
            summary=event.summary,
            created_at=event.created_at.isoformat(),
        )


class ResearchRunSubstageSummary(BaseModel):
    id: int = Field(..., description="Unique identifier of the sub-stage summary event")
    stage: str = Field(..., description="Stage identifier")
    summary: dict = Field(..., description="LLM-generated summary payload")
    created_at: str = Field(..., description="ISO timestamp when the summary was recorded")

    @staticmethod
    def from_db_record(event: SubstageSummaryEvent) -> "ResearchRunSubstageSummary":
        return ResearchRunSubstageSummary(
            id=event.id,
            stage=event.stage,
            summary=event.summary,
            created_at=event.created_at.isoformat(),
        )


class ResearchRunBestNodeSelection(BaseModel):
    id: int = Field(..., description="Unique identifier of the reasoning record")
    stage: str = Field(..., description="Stage identifier where the selection happened")
    node_id: str = Field(..., description="Identifier of the selected node")
    reasoning: str = Field(..., description="LLM reasoning that justified the selection")
    created_at: str = Field(..., description="ISO timestamp when the reasoning was recorded")

    @staticmethod
    def from_db_record(event: BestNodeReasoningEvent) -> "ResearchRunBestNodeSelection":
        return ResearchRunBestNodeSelection(
            id=event.id,
            stage=event.stage,
            node_id=event.node_id,
            reasoning=event.reasoning,
            created_at=event.created_at.isoformat(),
        )


class ResearchRunStageSkipWindow(BaseModel):
    id: int = Field(..., description="Unique identifier for the skip window record")
    stage: str = Field(..., description="Stage identifier where skipping became possible")
    opened_at: str = Field(..., description="ISO timestamp when the window opened")
    opened_reason: Optional[str] = Field(None, description="Reason provided when the window opened")
    closed_at: Optional[str] = Field(
        None, description="ISO timestamp when the window closed (if closed)"
    )
    closed_reason: Optional[str] = Field(None, description="Reason provided when the window closed")

    @staticmethod
    def from_db_record(record: StageSkipWindowRecord) -> "ResearchRunStageSkipWindow":
        return ResearchRunStageSkipWindow(
            id=record.id,
            stage=record.stage,
            opened_at=record.opened_at.isoformat(),
            opened_reason=record.opened_reason,
            closed_at=record.closed_at.isoformat() if record.closed_at else None,
            closed_reason=record.closed_reason,
        )


class ResearchRunPaperGenerationProgress(BaseModel):
    id: int = Field(..., description="Unique identifier of the paper generation event")
    run_id: str = Field(..., description="Research run identifier")
    step: str = Field(
        ...,
        description="Current step: plot_aggregation, citation_gathering, paper_writeup, or paper_review",
    )
    substep: Optional[str] = Field(
        None, description="Substep identifier (e.g., 'round_1', 'revision_2')"
    )
    progress: float = Field(..., description="Overall progress (0.0-1.0)")
    step_progress: float = Field(..., description="Progress within current step (0.0-1.0)")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Step-specific metadata (figures, citations, scores, etc.)"
    )
    created_at: str = Field(..., description="ISO timestamp when the event was recorded")

    @staticmethod
    def from_db_record(event: PaperGenerationEvent) -> "ResearchRunPaperGenerationProgress":
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


class ResearchRunCodeExecution(BaseModel):
    """Latest code execution snapshot for a run."""

    execution_id: str = Field(..., description="Unique identifier for the code execution attempt")
    stage_name: str = Field(..., description="Stage name reported by the research pipeline")
    run_type: RunType = Field(
        ...,
        description="Type of execution ('codex_execution' for the Codex session, 'runfile_execution' for the runfile command).",
    )
    code: Optional[str] = Field(None, description="Python source code submitted for execution")
    status: str = Field(..., description="Execution status reported by the worker")
    started_at: str = Field(..., description="ISO timestamp when execution began")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when execution ended")
    exec_time: Optional[float] = Field(None, description="Execution time reported by the worker")

    @staticmethod
    def from_db_record(record: "CodeExecutionEvent") -> "ResearchRunCodeExecution":
        return ResearchRunCodeExecution(
            execution_id=record.execution_id,
            stage_name=record.stage_name,
            run_type=parse_run_type(run_type=record.run_type),
            code=record.code,
            status=record.status,
            started_at=record.started_at.isoformat(),
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            exec_time=record.exec_time,
        )


class ResearchRunArtifactMetadata(BaseModel):
    id: int = Field(..., description="Artifact identifier")
    artifact_type: str = Field(..., description="Artifact type label")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    created_at: str = Field(..., description="ISO timestamp when the artifact was recorded")
    run_id: str = Field(..., description="Research run identifier")
    conversation_id: Optional[int] = Field(None, description="ID of the associated conversation")

    @staticmethod
    def from_db_record(
        artifact: ResearchPipelineArtifact,
        conversation_id: int,
        run_id: str,
    ) -> "ResearchRunArtifactMetadata":
        return ResearchRunArtifactMetadata(
            id=artifact.id,
            artifact_type=artifact.artifact_type,
            filename=artifact.filename,
            file_size=artifact.file_size,
            file_type=artifact.file_type,
            created_at=artifact.created_at.isoformat(),
            run_id=run_id,
            conversation_id=conversation_id,
        )


class ArtifactPresignedUrlResponse(BaseModel):
    """Response containing presigned S3 download URL."""

    url: str = Field(..., description="Presigned S3 download URL (valid for 1 hour)")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    artifact_id: int = Field(..., description="Artifact identifier")
    filename: str = Field(..., description="Original filename")


class TreeVizItem(BaseModel):
    """Stored tree visualization payload for a run stage."""

    id: int = Field(..., description="Tree viz identifier")
    run_id: str = Field(..., description="Research run identifier")
    stage_id: str = Field(..., description="Stage identifier (stage_1..stage_4)")
    version: int = Field(..., description="Version counter for the stored viz")
    viz: dict = Field(..., description="Tree visualization payload")
    created_at: str = Field(..., description="ISO timestamp when the viz was stored")
    updated_at: str = Field(..., description="ISO timestamp when the viz was last updated")

    @staticmethod
    def from_db_record(record: TreeVizRecord) -> "TreeVizItem":
        return TreeVizItem(
            id=record.id,
            run_id=record.run_id,
            stage_id=record.stage_id,
            version=record.version,
            viz=record.viz,
            created_at=record.created_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
        )


class ChildConversationInfo(BaseModel):
    """Brief info about a child conversation seeded from a run."""

    conversation_id: int = Field(..., description="Child conversation ID")
    title: str = Field(..., description="Child conversation title")
    created_at: str = Field(..., description="ISO timestamp when created")
    status: str = Field(..., description="Conversation status")


class ResearchRunDetailsResponse(BaseModel):
    run: ResearchRunInfo = Field(..., description="Metadata describing the run")
    stage_progress: List[ResearchRunStageProgress] = Field(
        default_factory=list, description="Stage progress telemetry"
    )
    logs: List[ResearchRunLogEntry] = Field(
        default_factory=list, description="Log events generated by the run"
    )
    substage_events: List[ResearchRunSubstageEvent] = Field(
        default_factory=list, description="Sub-stage completion events"
    )
    substage_summaries: List[ResearchRunSubstageSummary] = Field(
        default_factory=list,
        description="LLM-generated summaries for completed sub-stages",
    )
    best_node_selections: List[ResearchRunBestNodeSelection] = Field(
        default_factory=list,
        description="Reasoning records captured whenever a best node is selected",
    )
    events: List[ResearchRunEvent] = Field(
        default_factory=list,
        description="Audit events describing run-level lifecycle transitions",
    )
    artifacts: List[ResearchRunArtifactMetadata] = Field(
        default_factory=list, description="Artifacts uploaded for the run"
    )
    tree_viz: List[TreeVizItem] = Field(
        default_factory=list,
        description="Tree visualizations stored for this run",
    )
    paper_generation_progress: List[ResearchRunPaperGenerationProgress] = Field(
        default_factory=list, description="Paper generation progress events (Stage 5)"
    )
    stage_skip_windows: List[ResearchRunStageSkipWindow] = Field(
        default_factory=list,
        description="Windows indicating when each stage became skippable.",
    )
    child_conversations: List[ChildConversationInfo] = Field(
        default_factory=list,
        description="Conversations that were seeded from this run",
    )


# ============================================================================
# LLM Review Models
# ============================================================================


class LlmReviewResponse(BaseModel):
    """Response model for LLM review data."""

    id: int = Field(..., description="Unique identifier of the review")
    run_id: str = Field(..., description="Research run identifier")
    summary: str = Field(..., description="Executive summary of the review")
    strengths: List[str] = Field(..., description="List of identified strengths")
    weaknesses: List[str] = Field(..., description="List of identified weaknesses")
    originality: int = Field(..., description="Originality score (1-4)")
    quality: int = Field(..., description="Quality score (1-4)")
    clarity: int = Field(..., description="Clarity score (1-4)")
    significance: int = Field(..., description="Significance score (1-4)")
    questions: List[str] = Field(..., description="List of reviewer questions")
    limitations: List[str] = Field(..., description="List of identified limitations")
    ethical_concerns: bool = Field(..., description="Whether ethical concerns were raised")
    soundness: int = Field(..., description="Soundness score (1-4)")
    presentation: int = Field(..., description="Presentation score (1-4)")
    contribution: int = Field(..., description="Contribution score (1-4)")
    overall: int = Field(..., description="Overall quality score (1-10)")
    confidence: int = Field(..., description="Reviewer confidence score (1-5)")
    decision: str = Field(..., description="Final decision ('Accept' or 'Reject')")
    source_path: Optional[str] = Field(None, description="Source path or reference for the review")
    created_at: str = Field(..., description="ISO timestamp when the review was created")


class LlmReviewNotFoundResponse(BaseModel):
    """Response model when no review exists for a run."""

    run_id: str = Field(..., description="Research run identifier")
    exists: bool = Field(False, description="Indicates no review exists")
    message: str = Field(..., description="Explanation that no review was found")


# ============================================================================
# Run Tree Models
# ============================================================================


class RunTreeNode(BaseModel):
    """A single node in the run tree (ancestors and descendants)."""

    run_id: str = Field(..., description="Unique identifier of the run")
    idea_title: str = Field(..., description="Title of the idea for this run")
    status: str = Field(..., description="Current status of the run")
    created_at: Optional[str] = Field(None, description="ISO timestamp when the run was created")
    parent_run_id: Optional[str] = Field(
        None, description="Parent run ID if this run was seeded from another run"
    )
    conversation_id: int = Field(..., description="ID of the conversation for this run")
    is_current: bool = Field(False, description="Whether this is the currently viewed run")


class RunTreeResponse(BaseModel):
    """Response containing the full tree of runs (ancestors and descendants)."""

    nodes: List[RunTreeNode] = Field(
        default_factory=list,
        description="List of all runs in the tree, ordered by creation time",
    )
