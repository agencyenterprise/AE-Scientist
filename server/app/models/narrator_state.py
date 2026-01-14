"""
ResearchRunState Schema for Narrator Architecture

Single source of truth for the frontend.
Pattern: Simple, flat structure. Everything easily accessible.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .timeline_events import MetricCollection, TimelineEvent


class ActiveNode(BaseModel):
    """Represents a node currently executing in the research pipeline."""

    execution_id: str = Field(..., description="Unique execution ID")
    stage: str = Field(..., description="Stage identifier")
    status: Literal["running", "completed", "failed"] = Field(
        default="running", description="Current execution status"
    )
    started_at: datetime = Field(..., description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    exec_time: Optional[float] = Field(None, description="Execution time in seconds")
    run_type: str = Field(default="main_execution", description="Type of run")


class StageGoal(BaseModel):
    """Goal and metadata for a pipeline stage."""

    stage: str = Field(..., description="Stage identifier")
    title: str = Field(..., description="Display title")
    goal: Optional[str] = Field(None, description="What we're trying to achieve")
    approach: Optional[str] = Field(None, description="How we're approaching it")
    success_criteria: Optional[str] = Field(None, description="How we know we're done")
    status: Literal["pending", "in_progress", "completed", "skipped"] = Field(
        default="pending", description="Current status"
    )
    started_at: Optional[datetime] = Field(None, description="When stage started")
    completed_at: Optional[datetime] = Field(None, description="When stage completed")
    current_iteration: Optional[int] = Field(None, description="Current iteration")
    max_iterations: Optional[int] = Field(None, description="Maximum iterations")
    progress: Optional[float] = Field(None, description="Progress 0.0-1.0")
    total_nodes: int = Field(default=0, description="Total nodes in this stage")
    buggy_nodes: int = Field(default=0, description="Number of buggy nodes")
    good_nodes: int = Field(default=0, description="Number of good nodes")


class ResearchRunState(BaseModel):
    """Complete state of a research run. Single source of truth for frontend."""

    run_id: str = Field(..., description="Unique run identifier")
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    conversation_id: int
    overall_goal: Optional[str] = None
    hypothesis: Optional[str] = None
    stages: List[StageGoal] = Field(default_factory=list)
    current_stage: Optional[str] = None
    current_stage_goal: Optional[StageGoal] = None
    timeline: List[TimelineEvent] = Field(default_factory=list)
    current_focus: Optional[str] = None
    active_nodes: List[ActiveNode] = Field(default_factory=list)
    overall_progress: float = 0.0
    current_stage_progress: float = 0.0
    best_node_id: Optional[str] = None
    best_metrics: Optional[MetricCollection] = None
    best_node_reasoning: Optional[str] = None
    artifact_ids: List[int] = Field(default_factory=list)
    # stage_id -> tree_viz_data
    tree_viz: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    started_running_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    gpu_type: Optional[str] = None
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
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending",
    overall_goal: Optional[str] = None,
    hypothesis: Optional[str] = None,
) -> ResearchRunState:
    """Create initial state for a new research run."""
    now = datetime.now(timezone.utc)
    
    standard_stages = [
        StageGoal(stage="1_initial_implementation", title="Initial Implementation", status="pending"),
        StageGoal(stage="2_baseline_tuning", title="Baseline Tuning", status="pending"),
        StageGoal(stage="3_creative_research", title="Creative Research", status="pending"),
        StageGoal(stage="4_ablation_studies", title="Ablation Studies", status="pending"),
        StageGoal(stage="5_paper_generation", title="Paper Generation", status="pending"),
    ]
    
    return ResearchRunState(
        run_id=run_id,
        status=status,
        conversation_id=conversation_id,
        overall_goal=overall_goal,
        hypothesis=hypothesis,
        stages=standard_stages,
        created_at=now,
        updated_at=now,
    )

