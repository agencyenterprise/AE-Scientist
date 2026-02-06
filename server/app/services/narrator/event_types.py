"""
Narrator Event Types

These types define the events that can be processed by the narrator.
They are defined here (separate from schemas.py) to avoid circular imports.

The narrator pipeline uses these types for type-safe event dispatch.
"""

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel

from app.models.research_pipeline import ExecutionType, RunType

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
    stage: str
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str]
    is_seed_node: bool
    is_seed_agg_node: bool


class SubstageCompletedEvent(BaseModel):
    stage: str
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]


class SubstageSummaryEvent(BaseModel):
    stage: str
    summary: Dict[str, Any]


class PaperGenerationProgressEvent(BaseModel):
    step: Literal["plot_aggregation", "citation_gathering", "paper_writeup", "paper_review"]
    substep: Optional[str] = None
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]] = None


class RunningCodeEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    code: str
    started_at: str
    run_type: RunType
    execution_type: ExecutionType
    is_seed_node: bool
    is_seed_agg_node: bool
    node_index: int  # 1-based node index for display


class RunCompletedEventPayload(BaseModel):
    execution_id: str
    stage_name: str
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
    SubstageCompletedEvent,
    SubstageSummaryEvent,
    PaperGenerationProgressEvent,
    RunningCodeEventPayload,
    RunCompletedEventPayload,
    RunStartedEventData,
    RunFinishedEventData,
]
