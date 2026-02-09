"""
Narrator Event Types

These types define the events that can be processed by the narrator.
They are defined here (separate from schemas.py) to avoid circular imports.

The narrator pipeline uses these types for type-safe event dispatch.
"""

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel

from app.models.research_pipeline import ExecutionType, RunType
from app.models.timeline_events import ExperimentalStageId, StageId

# ============================================================================
# Internal Event Data Models (used by narrator, not exposed via API)
# ============================================================================


class RunStartedEventData(BaseModel):
    """Internal event data for run_started events (used by narrator)."""

    started_running_at: str
    gpu_type: str
    cost_per_hour_cents: Optional[int]


class RunFinishedEventData(BaseModel):
    """Internal event data for run_finished events (used by narrator)."""

    success: bool
    status: Literal["completed", "failed", "cancelled"]
    message: Optional[str]
    reason: Literal[
        "pipeline_completed",
        "pipeline_error",
        "heartbeat_timeout",
        "deadline_exceeded",
        "user_cancelled",
        "container_died",
        "pipeline_event_finish",
    ]


# ============================================================================
# Webhook Event Schemas (source of truth)
# These are imported by schemas.py for use in API validation
# ============================================================================


class StageProgressEvent(BaseModel):
    stage: StageId
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str]
    is_seed_node: bool
    is_seed_agg_node: bool


class StageCompletedEvent(BaseModel):
    stage: StageId
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]  # Contains goals, feedback, metrics, etc.


class StageSummaryEvent(BaseModel):
    """Event containing the LLM-generated transition summary for a stage."""

    stage: ExperimentalStageId  # Only experimental stages (1-4) produce summaries
    summary: str  # The transition summary text


class PaperGenerationProgressEvent(BaseModel):
    step: Literal["plot_aggregation", "citation_gathering", "paper_writeup", "paper_review"]
    substep: Optional[str] = None
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]] = None


class RunningCodeEventPayload(BaseModel):
    execution_id: str
    stage: StageId
    code: str
    started_at: str
    run_type: RunType
    execution_type: ExecutionType
    is_seed_node: bool
    is_seed_agg_node: bool
    node_index: int  # 1-based node index for display


class RunCompletedEventPayload(BaseModel):
    execution_id: str
    stage: StageId
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: str
    run_type: RunType
    execution_type: ExecutionType
    is_seed_node: bool
    is_seed_agg_node: bool
    node_index: int  # 1-based node index for display


# ============================================================================
# Narrator Event Union Type
# ============================================================================

# Union of all event types that can be processed by the narrator.
# This provides type safety throughout the event processing pipeline.
NarratorEvent = Union[
    StageProgressEvent,
    StageCompletedEvent,
    StageSummaryEvent,
    PaperGenerationProgressEvent,
    RunningCodeEventPayload,
    RunCompletedEventPayload,
    RunStartedEventData,
    RunFinishedEventData,
]
