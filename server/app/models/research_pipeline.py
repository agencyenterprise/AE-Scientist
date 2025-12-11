"""
Pydantic models for research pipeline run APIs.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.conversations import ResearchRunSummary

# ============================================================================
# List API Models
# ============================================================================


class ResearchRunListItem(BaseModel):
    """Item in the research runs list with enriched data from related tables."""

    run_id: str = Field(..., description="Unique identifier of the run")
    status: str = Field(..., description="Current status of the run")
    idea_title: str = Field(..., description="Title from the idea version")
    idea_hypothesis: Optional[str] = Field(
        None, description="Short hypothesis from the idea version"
    )
    current_stage: Optional[str] = Field(None, description="Latest stage from progress events")
    progress: Optional[float] = Field(
        None, description="Progress percentage (0-1) from latest event"
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


class ResearchRunListResponse(BaseModel):
    """Response model for the research runs list API."""

    items: List[ResearchRunListItem] = Field(
        default_factory=list, description="List of research runs"
    )
    total: int = Field(..., description="Total count of research runs")


class ResearchRunInfo(ResearchRunSummary):
    start_deadline_at: Optional[str] = Field(
        None, description="ISO timestamp representing the start deadline window"
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


class ResearchRunLogEntry(BaseModel):
    id: int = Field(..., description="Unique identifier of the log event")
    level: str = Field(..., description="Log level (info, warn, error, ...)")
    message: str = Field(..., description="Log message")
    created_at: str = Field(..., description="ISO timestamp of the log event")


class ResearchRunEvent(BaseModel):
    id: int = Field(..., description="Unique identifier of the audit event")
    run_id: str = Field(..., description="Run identifier that produced the event")
    event_type: str = Field(..., description="Audit event type label")
    metadata: Dict[str, object] = Field(
        default_factory=dict,
        description="Structured metadata captured for the event",
    )
    occurred_at: str = Field(..., description="ISO timestamp when the event was recorded")


class ResearchRunSubstageEvent(BaseModel):
    id: int = Field(..., description="Unique identifier of the sub-stage completion event")
    stage: str = Field(..., description="Stage identifier")
    node_id: Optional[str] = Field(
        None,
        description="Optional identifier associated with the sub-stage (reserved for future use)",
    )
    summary: dict = Field(..., description="Summary payload stored for this sub-stage")
    created_at: str = Field(..., description="ISO timestamp of the event")


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


class ResearchRunArtifactMetadata(BaseModel):
    id: int = Field(..., description="Artifact identifier")
    artifact_type: str = Field(..., description="Artifact type label")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    created_at: str = Field(..., description="ISO timestamp when the artifact was recorded")
    download_path: str = Field(..., description="API path to initiate a download")


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
    stage_id: str = Field(..., description="Stage identifier (Stage_1..Stage_4)")
    version: int = Field(..., description="Version counter for the stored viz")
    viz: dict = Field(..., description="Tree visualization payload")
    created_at: str = Field(..., description="ISO timestamp when the viz was stored")
    updated_at: str = Field(..., description="ISO timestamp when the viz was last updated")


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
    originality: float = Field(..., description="Originality score (1-4)")
    quality: float = Field(..., description="Quality score (1-4)")
    clarity: float = Field(..., description="Clarity score (1-4)")
    significance: float = Field(..., description="Significance score (1-4)")
    questions: List[str] = Field(..., description="List of reviewer questions")
    limitations: List[str] = Field(..., description="List of identified limitations")
    ethical_concerns: bool = Field(..., description="Whether ethical concerns were raised")
    soundness: float = Field(..., description="Soundness score (1-4)")
    presentation: float = Field(..., description="Presentation score (1-4)")
    contribution: float = Field(..., description="Contribution score (1-4)")
    overall: float = Field(..., description="Overall quality score (1-10)")
    confidence: float = Field(..., description="Reviewer confidence score (1-5)")
    decision: str = Field(..., description="Final decision ('Accept' or 'Reject')")
    source_path: Optional[str] = Field(None, description="Source path or reference for the review")
    created_at: str = Field(..., description="ISO timestamp when the review was created")


class LlmReviewNotFoundResponse(BaseModel):
    """Response model when no review exists for a run."""

    run_id: str = Field(..., description="Research run identifier")
    exists: bool = Field(False, description="Indicates no review exists")
    message: str = Field(..., description="Explanation that no review was found")
