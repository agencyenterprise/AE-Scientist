"""Common predicates for narrator state queries."""

from typing import Optional

from app.models.narrator_state import ResearchRunState, StageGoal
from app.models.timeline_events import StageId


def is_stage_started(state: ResearchRunState, stage: StageId) -> bool:
    """Check if a stage has started (status != 'pending')."""
    return any(s.stage == stage and s.status != "pending" for s in state.stages)


def is_stage_completed(state: ResearchRunState, stage: StageId) -> bool:
    """Check if a stage has completed (status == 'completed')."""
    return any(s.stage == stage and s.status == "completed" for s in state.stages)


def is_stage_in_progress(state: ResearchRunState, stage: StageId) -> bool:
    """Check if a stage is currently in progress (status == 'in_progress')."""
    return any(s.stage == stage and s.status == "in_progress" for s in state.stages)


def find_stage(state: ResearchRunState, stage: StageId) -> Optional[StageGoal]:
    """Find a stage object by identifier."""
    return next((s for s in state.stages if s.stage == stage), None)


def get_current_stage(state: ResearchRunState) -> Optional[StageGoal]:
    """Get the currently active stage (in_progress)."""
    return next((s for s in state.stages if s.status == "in_progress"), None)


def get_completed_stages(state: ResearchRunState) -> list[StageGoal]:
    """Get all completed stages."""
    return [s for s in state.stages if s.status == "completed"]
