"""
State Reducer for Narrator Architecture

Pure functions that compute ResearchRunState from timeline events.
Pattern: Dispatcher (event_type → handler_fn), handlers return partial changes.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict

from app.models.narrator_state import ActiveNode, ResearchRunState, StateUpdateResult
from app.models.timeline_events import (
    NodeExecutionCompletedEvent,
    NodeExecutionStartedEvent,
    NodeResultEvent,
    PaperGenerationStepEvent,
    ProgressUpdateEvent,
    StageCompletedEvent,
    StageStartedEvent,
    TimelineEvent,
)


def handle_stage_started(
    state: ResearchRunState, event: StageStartedEvent
) -> StateUpdateResult:
    """Handle stage_started event."""
    changes: Dict[str, Any] = {
        "current_stage": event.stage,
        "current_focus": f"Starting {event.stage_name}",
        "updated_at": datetime.now(timezone.utc),
        "timeline": state.timeline + [event],
    }
    
    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.status = "in_progress"
            stage.started_at = event.timestamp
            changes["current_stage_goal"] = stage
            break
    changes["stages"] = updated_stages
    
    return StateUpdateResult(changes=changes)


def handle_node_result(state: ResearchRunState, event: NodeResultEvent) -> StateUpdateResult:
    """Handle node_result event."""
    changes: Dict[str, Any] = {
        "timeline": state.timeline + [event],
        "updated_at": datetime.now(timezone.utc),
    }
    
    if event.outcome == "success" and event.metrics and state.best_metrics is None:
        changes["best_metrics"] = event.metrics
        changes["best_node_id"] = event.node_id
    
    return StateUpdateResult(changes=changes)


def handle_stage_completed(
    state: ResearchRunState, event: StageCompletedEvent
) -> StateUpdateResult:
    """Handle stage_completed event."""
    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.status = "completed"
            stage.completed_at = event.timestamp
            stage.progress = 1.0
            break
    
    completed_count = sum(1 for s in updated_stages if s.status == "completed")
    total_count = len(updated_stages)
    
    changes: Dict[str, Any] = {
        "stages": updated_stages,
        "timeline": state.timeline + [event],
        "overall_progress": completed_count / total_count if total_count > 0 else 0.0,
        "current_focus": None,
        "updated_at": datetime.now(timezone.utc),
    }
    
    if event.best_metrics:
        changes["best_metrics"] = event.best_metrics
        changes["best_node_id"] = event.best_node_id
    
    return StateUpdateResult(changes=changes)


def handle_progress_update(
    state: ResearchRunState, event: ProgressUpdateEvent
) -> StateUpdateResult:
    """Handle progress_update event."""
    updated_stages = [s.model_copy() for s in state.stages]
    stage_progress = 0.0
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.current_iteration = event.iteration
            stage.max_iterations = event.max_iterations
            stage.progress = event.iteration / event.max_iterations if event.max_iterations > 0 else 0.0
            stage_progress = stage.progress
            break
    
    changes: Dict[str, Any] = {
        "stages": updated_stages,
        "timeline": state.timeline + [event],
        "current_stage_progress": stage_progress,
        "updated_at": datetime.now(timezone.utc),
    }
    
    if event.current_focus:
        changes["current_focus"] = event.current_focus
    if event.current_best:
        changes["best_metrics"] = event.current_best
    
    return StateUpdateResult(changes=changes)


def handle_node_execution_started(
    state: ResearchRunState, event: NodeExecutionStartedEvent
) -> StateUpdateResult:
    """Handle node_execution_started event - add node to active_nodes list."""
    new_active_node = ActiveNode(
        execution_id=event.execution_id,
        stage=event.stage,
        status="running",
        started_at=event.timestamp,
        run_type=event.run_type,
    )
    
    updated_active_nodes = state.active_nodes + [new_active_node]
    
    changes: Dict[str, Any] = {
        "active_nodes": updated_active_nodes,
        "timeline": state.timeline + [event],
        "updated_at": datetime.now(timezone.utc),
    }
    
    return StateUpdateResult(changes=changes)


def handle_node_execution_completed(
    state: ResearchRunState, event: NodeExecutionCompletedEvent
) -> StateUpdateResult:
    """Handle node_execution_completed event - update and remove node from active_nodes."""
    updated_active_nodes = []
    for node in state.active_nodes:
        if node.execution_id == event.execution_id:
            # remove completed nodes from active list
            continue
        updated_active_nodes.append(node)
    
    changes: Dict[str, Any] = {
        "active_nodes": updated_active_nodes,
        "timeline": state.timeline + [event],
        "updated_at": datetime.now(timezone.utc),
    }
    
    return StateUpdateResult(changes=changes)


def handle_paper_generation_step(
    state: ResearchRunState, event: PaperGenerationStepEvent
) -> StateUpdateResult:
    """Handle paper_generation_step event."""
    focus_text = f"Paper generation: {event.step}"
    if event.substep:
        focus_text += f" - {event.substep}"
    
    changes: Dict[str, Any] = {
        "current_focus": focus_text,
        "overall_progress": 0.8 + (0.2 * event.progress),
        "timeline": state.timeline + [event],
        "updated_at": datetime.now(timezone.utc),
    }
    
    return StateUpdateResult(changes=changes)


HandlerFn = Callable[[ResearchRunState, TimelineEvent], StateUpdateResult]

HANDLERS: Dict[str, HandlerFn] = {
    "stage_started": handle_stage_started,
    "node_result": handle_node_result,
    "stage_completed": handle_stage_completed,
    "progress_update": handle_progress_update,
    "paper_generation_step": handle_paper_generation_step,
    "node_execution_started": handle_node_execution_started,
    "node_execution_completed": handle_node_execution_completed,
}


def reduce(state: ResearchRunState, event: TimelineEvent) -> StateUpdateResult:
    """Pure reducer: (state, event) → state changes. Deterministic."""
    handler = HANDLERS.get(event.type)
    if handler is None:
        return StateUpdateResult(changes={}, should_update=False)
    return handler(state, event)


def apply_changes(state: ResearchRunState, changes: Dict[str, Any]) -> ResearchRunState:
    """Apply partial changes to state, returning new state."""
    return state.model_copy(update=changes)


def replay_events(
    initial_state: ResearchRunState, events: list[TimelineEvent]
) -> ResearchRunState:
    """Replay timeline events to reconstruct state."""
    state = initial_state
    for event in events:
        result = reduce(state, event)
        if result.should_update:
            state = apply_changes(state, result.changes)
    return state
