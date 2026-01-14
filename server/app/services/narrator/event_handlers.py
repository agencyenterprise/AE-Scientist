"""
Event Handlers for Narrator Architecture

Transform raw execution events into timeline events.
These are the translation layer between technical execution and narrative presentation.

Pattern:
- Extract, don't generate (use existing data)
- Simple transformations
- No LLM calls (for now)
- Return timeline events or None
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, cast

from app.models.narrator_state import ResearchRunState
from app.models.timeline_events import (
    MetricCollection,
    MetricInterpretation,
    NodeExecutionCompletedEvent,
    NodeExecutionStartedEvent,
    NodeResultEvent,
    PaperGenerationStepEvent,
    ProgressUpdateEvent,
    StageCompletedEvent,
    StageStartedEvent,
    TimelineEvent,
)
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
# EVENT HANDLERS (Raw Event → Timeline Event)
# ============================================================================


def handle_stage_progress_event(
    _run_id: str, event_data: Dict[str, Any], state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform stage_progress event into timeline event.

    Creates:
    - StageStartedEvent (if iteration == 1 AND stage not already started)
    - ProgressUpdateEvent (otherwise)

    Args:
        run_id: Research run ID
        event_data: Raw stage_progress event data
        state: Current research run state (for checking if stage already started)

    Returns:
        List of timeline events
    """
    stage = event_data.get("stage", "")
    iteration = event_data.get("iteration", 1)
    max_iterations = event_data.get("max_iterations", 10)
    # progress = event_data.get("progress", 0.0)
    best_metric = event_data.get("best_metric")

    now = datetime.now(timezone.utc)

    # If iteration == 1 AND stage not already started, this is stage start
    if iteration == 1 and state and not is_stage_started(state, stage):
        stage_name = STAGE_NAMES.get(stage, stage) or stage
        return [
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=now,
                stage=stage,
                node_id=None,
                headline=f"Starting {stage_name}",
                stage_name=stage_name,
                goal=None,
            )
        ]

    # Otherwise, it's a progress update
    stage_name = STAGE_NAMES.get(stage, stage)
    current_focus = f"{stage_name}: Iteration {iteration}/{max_iterations}"

    # Create metric interpretation if we have best_metric
    current_best = None
    if best_metric:
        try:
            metric_value = float(best_metric)
            current_best = MetricCollection(
                primary=MetricInterpretation(
                    name="best_metric",
                    value=metric_value,
                    formatted=f"{metric_value:.4f}",
                    interpretation="Current best",
                    context=f"Stage {stage}",
                    comparison=None,  # TODO: fill in
                )
            )
        except (ValueError, TypeError):
            pass

    return [
        ProgressUpdateEvent(
            id=str(uuid.uuid4()),
            timestamp=now,
            stage=stage,
            node_id=None,
            headline=f"Iteration {iteration}/{max_iterations}",
            current_focus=current_focus,
            iteration=iteration,
            max_iterations=max_iterations,
            current_best=current_best,
        )
    ]


def handle_substage_completed_event(
    _run_id: str, event_data: Dict[str, Any], _state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform substage_completed event into StageCompletedEvent.

    Args:
        run_id: Research run ID
        event_data: Raw substage_completed event data

    Returns:
        List with StageCompletedEvent
    """
    stage = event_data.get("stage", "")
    summary = event_data.get("summary", {})

    now = datetime.now(timezone.utc)
    stage_name = STAGE_NAMES.get(stage, stage)

    # Extract data from summary
    best_node_id = summary.get("best_node_id")
    total_attempts = summary.get("total_nodes", 0)
    successful_attempts = summary.get("good_nodes", 0)
    failed_attempts = summary.get("buggy_nodes", 0)

    # Extract best metric if available
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
                    context=f"Stage {stage}",
                    comparison=None,  # TODO: fill in
                )
            )
        except (ValueError, TypeError):
            pass

    # Extract summary text if available
    summary_text = summary.get("summary_text") or summary.get("reason")

    return [
        StageCompletedEvent(
            id=str(uuid.uuid4()),
            timestamp=now,
            stage=stage,
            node_id=best_node_id,
            headline=f"{stage_name} Complete",
            summary=summary_text,
            best_node_id=best_node_id,
            best_metrics=best_metrics,
            total_attempts=total_attempts,
            successful_attempts=successful_attempts,
            failed_attempts=failed_attempts,
            confidence=None,
        )
    ]


def handle_substage_summary_event(
    _run_id: str, _event_data: Dict[str, Any], _state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform substage_summary event (LLM-generated) into enriched data.

    For now, we don't create a separate timeline event from this.
    Instead, we use this data to enrich the StageCompletedEvent.

    This handler exists for future use when we want to extract
    insights or key learnings from the LLM-generated summary.

    Args:
        run_id: Research run ID
        event_data: Raw substage_summary event data

    Returns:
        None (for now, used for enrichment only)
    """
    # Future: Extract insights, key learnings, confidence level
    # For now, return empty list (no separate timeline event)
    return []


def handle_best_node_selection_event(
    _run_id: str, event_data: Dict[str, Any], _state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform best_node_selection event into NodeResultEvent.

    This event tells us which node was selected as best for a stage,
    along with the reasoning (LLM-generated).

    Args:
        run_id: Research run ID
        event_data: Raw best_node_selection event data

    Returns:
        List with NodeResultEvent
    """
    stage = event_data.get("stage", "")
    node_id = event_data.get("node_id", "")
    reasoning = event_data.get("reasoning", "")

    now = datetime.now(timezone.utc)

    # Create a node result event marking this as the best node
    return [
        NodeResultEvent(
            id=str(uuid.uuid4()),
            timestamp=now,
            stage=stage,
            node_id=node_id,
            headline=f"Best Node Selected: {node_id}",
            outcome="success",
            summary=reasoning,
            metrics=None,
            error_type=None,
            error_summary=None,
            exec_time=None,
        )
    ]


def handle_running_code_event(
    _run_id: str, event_data: Dict[str, Any], state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform running_code event into NodeExecutionStartedEvent.

    Note: This is the first signal that a stage has started (code is executing).
    If the stage hasn't started yet (checked via state), we emit stage_started first.

    Args:
        run_id: Research run ID
        event_data: Raw running_code event data
        state: Current research run state (for checking if stage already started)

    Returns:
        List of timeline events
    """
    execution_id = event_data.get("execution_id", "")
    stage_name = event_data.get("stage_name", "")
    run_type = event_data.get("run_type", "main_execution")
    code = event_data.get("code", "")
    started_at_str = event_data.get("started_at", "")

    # Parse timestamp
    try:
        started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        started_at = datetime.now(timezone.utc)

    # Create code preview (first 100 chars)
    code_preview = code[:100] + "..." if len(code) > 100 else code

    events: List[TimelineEvent] = []
    offset_ms = 0  # Start with 0 offset

    # If stage hasn't started, emit stage_started event first
    if state and not is_stage_started(state, stage_name):
        stage_display_name = STAGE_NAMES.get(stage_name, stage_name) or stage_name
        events.append(
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=started_at + timedelta(milliseconds=offset_ms),
                stage=stage_name,
                node_id=None,
                headline=f"Starting {stage_display_name}",
                stage_name=stage_display_name,
                goal=None,
            )
        )
        offset_ms += 10  # Increment offset for next event

    # Then emit node execution started event
    events.append(
        NodeExecutionStartedEvent(
            id=str(uuid.uuid4()),
            timestamp=started_at + timedelta(milliseconds=offset_ms),
            stage=stage_name,
            node_id=execution_id,
            headline=f"Node {execution_id[:8]} started",
            execution_id=execution_id,
            run_type=run_type,
            code_preview=code_preview,
        )
    )
    offset_ms += 10  # Increment for consistency

    return events


def handle_run_completed_event(
    _run_id: str, event_data: Dict[str, Any], _state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform run_completed event into NodeExecutionCompletedEvent.

    Args:
        run_id: Research run ID
        event_data: Raw run_completed event data

    Returns:
        List with NodeExecutionCompletedEvent
    """
    execution_id = event_data.get("execution_id", "")
    stage_name = event_data.get("stage_name", "")
    status = event_data.get("status", "success")
    exec_time = event_data.get("exec_time", 0.0)
    run_type = event_data.get("run_type", "main_execution")
    completed_at_str = event_data.get("completed_at", "")

    # Parse timestamp
    try:
        completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        completed_at = datetime.now(timezone.utc)

    status_emoji = "✅" if status == "success" else "❌"
    headline = f"{status_emoji} Node {execution_id[:8]} {status} ({exec_time:.1f}s)"

    return [
        NodeExecutionCompletedEvent(
            id=str(uuid.uuid4()),
            timestamp=completed_at,
            stage=stage_name,
            node_id=execution_id,
            headline=headline,
            execution_id=execution_id,
            status=status,
            exec_time=exec_time,
            run_type=run_type,
        )
    ]


def handle_paper_generation_progress_event(
    _run_id: str, event_data: Dict[str, Any], state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform paper_generation_progress event into PaperGenerationStepEvent.

    When progress reaches 1.0, also emits a StageCompletedEvent for paper generation.
    If this is the first paper generation event and the stage hasn't started, also emits StageStartedEvent.

    Args:
        run_id: Research run ID
        event_data: Raw paper_generation_progress event data
        state: Current research run state (for checking if stage already started)

    Returns:
        List of timeline events (1-3 events)
    """
    step = event_data.get("step", "")
    substep = event_data.get("substep")
    progress = event_data.get("progress", 0.0)
    step_progress = event_data.get("step_progress", 0.0)
    details = event_data.get("details")

    now = datetime.now(timezone.utc)
    offset_ms = 0  # Start with 0 offset

    events: List[TimelineEvent] = []

    # If stage not started, emit StageStartedEvent first
    if state and not is_stage_started(state, "5_paper_generation"):
        events.append(
            StageStartedEvent(
                id=str(uuid.uuid4()),
                timestamp=now + timedelta(milliseconds=offset_ms),
                stage="5_paper_generation",
                node_id=None,
                headline="Starting Paper Generation",
                stage_name="Paper Generation",
                goal=None,
            )
        )
        offset_ms += 10  # Increment offset for next event

    # Create headline
    headline = f"Paper: {step.replace('_', ' ').title()}"
    if substep:
        headline += f" - {substep}"

    # Add the paper generation step event
    events.append(
        PaperGenerationStepEvent(
            id=str(uuid.uuid4()),
            timestamp=now + timedelta(milliseconds=offset_ms),
            stage="5_paper_generation",
            node_id=None,
            headline=headline,
            step=step,
            substep=substep,
            description=None,
            progress=progress,
            step_progress=step_progress,
            details=details,
        )
    )
    offset_ms += 10  # Increment offset for next event

    # If progress is 1.0, paper generation is complete
    if progress >= 1.0:
        events.append(
            StageCompletedEvent(
                id=str(uuid.uuid4()),
                timestamp=now + timedelta(milliseconds=offset_ms),
                stage="5_paper_generation",
                node_id=None,
                headline="Paper Generation Complete",
                summary="Research paper completed with all sections, citations, and reviews",
                best_node_id=None,
                best_metrics=None,
                total_attempts=1,
                successful_attempts=1,
                failed_attempts=0,
                confidence=None,
            )
        )
        offset_ms += 10  # Increment for consistency (even though it's the last event)

    return events


def handle_run_finished_event(
    _run_id: str, _event_data: Dict[str, Any], _state: Optional[ResearchRunState] = None
) -> List[TimelineEvent]:
    """
    Transform run_finished event into timeline event.

    This marks the entire research run as complete and triggers queue cleanup.

    Args:
        run_id: Research run ID
        event_data: Raw run_finished event data (success, status, message)
        state: Current research run state (unused)

    Returns:
        Empty list (no timeline event, just triggers cleanup)
    """
    # No timeline event needed - this is just for cleanup signaling
    # The actual completion is already captured by stage_completed events
    return []


# ============================================================================
# DISPATCH TABLE
# ============================================================================

# Type alias for the transformer function signature
TransformerFn = Callable[
    [str, Dict[str, Any], Optional[ResearchRunState]],
    List[TimelineEvent],
]

# The actual dispatch table
# We use a controlled cast here to bridge the gap between:
# - What we know: each transformer handles specific raw event types correctly
# - What mypy needs: a consistent signature for all transformers in the dict
#
# This is a standard pattern in typed Python for event dispatch systems.
# The invariant we're asserting: "The event_type key guarantees the correct
# raw event data structure will be passed to each transformer at runtime."
EVENT_HANDLERS: Dict[str, TransformerFn] = cast(
    Dict[str, TransformerFn],
    {
        "stage_progress": handle_stage_progress_event,
        "substage_completed": handle_substage_completed_event,
        "substage_summary": handle_substage_summary_event,
        "paper_generation_progress": handle_paper_generation_progress_event,
        "best_node_selection": handle_best_node_selection_event,
        "running_code": handle_running_code_event,
        "run_completed": handle_run_completed_event,
        "run_finished": handle_run_finished_event,
    },
)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def process_execution_event(
    run_id: str,
    event_type: str,
    event_data: Dict[str, Any],
    state: Optional[ResearchRunState] = None,
) -> List[TimelineEvent]:
    """
    Process a raw execution event and return timeline events.

    This is the main entry point for the narrator event pipeline.
    Handlers may return multiple events (e.g., stage_started + node_execution_started).

    Args:
        run_id: Research run ID
        event_type: Type of raw event (stage_progress, substage_completed, etc.)
        event_data: Raw event data
        state: Current research run state (for context-aware event generation)

    Returns:
        List of timeline events (may be empty)

    Pattern:
        - Simple dispatcher pattern
        - Handlers receive state for context-aware decisions
        - Handlers return List[TimelineEvent] (may be empty)
        - Multiple events can be emitted from a single raw event

    Type safety:
        - The event_type key determines which transformer is called
        - Each transformer knows how to handle its specific raw event structure
        - Runtime dispatch is safe due to the webhook endpoint routing
    """
    handler = EVENT_HANDLERS.get(event_type)

    if handler is None:
        # Unknown event type - no timeline events
        return []

    # Call handler to transform raw event → timeline events
    return handler(run_id, event_data, state)
