"""
ResearchRunState Schema for Narrator Architecture

Single source of truth for the frontend.
Pattern: Simple, flat structure. Everything easily accessible.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .timeline_events import StageId, TimelineEvent


class ActiveNode(BaseModel):
    """Represents a node currently executing in the research pipeline."""

    execution_id: str = Field(..., description="Unique execution ID")
    stage: StageId = Field(..., description="Stage identifier")
    status: Literal["running", "completed", "failed"] = Field(
        default="running", description="Current execution status"
    )
    started_at: datetime = Field(..., description="When execution started")
    completed_at: Optional[datetime] = Field(default=None, description="When execution completed")
    exec_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    run_type: str = Field(default="main_execution", description="Type of run")


class StageGoal(BaseModel):
    """Goal and metadata for a pipeline stage."""

    stage: StageId = Field(..., description="Stage identifier")
    title: str = Field(..., description="Display title")
    goal: Optional[str] = Field(default=None, description="What we're trying to achieve")
    status: Literal["pending", "in_progress", "completed", "skipped"] = Field(
        default="pending", description="Current status"
    )
    progress: Optional[float] = Field(default=None, description="Progress 0.0-1.0")


ResearchRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class ResearchRunState(BaseModel):
    """Complete state of a research run. Single source of truth for frontend."""

    run_id: str = Field(..., description="Unique run identifier")
    status: ResearchRunStatus
    conversation_id: int
    idea_title: Optional[str] = None
    stages: List[StageGoal] = Field(default_factory=list)
    current_stage: Optional[StageId] = None
    timeline: List[TimelineEvent] = Field(default_factory=list)
    current_focus: Optional[str] = None
    active_nodes: List[ActiveNode] = Field(default_factory=list)
    overall_progress: float = 0.0
    started_running_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    gpu_type: str
    estimated_cost_cents: Optional[int] = None
    actual_cost_cents: Optional[int] = None
    cost_per_hour_cents: Optional[int] = None
    error_message: Optional[str] = None
    version: int = 1


class StateUpdateResult(BaseModel):
    """Partial state changes from applying a timeline event."""

    changes: Dict[str, Any] = Field(default_factory=dict)
    should_update: bool = True


def create_initial_state(
    *,
    run_id: str,
    conversation_id: int,
    gpu_type: str,
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending",
    idea_title: Optional[str] = None,
) -> ResearchRunState:
    """Create initial state for a new research run."""
    standard_stages = [
        StageGoal(
            stage=StageId.initial_implementation,
            title="Initial Implementation",
            status="pending",
        ),
        StageGoal(
            stage=StageId.baseline_tuning,
            title="Baseline Tuning",
            status="pending",
        ),
        StageGoal(
            stage=StageId.creative_research,
            title="Creative Research",
            status="pending",
        ),
        StageGoal(
            stage=StageId.ablation_studies,
            title="Ablation Studies",
            status="pending",
        ),
        StageGoal(
            stage=StageId.paper_generation,
            title="Paper Generation",
            status="pending",
        ),
    ]

    return ResearchRunState(
        run_id=run_id,
        status=status,
        conversation_id=conversation_id,
        idea_title=idea_title,
        stages=standard_stages,
        gpu_type=gpu_type,
    )
