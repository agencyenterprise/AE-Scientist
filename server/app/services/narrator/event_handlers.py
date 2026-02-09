"""
Event Handlers for Narrator Architecture

Transform raw execution events into timeline events.
These are the translation layer between technical execution and narrative presentation.

Pattern:
- Extract, don't generate (use existing data)
- Simple transformations
- No LLM calls (for now)
- Return timeline events or None
- Type-safe: handlers receive typed Pydantic models, not dicts
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.models.narrator_state import ResearchRunState
from app.models.timeline_events import (
    MetricCollection,
    MetricInterpretation,
    NodeExecutionCompletedEvent,
    NodeExecutionStartedEvent,
    PaperGenerationStepEvent,
    ProgressUpdateEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StageCompletedEvent,
    StageId,
    StageStartedEvent,
    StageTransitionEvent,
    TimelineEvent,
)
from app.services.narrator.event_types import (
    NarratorEvent,
    PaperGenerationProgressEvent,
    RunCompletedEventPayload,
    RunFinishedEventData,
    RunningCodeEventPayload,
    RunStartedEventData,
)
from app.services.narrator.event_types import StageCompletedEvent as StageCompletedEventPayload
from app.services.narrator.event_types import StageProgressEvent, StageSummaryEvent
from app.services.narrator.predicates import is_stage_started

# ============================================================================
# STAGE NAME MAPPING
# ============================================================================

STAGE_NAMES = {
    "1_initial_implementation": "Initial Implementation",
    "2_baseline_tuning": "Baseline Tuning",
    "3_creative_research": "Creative Research",
    "4_ablation_studies": "Ablation Studies",
    "5_paper_generation": "Paper Generation",
}


# ============================================================================
# EVENT HANDLERS (Typed Event → Timeline Event)
# ============================================================================


def handle_stage_progress_event(
    event: StageProgressEvent, state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform stage_progress event into timeline event.

    Creates:
    - StageStartedEvent (if iteration == 1 AND stage not already started), followed by
    - ProgressUpdateEvent (always)
    """
    now = datetime.now(timezone.utc)
    events: List[TimelineEvent] = []
    offset_ms = 0

    # If iteration == 1 AND stage not already started, emit stage start FIRST
    if event.iteration == 1 and state and not is_stage_started(state, event.stage):
        stage_display_name = STAGE_NAMES.get(event.stage, event.stage) or event.stage
        events.append(
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=now + timedelta(milliseconds=offset_ms),
                stage=event.stage,
                node_id=None,
                headline=f"Starting {stage_display_name}",
                goal=None,
            )
        )
        offset_ms += 10

    # Always emit the progress update (so frontend gets iteration count)
    stage_name = STAGE_NAMES.get(event.stage, event.stage)

    # Create different focus text based on node type
    if event.is_seed_agg_node:
        current_focus = f"{stage_name}: Aggregating seed results"
        headline = f"Aggregation {event.iteration}/{event.max_iterations}"
    elif event.is_seed_node:
        current_focus = f"{stage_name}: Seed evaluation {event.iteration}/{event.max_iterations}"
        headline = f"Seed {event.iteration}/{event.max_iterations}"
    else:
        current_focus = f"{stage_name}: Iteration {event.iteration}/{event.max_iterations}"
        headline = f"Iteration {event.iteration}/{event.max_iterations}"

    # Create metric interpretation if we have best_metric
    current_best = None
    if event.best_metric:
        try:
            metric_value = float(event.best_metric)
            current_best = MetricCollection(
                primary=MetricInterpretation(
                    name="best_metric",
                    value=metric_value,
                    formatted=f"{metric_value:.4f}",
                    interpretation="Current best",
                    context=f"Stage {event.stage}",
                    comparison=None,
                )
            )
        except (ValueError, TypeError):
            pass

    events.append(
        ProgressUpdateEvent(
            id=str(uuid.uuid4()),
            timestamp=now + timedelta(milliseconds=offset_ms),
            stage=event.stage,
            node_id=None,
            headline=headline,
            current_focus=current_focus,
            iteration=event.iteration,
            max_iterations=event.max_iterations,
            current_best=current_best,
            is_seed_node=event.is_seed_node,
            is_seed_agg_node=event.is_seed_agg_node,
        )
    )

    return events


def handle_stage_completed_event(
    event: StageCompletedEventPayload, _state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """Transform stage_completed event into StageCompletedEvent."""
    now = datetime.now(timezone.utc)
    stage_name = STAGE_NAMES.get(event.stage, event.stage)

    # Extract best metric if available
    summary = event.summary
    best_metrics = None
    best_metric_value = summary.get("best_metric")
    if best_metric_value:
        try:
            metric_value = float(best_metric_value)
            best_metrics = MetricCollection(
                primary=MetricInterpretation(
                    name="best_metric",
                    value=metric_value,
                    formatted=f"{metric_value:.4f}",
                    interpretation="Best result for this stage",
                    context=f"Stage {event.stage}",
                    comparison=None,
                )
            )
        except (ValueError, TypeError):
            pass

    return [
        StageCompletedEvent(
            id=str(uuid.uuid4()),
            timestamp=now,
            stage=event.stage,
            node_id=None,
            headline=f"{stage_name} Complete",
            best_metrics=best_metrics,
        )
    ]


def handle_stage_summary_event(
    event: StageSummaryEvent, _state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform stage_summary event into StageTransitionEvent.

    The stage_summary event contains an LLM-generated transition summary
    that describes what was accomplished and what comes next.
    """
    now = datetime.now(timezone.utc)

    # summary is now just the transition summary string
    transition_summary = event.summary
    if not transition_summary:
        # No transition summary available, don't create event
        return []

    # Get stage information for headline
    stage = event.stage
    stage_name = STAGE_NAMES.get(stage, stage)

    return [
        StageTransitionEvent(
            id=str(uuid.uuid4()),
            timestamp=now,
            stage=stage,
            node_id=None,
            headline=f"Completed {stage_name}",
            transition_summary=transition_summary,
        )
    ]


def handle_running_code_event(
    event: RunningCodeEventPayload, state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform running_code event into NodeExecutionStartedEvent.

    Note: This is the first signal that a stage has started (code is executing).
    If the stage hasn't started yet (checked via state), we emit stage_started first.
    """
    # Parse timestamp
    try:
        started_at = datetime.fromisoformat(event.started_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        started_at = datetime.now(timezone.utc)

    # Store the full code - frontend handles display/scrolling
    code_preview = event.code

    events: List[TimelineEvent] = []
    offset_ms = 0

    # If stage hasn't started, emit stage_started event first
    if state and not is_stage_started(state, event.stage):
        stage_display_name = STAGE_NAMES.get(event.stage, event.stage) or event.stage
        events.append(
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=started_at + timedelta(milliseconds=offset_ms),
                stage=event.stage,
                node_id=None,
                headline=f"Starting {stage_display_name}",
                goal=None,
            )
        )
        offset_ms += 10

    # Then emit node execution started event
    events.append(
        NodeExecutionStartedEvent(
            id=str(uuid.uuid4()),
            timestamp=started_at + timedelta(milliseconds=offset_ms),
            stage=event.stage,
            node_id=event.execution_id,
            headline=f"Node {event.node_index} started",
            execution_id=event.execution_id,
            run_type=event.run_type.value,
            execution_type=event.execution_type.value,
            code_preview=code_preview,
            is_seed_node=event.is_seed_node,
            is_seed_agg_node=event.is_seed_agg_node,
            node_index=event.node_index,
        )
    )

    return events


def handle_run_completed_event(
    event: RunCompletedEventPayload, _state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """Transform run_completed event into NodeExecutionCompletedEvent."""
    # Parse timestamp
    try:
        completed_at = datetime.fromisoformat(event.completed_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        completed_at = datetime.now(timezone.utc)

    headline = f"Node {event.node_index} {event.status} ({event.exec_time:.1f}s)"

    return [
        NodeExecutionCompletedEvent(
            id=str(uuid.uuid4()),
            timestamp=completed_at,
            stage=event.stage,
            node_id=event.execution_id,
            headline=headline,
            execution_id=event.execution_id,
            status=event.status,
            exec_time=event.exec_time,
            run_type=event.run_type.value,
            execution_type=event.execution_type.value,
            is_seed_node=event.is_seed_node,
            is_seed_agg_node=event.is_seed_agg_node,
            node_index=event.node_index,
        )
    ]


def handle_paper_generation_progress_event(
    event: PaperGenerationProgressEvent, state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform paper_generation_progress event into PaperGenerationStepEvent.

    When progress reaches 1.0, also emits a StageCompletedEvent for paper generation.
    If this is the first paper generation event and the stage hasn't started, also emits StageStartedEvent.
    """
    now = datetime.now(timezone.utc)
    offset_ms = 0

    events: List[TimelineEvent] = []

    # If stage not started, emit StageStartedEvent first
    if state and not is_stage_started(state, StageId.paper_generation):
        events.append(
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=now + timedelta(milliseconds=offset_ms),
                stage=StageId.paper_generation,
                node_id=None,
                headline="Starting Paper Generation",
                goal=None,
            )
        )
        offset_ms += 10

    # Create headline
    headline = f"Paper: {event.step.replace('_', ' ').title()}"
    if event.substep:
        headline += f" - {event.substep}"

    # Add the paper generation step event
    events.append(
        PaperGenerationStepEvent(
            id=str(uuid.uuid4()),
            timestamp=now + timedelta(milliseconds=offset_ms),
            stage=StageId.paper_generation,
            node_id=None,
            headline=headline,
            step=event.step,
            substep=event.substep,
            description=None,
            progress=event.progress,
            step_progress=event.step_progress,
            details=event.details,
        )
    )
    offset_ms += 10

    # If progress is 1.0, paper generation is complete
    if event.progress >= 1.0:
        events.append(
            StageCompletedEvent(
                id=str(uuid.uuid4()),
                timestamp=now + timedelta(milliseconds=offset_ms),
                stage=StageId.paper_generation,
                node_id=None,
                headline="Paper Generation Complete",
                best_metrics=None,
            )
        )

    return events


def handle_run_started_event(
    event: RunStartedEventData, _state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform run_started event into timeline event.

    This marks the transition from "pending" to "running" when the container is ready.
    """
    # Parse timestamp
    try:
        timestamp = datetime.fromisoformat(event.started_running_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        timestamp = datetime.now(timezone.utc)

    # Generate headline
    headline = f"Research Run Started on {event.gpu_type}"

    return [
        RunStartedEvent(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            stage=StageId.initial_implementation,  # Default to first stage
            node_id=None,
            headline=headline,
            gpu_type=event.gpu_type,
            cost_per_hour_cents=event.cost_per_hour_cents,
        )
    ]


def handle_run_finished_event(
    event: RunFinishedEventData, state: Optional[ResearchRunState]
) -> List[TimelineEvent]:
    """
    Transform run_finished event into timeline event.

    This marks the entire research run as complete and triggers queue cleanup.
    """
    # Determine reason (fallback if not provided)
    reason = (
        event.reason
        if event.reason
        else ("pipeline_completed" if event.success else "pipeline_error")
    )

    # Generate headline based on status
    if event.success:
        headline = "Research Run Completed Successfully"
    elif reason == "heartbeat_timeout":
        headline = "Research Run Failed - Container Timeout"
    elif reason == "deadline_exceeded":
        headline = "Research Run Failed - Time Limit Exceeded"
    elif reason == "user_cancelled":
        headline = "Research Run Cancelled by User"
    elif reason == "container_died":
        headline = "Research Run Failed - Container Died"
    else:
        headline = "Research Run Failed"

    # Extract summary info from state if available
    stages_completed = 0
    total_nodes_executed = 0
    total_duration_seconds = None
    best_result = None
    summary = None

    if state:
        stages_completed = sum(1 for stage in state.stages if stage.status == "completed")
        total_nodes_executed = sum(
            stage.total_nodes for stage in state.stages if stage.total_nodes > 0
        )

        if state.started_running_at and state.completed_at:
            total_duration_seconds = (state.completed_at - state.started_running_at).total_seconds()

        best_result = state.best_metrics

        if event.success:
            summary = (
                f"Completed {stages_completed} stages with {total_nodes_executed} nodes executed."
            )
        else:
            summary = (
                f"Run stopped after {stages_completed} stages. {event.message or 'Unknown error'}"
            )

    current_stage = (
        state.current_stage if state and state.current_stage else StageId.initial_implementation
    )
    return [
        RunFinishedEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            stage=current_stage,
            node_id=None,
            headline=headline,
            status=event.status,
            success=event.success,
            reason=reason,
            message=event.message,
            summary=summary,
            total_duration_seconds=total_duration_seconds,
            stages_completed=stages_completed,
            total_nodes_executed=total_nodes_executed,
            best_result=best_result,
        )
    ]


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def process_execution_event(
    _run_id: str,
    _event_type: str,
    event_data: NarratorEvent,
    state: Optional[ResearchRunState] = None,
) -> List[TimelineEvent]:
    """
    Process a typed execution event and return timeline events.

    This is the main entry point for the narrator event pipeline.
    Handlers may return multiple events (e.g., stage_started + node_execution_started).

    Args:
        _run_id: Research run ID (unused but kept for API consistency)
        _event_type: Type of raw event (for logging/debugging)
        event_data: Typed event data (Pydantic model)
        state: Current research run state (for context-aware event generation)

    Returns:
        List of timeline events (may be empty)
    """
    # Dispatch based on event type using isinstance checks
    # This provides full type safety - the type checker knows the exact type in each branch
    if isinstance(event_data, StageProgressEvent):
        return handle_stage_progress_event(event_data, state)
    elif isinstance(event_data, StageCompletedEventPayload):
        return handle_stage_completed_event(event_data, state)
    elif isinstance(event_data, StageSummaryEvent):
        return handle_stage_summary_event(event_data, state)
    elif isinstance(event_data, PaperGenerationProgressEvent):
        return handle_paper_generation_progress_event(event_data, state)
    elif isinstance(event_data, RunningCodeEventPayload):
        return handle_running_code_event(event_data, state)
    elif isinstance(event_data, RunCompletedEventPayload):
        return handle_run_completed_event(event_data, state)
    elif isinstance(event_data, RunStartedEventData):
        return handle_run_started_event(event_data, state)
    elif isinstance(event_data, RunFinishedEventData):
        return handle_run_finished_event(event_data, state)
