"""
Timeline Event Schemas for Narrator-based UX

These schemas define the narrative events that appear in the research run timeline UI.
They transform raw execution events into user-friendly descriptions.
"""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ============================================================================
# PRIMITIVES
# ============================================================================


class MetricInterpretation(BaseModel):
    """
    Interpreted metric with human-readable context.
    
    Transforms raw metric (0.8234567) into meaningful information:
    - Formatted: "82.3%"
    - Interpretation: "5.2% above baseline"
    """

    name: str = Field(..., description="Metric name", examples=["accuracy", "f1_score"])
    value: float = Field(..., description="Raw metric value")
    formatted: str = Field(
        ..., description="Formatted for display", examples=["82.3%", "0.823"]
    )
    interpretation: Optional[str] = Field(
        None,
        description="What this value means",
        examples=["5.2% above baseline", "Best result so far"],
    )
    context: Optional[str] = Field(
        None,
        description="Evaluation context",
        examples=["Validation set", "Test dataset"],
    )
    comparison: Optional[Dict[str, Any]] = Field(
        None,
        description="Comparison with baseline/previous best",
        examples=[
            {
                "baseline": 0.77,
                "previous_best": 0.81,
                "delta_vs_baseline": 0.053,
                "delta_vs_previous": 0.013,
            }
        ],
    )


class MetricCollection(BaseModel):
    """Group of related metrics for a node or stage."""

    primary: MetricInterpretation = Field(..., description="Primary metric being optimized")
    secondary: List[MetricInterpretation] = Field(
        default_factory=list, description="Additional metrics tracked"
    )


# ============================================================================
# TIMELINE EVENT BASE
# ============================================================================


class TimelineEventBase(BaseModel):
    """Base class for all timeline events."""

    id: str = Field(..., description="Unique event ID (UUID)")
    timestamp: datetime = Field(..., description="When this event occurred")
    stage: str = Field(..., description="Stage identifier (e.g., '1_initial_implementation')")
    node_id: Optional[str] = Field(None, description="Node ID if event relates to specific node")


# ============================================================================
# CORE TIMELINE EVENT TYPES
# ============================================================================


class StageStartedEvent(TimelineEventBase):
    """
    Emitted when a stage begins.
    
    Emission Criteria:
    - Triggered when stage_progress event arrives with iteration = 0
    - OR when first substage_event arrives for a new stage
    - Emitted once per stage (5 times per run)
    
    Frequency: 5 per run (one per stage)
    """

    type: Literal["stage_started"] = "stage_started"

    headline: str = Field(..., description="Short headline")
    stage_name: str = Field(..., description="Human-readable stage name")
    goal: Optional[str] = Field(None, description="What we're trying to achieve")


class NodeResultEvent(TimelineEventBase):
    """
    Emitted when a node completes execution.
    
    Emission Criteria:
    - Triggered when substage_event arrives with node completion
    - Includes metrics from corresponding stage_progress event
    - Emitted for each node that completes (success or failure)
    
    Frequency: 10-50 per stage (varies by stage complexity)
    """

    type: Literal["node_result"] = "node_result"

    headline: str = Field(..., description="Short headline")
    outcome: Literal["success", "failure", "partial"] = Field(
        ..., description="Execution outcome"
    )
    summary: Optional[str] = Field(None, description="Brief description of what occurred")

    metrics: Optional[MetricCollection] = Field(None, description="Interpreted metrics")

    error_type: Optional[str] = Field(None, description="Error type if failed")
    error_summary: Optional[str] = Field(None, description="Error explanation if failed")

    exec_time: Optional[float] = Field(None, description="Execution time in seconds")


class StageCompletedEvent(TimelineEventBase):
    """
    Emitted when a stage completes.
    
    Emission Criteria:
    - Triggered when substage_completed event arrives
    - Enriched with data from substage_summary event (already LLM-generated)
    - Emitted once per stage completion
    
    Frequency: 5 per run (one per stage)
    """

    type: Literal["stage_completed"] = "stage_completed"

    headline: str = Field(..., description="Short headline")
    summary: Optional[str] = Field(
        None, description="What was accomplished (from substage_summary)"
    )

    best_node_id: Optional[str] = Field(None, description="ID of best node from this stage")
    best_metrics: Optional[MetricCollection] = Field(None, description="Best metrics achieved")

    total_attempts: int = Field(0, description="Total nodes explored")
    successful_attempts: int = Field(0, description="Nodes that completed successfully")
    failed_attempts: int = Field(0, description="Nodes that failed")

    confidence: Optional[Literal["high", "medium", "low"]] = Field(
        None, description="Confidence in results (from substage_summary)"
    )


class ProgressUpdateEvent(TimelineEventBase):
    """
    Emitted periodically to show current focus.
    
    Emission Criteria:
    - Triggered by stage_progress events (every iteration)
    - Shows current iteration, focus, and progress metrics
    - Throttled to avoid overwhelming the timeline
    
    Frequency: ~10 per stage (one per iteration)
    """

    type: Literal["progress_update"] = "progress_update"

    headline: str = Field(..., description="Short headline")
    current_focus: Optional[str] = Field(None, description="What's happening right now")

    iteration: int = Field(..., description="Current iteration within the stage (1-based index)")
    max_iterations: int = Field(..., description="Total iterations planned")
    
    current_best: Optional[MetricCollection] = Field(
        None, description="Current best metrics if available"
    )


class PaperGenerationStepEvent(TimelineEventBase):
    """
    Emitted during Stage 5 (paper generation).
    
    Emission Criteria:
    - Triggered by paper_generation_progress events
    - Shows current step and progress within paper generation
    - Emitted for each major paper generation step
    
    Frequency: 4-6 per paper generation stage
    """

    type: Literal["paper_generation_step"] = "paper_generation_step"

    headline: str = Field(..., description="Short headline")
    step: Literal["plot_aggregation", "citation_gathering", "paper_writeup", "paper_review"] = (
        Field(..., description="Current step")
    )
    substep: Optional[str] = Field(None, description="Substep if applicable")
    description: Optional[str] = Field(None, description="What's happening in this step")
    progress: float = Field(..., description="Overall progress (0.0-1.0)")
    step_progress: float = Field(..., description="Progress within this step (0.0-1.0)")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Step-specific details (figures selected, citations found, etc.)"
    )


class NodeExecutionStartedEvent(TimelineEventBase):
    """
    Emitted when a node starts executing code.
    
    Emission Criteria:
    - Triggered by running_code events from research pipeline
    - Tracks individual node execution lifecycle
    - Helps show concurrent node execution
    
    Frequency: 10-50 per stage (one per node execution)
    """

    type: Literal["node_execution_started"] = "node_execution_started"

    headline: str = Field(..., description="Short headline")
    execution_id: str = Field(..., description="Unique execution ID")
    run_type: str = Field(default="main_execution", description="Type of run")
    code_preview: Optional[str] = Field(None, description="Preview of code being executed")


class NodeExecutionCompletedEvent(TimelineEventBase):
    """
    Emitted when a node completes execution.
    
    Emission Criteria:
    - Triggered by run_completed events from research pipeline
    - Tracks node completion with timing and status
    - Pairs with NodeExecutionStartedEvent
    
    Frequency: 10-50 per stage (one per node execution)
    """

    type: Literal["node_execution_completed"] = "node_execution_completed"

    headline: str = Field(..., description="Short headline")
    execution_id: str = Field(..., description="Unique execution ID")
    status: Literal["success", "failed"] = Field(..., description="Execution status")
    exec_time: float = Field(..., description="Execution time in seconds")
    run_type: str = Field(default="main_execution", description="Type of run")


# ============================================================================
# TIMELINE EVENT UNION
# ============================================================================

TimelineEvent = Annotated[
    Union[
        StageStartedEvent,
        NodeResultEvent,
        StageCompletedEvent,
        ProgressUpdateEvent,
        PaperGenerationStepEvent,
        NodeExecutionStartedEvent,
        NodeExecutionCompletedEvent,
    ],
    Field(discriminator="type"),
]
