"""
State Reducer for Narrator Architecture

Pure functions that compute ResearchRunState from timeline events.
Pattern: Dispatcher (event_type → handler_fn), handlers return partial changes.
"""

from typing import Any, Callable, Dict, cast

from app.models.narrator_state import ActiveNode, ResearchRunState, StateUpdateResult
from app.models.timeline_events import (
    NodeExecutionCompletedEvent,
    NodeExecutionStartedEvent,
    NodeResultEvent,
    PaperGenerationStepEvent,
    ProgressUpdateEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StageCompletedEvent,
    StageStartedEvent,
    TimelineEvent,
)


def handle_stage_started(state: ResearchRunState, event: StageStartedEvent) -> StateUpdateResult:
    """Handle stage_started event."""
    changes: Dict[str, Any] = {
        "current_stage": event.stage,
        "current_focus": event.headline,
        "timeline": state.timeline + [event],
    }

    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.status = "in_progress"
            break
    changes["stages"] = updated_stages

    return StateUpdateResult(changes=changes)


def handle_node_result(state: ResearchRunState, event: NodeResultEvent) -> StateUpdateResult:
    """Handle node_result event."""
    changes: Dict[str, Any] = {
        "timeline": state.timeline + [event],
    }

    return StateUpdateResult(changes=changes)


def handle_stage_completed(
    state: ResearchRunState, event: StageCompletedEvent
) -> StateUpdateResult:
    """Handle stage_completed event."""
    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.status = "completed"
            stage.progress = 1.0
            break

    completed_count = sum(1 for s in updated_stages if s.status == "completed")
    total_count = len(updated_stages)

    changes: Dict[str, Any] = {
        "stages": updated_stages,
        "timeline": state.timeline + [event],
        "overall_progress": completed_count / total_count if total_count > 0 else 0.0,
        "current_focus": None,
    }

    return StateUpdateResult(changes=changes)


def handle_progress_update(
    state: ResearchRunState, event: ProgressUpdateEvent
) -> StateUpdateResult:
    """Handle progress_update event."""
    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.progress = (
                event.iteration / event.max_iterations if event.max_iterations > 0 else 0.0
            )
            break

    changes: Dict[str, Any] = {
        "stages": updated_stages,
        "timeline": state.timeline + [event],
    }

    if event.current_focus:
        changes["current_focus"] = event.current_focus

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
    }

    return StateUpdateResult(changes=changes)


def handle_node_execution_completed(
    state: ResearchRunState, event: NodeExecutionCompletedEvent
) -> StateUpdateResult:
    """Handle node_execution_completed event - update and remove node from active_nodes."""
    updated_active_nodes = []
    for node in state.active_nodes:
        if node.execution_id == event.execution_id and node.run_type == event.run_type:
            # remove completed nodes from active list (must match both execution_id AND run_type)
            continue
        updated_active_nodes.append(node)

    changes: Dict[str, Any] = {
        "active_nodes": updated_active_nodes,
        "timeline": state.timeline + [event],
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
    }

    # update stage progress
    updated_stages = [s.model_copy() for s in state.stages]
    for stage in updated_stages:
        if stage.stage == event.stage:
            stage.progress = event.progress
            break
    changes["stages"] = updated_stages

    return StateUpdateResult(changes=changes)


def handle_run_started(state: ResearchRunState, event: RunStartedEvent) -> StateUpdateResult:
    """
    Handle run_started event - updates state with started_running_at and cost info.

    Updates:
    - started_running_at: Set to event timestamp
    - gpu_type: Set GPU type
    - cost_per_hour_cents: Set cost per hour
    - status: Set to "running"
    - timeline: Append event
    """
    changes: Dict[str, Any] = {
        "timeline": state.timeline + [event],
        "status": "running",
        "started_running_at": event.timestamp,
    }

    # Set GPU type and cost
    changes["gpu_type"] = event.gpu_type

    if event.cost_per_hour_cents:
        changes["cost_per_hour_cents"] = event.cost_per_hour_cents

    return StateUpdateResult(changes=changes)


def handle_run_finished(state: ResearchRunState, event: RunFinishedEvent) -> StateUpdateResult:
    """
    Handle run_finished event - marks the run as complete/failed.

    Updates:
    - status: Set to "completed", "failed", or "cancelled"
    - completed_at: Set to event timestamp
    - error_message: Set if run failed
    - timeline: Append event
    """
    changes: Dict[str, Any] = {
        "timeline": state.timeline + [event],
        "status": event.status,
        "completed_at": event.timestamp,
    }

    # Set error message if failed
    if not event.success and event.message:
        changes["error_message"] = event.message

    return StateUpdateResult(changes=changes)


# ============================================================================
# DISPATCH TABLE
# ============================================================================

# Type alias for the handler function signature
# We use the base TimelineEvent type here to satisfy mypy's contravariance rules
HandlerFn = Callable[[ResearchRunState, TimelineEvent], StateUpdateResult]

# The actual dispatch table
# We use a controlled cast here to bridge the gap between:
# - What we know: each handler receives the correct specific event type
# - What mypy needs: a consistent signature for all handlers in the dict
#
# This is a standard pattern in typed Python for event dispatch systems.
# The invariant we're asserting: "The event_type key guarantees the correct
# event subtype will be passed to each handler at runtime."
HANDLERS: Dict[str, HandlerFn] = cast(
    Dict[str, HandlerFn],
    {
        "run_started": handle_run_started,
        "stage_started": handle_stage_started,
        "node_result": handle_node_result,
        "stage_completed": handle_stage_completed,
        "progress_update": handle_progress_update,
        "paper_generation_step": handle_paper_generation_step,
        "node_execution_started": handle_node_execution_started,
        "node_execution_completed": handle_node_execution_completed,
        "run_finished": handle_run_finished,
    },
)


# ============================================================================
# REDUCER FUNCTIONS
# ============================================================================


def reduce(state: ResearchRunState, event: TimelineEvent) -> StateUpdateResult:
    """
    Pure reducer: (state, event) → state changes. Deterministic.

    This is the main entry point for state reduction. It dispatches to the
    appropriate handler based on the event type.

    The type safety here is guaranteed by:
    1. The discriminated union (TimelineEvent with type field)
    2. The HANDLERS dict mapping event.type → correct handler
    3. Runtime dispatch ensures the right handler gets the right event
    """
    handler = HANDLERS.get(event.type)
    if handler is None:
        return StateUpdateResult(changes={}, should_update=False)
    return handler(state, event)


def apply_changes(state: ResearchRunState, changes: Dict[str, Any]) -> ResearchRunState:
    """Apply partial changes to state, returning new state."""
    return state.model_copy(update=changes)


def replay_events(initial_state: ResearchRunState, events: list[TimelineEvent]) -> ResearchRunState:
    """Replay timeline events to reconstruct state."""
    state = initial_state
    for event in events:
        result = reduce(state, event)
        if result.should_update:
            state = apply_changes(state, result.changes)
    return state
