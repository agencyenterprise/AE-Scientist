"""
Narrator Service - Main Entry Point

This is the orchestrator that:
1. Receives raw execution events (non-blocking, queued)
2. Processes them sequentially (one at a time)
3. Transforms them into timeline events (via event_handlers)
4. Updates state via reducer (via state_reducer)
5. Persists timeline events and state to database
6. Publishes events to SSE subscribers

Pattern:
- Feature-flagged (can be disabled)
- Queue-based (events processed sequentially to avoid race conditions)
- Non-blocking ingestion (errors logged, not raised)
- Idempotent (safe to retry)
- Data-driven (simple functions compose)
- Database-locked (uses SELECT FOR UPDATE for consistency)
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.api.narrator_stream import publish_narrator_event
from app.models.narrator_state import ResearchRunState, create_initial_state
from app.services.database import DatabaseManager

from .event_handlers import process_execution_event
from .state_reducer import apply_changes, reduce

logger = logging.getLogger(__name__)

# ============================================================================
# EVENT QUEUE - ONE QUEUE PER RUN_ID
# ============================================================================

# Global dict of queues, one per run_id
_event_queues: Dict[str, asyncio.Queue] = {}
_queue_processors: Dict[str, asyncio.Task] = {}
_run_completed: Dict[str, bool] = {}  # Track which runs have completed


def _get_queue_for_run(run_id: str) -> asyncio.Queue:
    """
    Get or create event queue for a specific run_id.

    Each run has its own queue to allow parallel processing across runs
    while maintaining sequential processing within a run.
    """
    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()
    return _event_queues[run_id]


async def _process_event_queue(run_id: str, db: DatabaseManager) -> None:
    """
    Process events from queue sequentially.

    This runs as a background task, consuming events one at a time.
    """
    queue = _get_queue_for_run(run_id)

    logger.info("Narrator: Started queue processor for run=%s", run_id)

    while True:
        event_type: str = "<not_set>"
        event_data: Dict[str, Any] = {}
        try:
            # Check if run is complete and queue is empty BEFORE waiting for next event
            if _run_completed.get(run_id, False) and queue.qsize() == 0:
                logger.info("Narrator: Run complete and queue empty, cleaning up run=%s", run_id)
                _cleanup_run_queue(run_id)
                break

            # Wait for next event (blocks until available)
            logger.debug(
                "Narrator: Waiting for event from queue run=%s queue_size=%d", run_id, queue.qsize()
            )
            event_type, event_data = await queue.get()

            logger.info("Narrator: Processing event from queue run=%s type=%s", run_id, event_type)

            # Process the event
            await _process_single_event(db, run_id, event_type, event_data)

            # Mark task as done
            queue.task_done()

            logger.debug("Narrator: Event processed, queue_size=%d run=%s", queue.qsize(), run_id)

        except asyncio.CancelledError:
            logger.info("Narrator: Queue processor cancelled for run=%s", run_id)
            break
        except Exception as exc:
            logger.exception(
                "Narrator: Error in queue processor for run=%s type=%s event_data=%r: %s",
                run_id,
                event_type,
                event_data,
                exc,
            )
            # Mark task as done even on error to prevent queue blocking
            try:
                queue.task_done()
            except ValueError:
                pass  # task_done() called too many times
            # Continue processing despite errors


def _ensure_queue_processor_running(run_id: str, db: DatabaseManager) -> None:
    """
    Ensure background queue processor is running for this run_id.
    """
    if run_id not in _queue_processors or _queue_processors[run_id].done():
        # Start new processor task
        logger.info("Narrator: Creating queue processor task for run=%s", run_id)
        task = asyncio.create_task(_process_event_queue(run_id, db))
        _queue_processors[run_id] = task
        logger.info("Narrator: Queue processor task created for run=%s", run_id)


def _cleanup_run_queue(run_id: str) -> None:
    """
    Clean up queue and processor for a completed run.

    This prevents memory leaks by removing queues for finished runs.
    """
    if run_id in _event_queues:
        del _event_queues[run_id]
        logger.debug("Narrator: Cleaned up queue for run=%s", run_id)

    if run_id in _queue_processors:
        del _queue_processors[run_id]
        logger.debug("Narrator: Cleaned up processor for run=%s", run_id)

    if run_id in _run_completed:
        del _run_completed[run_id]
        logger.debug("Narrator: Cleaned up completion flag for run=%s", run_id)


def _mark_run_completed(run_id: str) -> None:
    """
    Mark a run as completed so its queue can be cleaned up.

    The queue will be cleaned up after all pending events are processed.
    """
    _run_completed[run_id] = True
    logger.info("Narrator: Marked run as completed run=%s", run_id)


# ============================================================================
# MAIN INGESTION FUNCTION (NON-BLOCKING)
# ============================================================================


async def ingest_narration_event(
    db: DatabaseManager,
    *,
    run_id: str,
    event_type: str,
    event_data: Dict[str, Any],
) -> None:
    """
    Main entry point for narrator event ingestion (non-blocking).

    This function:
    1. Checks feature flag
    2. Adds event to queue (non-blocking)
    3. Ensures queue processor is running

    The actual processing happens asynchronously in the background.

    Args:
        db: Database manager
        run_id: Research run ID
        event_type: Type of execution event (stage_progress, substage_completed, etc.)
        event_data: Raw event data

    Pattern:
        - Non-blocking: Returns immediately after queuing
        - Idempotent: Safe to call multiple times with same event
        - Feature-flagged: Can be disabled without breaking existing system
        - Sequential: Events processed one at a time per run_id
    """
    try:
        # Get queue for this run
        queue = _get_queue_for_run(run_id)

        # Ensure processor is running
        _ensure_queue_processor_running(run_id, db)

        # Add event to queue (non-blocking)
        await queue.put((event_type, event_data))

        logger.debug(
            "Narrator: Queued event run=%s type=%s queue_size=%d",
            run_id,
            event_type,
            queue.qsize(),
        )

    except Exception as exc:
        # Log error but don't raise - narrator should not break existing system
        logger.exception(
            "Narrator: Error queuing event run=%s type=%s: %s",
            run_id,
            event_type,
            exc,
        )


# ============================================================================
# EVENT PROCESSING (SEQUENTIAL, WITH DATABASE LOCK)
# ============================================================================


async def _process_single_event(
    db: DatabaseManager,
    run_id: str,
    event_type: str,
    event_data: Dict[str, Any],
) -> None:
    """
    Process a single event with database locking.

    This function:
    1. Acquires database lock on state row (SELECT FOR UPDATE)
    2. Fetches current state
    3. Generates timeline events
    4. Persists timeline events
    5. Updates state
    6. Commits transaction (releases lock)

    Args:
        db: Database manager
        run_id: Research run ID
        event_type: Type of execution event
        event_data: Raw event data
    """
    # Use database connection (auto-commits on success, rolls back on error)
    async with db.aget_connection() as conn:
        # Step 1: Get or create state (with lock)
        current_state = await _get_or_create_state_locked(db, run_id, conn)

        # Step 2: Generate timeline events
        timeline_events = process_execution_event(run_id, event_type, event_data, current_state)

        # Check if this is the run_finished event (triggers cleanup)
        # Do this BEFORE the empty check so it executes even if no timeline events
        if event_type == "run_finished":
            _mark_run_completed(run_id)

        if not timeline_events:
            # No timeline events for this execution event (normal)
            logger.debug(
                "Narrator: No timeline events generated for run=%s type=%s", run_id, event_type
            )
            return

        logger.info(
            "Narrator: Processing %d event(s) run=%s type=%s → timeline_types=%s",
            len(timeline_events),
            run_id,
            event_type,
            [e.type for e in timeline_events],
        )

        # Step 3: Persist timeline events and publish to SSE subscribers
        for timeline_event in timeline_events:
            await db.insert_timeline_event(run_id=run_id, event=timeline_event)

            # Publish timeline event to SSE subscribers immediately after persistence
            publish_narrator_event(
                run_id=run_id,
                event_type="timeline_event",
                data=timeline_event.model_dump(mode="json"),
            )

        # Step 4: Apply events through reducer to compute new state
        # Accumulate all state changes to publish as a single delta
        new_state = current_state
        accumulated_changes: Dict[str, Any] = {}

        for timeline_event in timeline_events:
            update_result = reduce(new_state, timeline_event)

            if update_result.should_update:
                new_state = apply_changes(new_state, update_result.changes)
                # Merge changes into accumulated dict
                accumulated_changes.update(update_result.changes)

        # Step 5: Persist updated state (no version check needed - we have lock)
        await db.upsert_research_run_state(run_id=run_id, state=new_state, conn=conn)

        # Step 6: Publish state delta to SSE subscribers (only changed fields)
        if accumulated_changes:
            # Serialize the changes for JSON transmission

            serialized_changes: Dict[str, Any] = {}
            for key, value in accumulated_changes.items():
                if isinstance(value, BaseModel):
                    # Pydantic model instance - serialize it
                    serialized_changes[key] = value.model_dump(mode="json")
                elif isinstance(value, list):
                    # List - serialize each item if it's a Pydantic model instance
                    serialized_changes[key] = [
                        item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                        for item in value
                    ]
                else:
                    # Primitive type - use as is
                    serialized_changes[key] = value

            publish_narrator_event(
                run_id=run_id,
                event_type="state_delta",
                data=serialized_changes,
            )

        logger.info(
            "Narrator: Events processed successfully run=%s count=%d",
            run_id,
            len(timeline_events),
        )

        # Transaction commits automatically on exit


async def _get_or_create_state_locked(
    db: DatabaseManager,
    run_id: str,
    conn: AsyncConnection[Any],
) -> ResearchRunState:
    """
    Get current state or create initial state if it doesn't exist.

    This should be called within a transaction that has acquired a lock.

    Args:
        db: Database manager
        run_id: Research run ID
        conn: Database connection (within transaction)

    Returns:
        Current or initial research run state
    """
    # Try to get state with lock (SELECT FOR UPDATE)
    current_state = await db.get_research_run_state_locked(run_id, conn)

    if current_state is None:
        # First event for this run - create initial state
        logger.info("Narrator: Creating initial state for run=%s (fallback path)", run_id)

        # Get conversation_id and idea info from research_pipeline_runs + ideas tables
        # TODO: move this somewhere else or throw if we don't need to recover in case the state gets deleted mid-run
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT 
                    rpr.idea_id,
                    i.conversation_id,
                    i.short_hypothesis
                FROM research_pipeline_runs rpr
                JOIN ideas i ON i.id = rpr.idea_id
                WHERE rpr.run_id = %s
                """,
                (run_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            logger.error("Narrator: Cannot create state for unknown run=%s", run_id)
            raise ValueError(f"Research run not found: {run_id}")

        conversation_id = row["conversation_id"]
        short_hypothesis = row["short_hypothesis"]

        current_state = create_initial_state(
            run_id=run_id,
            conversation_id=conversation_id,
            status="running",
            overall_goal=short_hypothesis,
            hypothesis=short_hypothesis,
        )

        # Persist initial state (using the same connection/transaction)
        await db.upsert_research_run_state(run_id=run_id, state=current_state, conn=conn)

    return current_state


# ============================================================================
# HELPER: INITIALIZE STATE FOR RUN
# ============================================================================


async def initialize_run_state(
    db: DatabaseManager,
    *,
    run_id: str,
    conversation_id: int,
    overall_goal: Optional[str] = None,
    hypothesis: Optional[str] = None,
    gpu_type: Optional[str] = None,
    cost_per_hour_cents: Optional[int] = None,
) -> ResearchRunState:
    """
    Initialize state for a new research run.

    This should be called when a run is created, before any events arrive.

    Args:
        db: Database manager
        run_id: Research run ID
        conversation_id: Associated conversation ID
        overall_goal: Optional research objective
        hypothesis: Optional hypothesis being tested
        gpu_type: Optional GPU type
        cost_per_hour_cents: Optional cost per hour in cents

    Returns:
        Initial research run state
    """
    # Create initial state
    initial_state = create_initial_state(
        run_id=run_id,
        conversation_id=conversation_id,
        status="pending",
        overall_goal=overall_goal,
        hypothesis=hypothesis,
    )

    # Add cost information
    if gpu_type:
        initial_state = initial_state.model_copy(update={"gpu_type": gpu_type})
    if cost_per_hour_cents:
        initial_state = initial_state.model_copy(
            update={"cost_per_hour_cents": cost_per_hour_cents}
        )

    # Persist to database
    await db.upsert_research_run_state(run_id=run_id, state=initial_state)

    logger.info("Narrator: Initialized state for run=%s", run_id)

    return initial_state


# ============================================================================
# HELPER: REBUILD STATE FROM EVENTS
# ============================================================================


async def rebuild_state_from_events(
    db: DatabaseManager,
    *,
    run_id: str,
) -> Optional[ResearchRunState]:
    """
    Rebuild state by replaying all timeline events.

    This is useful for:
    - Recovering from state corruption
    - Testing reducer logic
    - Debugging state issues

    Args:
        db: Database manager
        run_id: Research run ID

    Returns:
        Rebuilt state or None if no events found
    """
    # Get all timeline events for this run
    event_rows = await db.get_timeline_events(run_id)

    if not event_rows:
        logger.warning("Narrator: No events found for run=%s", run_id)
        return None

    logger.info(
        "Narrator: Rebuilding state from %d events for run=%s",
        len(event_rows),
        run_id,
    )

    # Get initial state (or create if missing)
    initial_state = await db.get_research_run_state(run_id)
    if initial_state is None:
        # Create minimal initial state
        initial_state = create_initial_state(
            run_id=run_id,
            conversation_id=0,  # Placeholder
            status="running",
        )

    # Clear timeline (we'll rebuild it)
    initial_state.timeline = []

    # Replay events
    current_state = initial_state
    # TODO: implement this
    # for event_row in event_rows:
    #     # Parse event_data back into TimelineEvent
    #     # Note: This requires proper deserialization based on event_type
    #     # event_data = event_row["event_data"]

    #     # For now, we'll skip the actual replay since we need proper
    #     # TimelineEvent deserialization. This is a TODO for later.
    #     # The structure is here, implementation can be completed when needed.
    #     pass

    # Persist rebuilt state
    await db.upsert_research_run_state(run_id=run_id, state=current_state)

    logger.info("Narrator: State rebuilt successfully for run=%s", run_id)

    return current_state
