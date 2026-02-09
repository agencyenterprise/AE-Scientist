"""
Database helpers for research pipeline telemetry events.
"""

# pylint: disable=not-async-context-manager

from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Protocol, Sequence

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class CodexEventItemProtocol(Protocol):
    """Protocol for codex event items to avoid circular imports."""

    stage: str
    node: int
    event_type: str
    event_content: dict[str, Any]
    occurred_at: str  # ISO format timestamp


class StageProgressEvent(NamedTuple):
    id: int
    run_id: str
    stage: str
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str]
    is_seed_node: bool
    created_at: datetime


class StageCompletedEvent(NamedTuple):
    id: int
    run_id: str
    stage: str
    summary: dict
    created_at: datetime


class StageSummaryEvent(NamedTuple):
    id: int
    run_id: str
    stage: str
    summary: dict
    created_at: datetime


class PaperGenerationEvent(NamedTuple):
    id: int
    run_id: str
    step: str
    substep: Optional[str]
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]]
    created_at: datetime


class CodeExecutionEvent(NamedTuple):
    id: int
    run_id: str
    execution_id: str
    stage_name: str
    run_type: str
    execution_type: str  # stage_goal, seed, aggregation, metrics
    code: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    exec_time: Optional[float]
    created_at: datetime
    updated_at: datetime
    node_index: int


class StageSkipWindowRecord(NamedTuple):
    id: int
    run_id: str
    stage: str
    opened_at: datetime
    opened_reason: Optional[str]
    closed_at: Optional[datetime]
    closed_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class CodexEventRecord(NamedTuple):
    id: int
    run_id: str
    stage: str
    node: int
    event_type: str
    event_content: dict
    created_at: datetime


class ResearchPipelineEventsMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Methods to read and write pipeline telemetry events."""

    # === INSERT METHODS ===

    async def insert_stage_progress_event(
        self,
        *,
        run_id: str,
        stage: str,
        iteration: int,
        max_iterations: int,
        progress: float,
        total_nodes: int,
        buggy_nodes: int,
        good_nodes: int,
        best_metric: Optional[str] = None,
        is_seed_node: bool = False,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert a stage progress event and return its ID."""
        if created_at is None:
            created_at = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_run_stage_progress_events
                        (run_id, stage, iteration, max_iterations, progress, total_nodes,
                         buggy_nodes, good_nodes, best_metric, is_seed_node, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        run_id,
                        stage,
                        iteration,
                        max_iterations,
                        progress,
                        total_nodes,
                        buggy_nodes,
                        good_nodes,
                        best_metric,
                        is_seed_node,
                        created_at,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert stage progress event")
                return int(result["id"])

    async def insert_run_log_event(
        self,
        *,
        run_id: str,
        message: str,
        level: str = "info",
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert a run log event and return its ID."""
        if created_at is None:
            created_at = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_run_log_events (run_id, message, level, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, message, level, created_at),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert run log event")
                return int(result["id"])

    async def insert_stage_completed_event(
        self,
        *,
        run_id: str,
        stage: str,
        summary: dict,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert a stage completed event and return its ID."""
        if created_at is None:
            created_at = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_stage_completed_events (run_id, stage, summary, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, stage, Jsonb(summary), created_at),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert stage completed event")
                return int(result["id"])

    async def insert_stage_summary_event(
        self,
        *,
        run_id: str,
        stage: str,
        summary: dict,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert a stage summary event and return its ID."""
        if created_at is None:
            created_at = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_stage_summary_events (run_id, stage, summary, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, stage, Jsonb(summary), created_at),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert stage summary event")
                return int(result["id"])

    async def insert_paper_generation_event(
        self,
        *,
        run_id: str,
        step: str,
        substep: Optional[str],
        progress: float,
        step_progress: float,
        details: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert a paper generation event and return its ID."""
        if created_at is None:
            created_at = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_paper_generation_events
                        (run_id, step, substep, progress, step_progress, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        run_id,
                        step,
                        substep,
                        progress,
                        step_progress,
                        Jsonb(details) if details is not None else None,
                        created_at,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert paper generation event")
                return int(result["id"])

    async def insert_codex_event(
        self,
        *,
        run_id: str,
        stage: str,
        node: int,
        event_type: str,
        event_content: dict,
        occurred_at: datetime,
    ) -> int:
        """Insert a codex event and return its ID."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_codex_events
                        (run_id, stage, node, event_type, event_content, occurred_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, stage, node, event_type, Jsonb(event_content), occurred_at, now),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert codex event")
                return int(result["id"])

    async def insert_codex_events_bulk(
        self,
        *,
        run_id: str,
        events: Sequence[CodexEventItemProtocol],
    ) -> int:
        """Bulk insert codex events. Returns the number of events inserted."""
        if not events:
            return 0

        now = datetime.now()
        # Build values for bulk insert
        values = [
            (
                run_id,
                event.stage,
                event.node,
                event.event_type,
                Jsonb(event.event_content),
                event.occurred_at,
                now,
            )
            for event in events
        ]

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(
                    """
                    INSERT INTO rp_codex_events
                        (run_id, stage, node, event_type, event_content, occurred_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
                return len(events)

    async def upsert_code_execution_event(
        self,
        *,
        run_id: str,
        execution_id: str,
        stage_name: str,
        run_type: str,
        execution_type: str,
        code: Optional[str] = None,
        status: str = "running",
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        exec_time: Optional[float] = None,
        node_index: Optional[int] = None,
    ) -> int:
        """Insert or update a code execution event and return its ID."""
        now = datetime.now()
        if started_at is None:
            started_at = now

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_code_execution_events
                        (run_id, execution_id, stage_name, run_type, execution_type, code, status,
                         started_at, completed_at, exec_time, node_index, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, execution_id, run_type)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        exec_time = EXCLUDED.exec_time,
                        execution_type = COALESCE(EXCLUDED.execution_type, rp_code_execution_events.execution_type),
                        node_index = COALESCE(EXCLUDED.node_index, rp_code_execution_events.node_index),
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (
                        run_id,
                        execution_id,
                        stage_name,
                        run_type,
                        execution_type,
                        code,
                        status,
                        started_at,
                        completed_at,
                        exec_time,
                        node_index,
                        now,
                        now,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to upsert code execution event")
                return int(result["id"])

    async def upsert_stage_skip_window(
        self,
        *,
        run_id: str,
        stage: str,
        state: str,
        timestamp: datetime,
        reason: Optional[str] = None,
    ) -> int:
        """Insert or update a stage skip window record and return its ID."""
        now = datetime.now()

        if state == "opened":
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO rp_stage_skip_windows
                            (run_id, stage, opened_at, opened_reason, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (run_id, stage)
                        DO UPDATE SET
                            opened_at = EXCLUDED.opened_at,
                            opened_reason = EXCLUDED.opened_reason,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id
                        """,
                        (run_id, stage, timestamp, reason, now, now),
                    )
                    result = await cursor.fetchone()
                    if not result:
                        raise ValueError("Failed to upsert stage skip window (opened)")
                    return int(result["id"])
        else:  # state == "closed"
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        UPDATE rp_stage_skip_windows
                        SET closed_at = %s, closed_reason = %s, updated_at = %s
                        WHERE run_id = %s AND stage = %s
                        RETURNING id
                        """,
                        (timestamp, reason, now, run_id, stage),
                    )
                    result = await cursor.fetchone()
                    if not result:
                        # Window doesn't exist yet, create it as closed
                        await cursor.execute(
                            """
                            INSERT INTO rp_stage_skip_windows
                                (run_id, stage, closed_at, closed_reason, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (run_id, stage, timestamp, reason, now, now),
                        )
                        result = await cursor.fetchone()
                        if not result:
                            raise ValueError("Failed to insert stage skip window (closed)")
                    return int(result["id"])

    # === READ METHODS ===

    async def list_stage_progress_events(self, run_id: str) -> List[StageProgressEvent]:
        query = """
            SELECT id, run_id, stage, iteration, max_iterations, progress, total_nodes,
                   buggy_nodes, good_nodes, best_metric, is_seed_node, created_at
            FROM rp_run_stage_progress_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [StageProgressEvent(**row) for row in (rows or [])]

    async def list_stage_completed_events(self, run_id: str) -> List[StageCompletedEvent]:
        query = """
            SELECT id, run_id, stage, summary, created_at
            FROM rp_stage_completed_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [StageCompletedEvent(**row) for row in (rows or [])]

    async def list_stage_summary_events(self, run_id: str) -> List[StageSummaryEvent]:
        query = """
            SELECT id,
                   run_id,
                   stage,
                   summary,
                   created_at
            FROM rp_stage_summary_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [StageSummaryEvent(**row) for row in (rows or [])]

    async def get_latest_stage_summary(self, run_id: str) -> Optional[StageSummaryEvent]:
        query = """
            SELECT id,
                   run_id,
                   stage,
                   summary,
                   created_at
            FROM rp_stage_summary_events
            WHERE run_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        return StageSummaryEvent(**row) if row else None

    async def get_latest_stage_progress(self, run_id: str) -> Optional[StageProgressEvent]:
        """Fetch the most recent stage progress event for a run."""
        query = """
            SELECT id, run_id, stage, iteration, max_iterations, progress, total_nodes,
                   buggy_nodes, good_nodes, best_metric, is_seed_node, created_at
            FROM rp_run_stage_progress_events
            WHERE run_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        return StageProgressEvent(**row) if row else None

    async def list_paper_generation_events(self, run_id: str) -> List[PaperGenerationEvent]:
        """Fetch all paper generation events for a run, ordered chronologically."""
        query = """
            SELECT id, run_id, step, substep, progress, step_progress, details, created_at
            FROM rp_paper_generation_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [PaperGenerationEvent(**row) for row in (rows or [])]

    async def get_latest_paper_generation_event(
        self, run_id: str
    ) -> Optional[PaperGenerationEvent]:
        """Fetch most recent paper generation event for a run."""
        query = """
            SELECT id, run_id, step, substep, progress, step_progress, details, created_at
            FROM rp_paper_generation_events
            WHERE run_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        return PaperGenerationEvent(**row) if row else None

    async def get_latest_code_execution_event(self, run_id: str) -> Optional[CodeExecutionEvent]:
        """Fetch the most recent code execution event for a run."""
        query = """
            SELECT id,
                   run_id,
                   execution_id,
                   stage_name,
                   run_type,
                   execution_type,
                   code,
                   status,
                   started_at,
                   completed_at,
                   exec_time,
                   created_at,
                   updated_at,
                   node_index
            FROM rp_code_execution_events
            WHERE run_id = %s
            ORDER BY started_at DESC NULLS LAST, id DESC
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        return CodeExecutionEvent(**row) if row else None

    async def list_latest_code_execution_events_by_run_type(
        self,
        *,
        run_id: str,
    ) -> List[CodeExecutionEvent]:
        """Fetch the latest code execution event per run_type for a run."""
        query = """
            SELECT DISTINCT ON (run_type)
                   id,
                   run_id,
                   execution_id,
                   stage_name,
                   run_type,
                   execution_type,
                   code,
                   status,
                   started_at,
                   completed_at,
                   exec_time,
                   created_at,
                   updated_at,
                   node_index
            FROM rp_code_execution_events
            WHERE run_id = %s
            ORDER BY run_type, started_at DESC NULLS LAST, id DESC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [CodeExecutionEvent(**row) for row in (rows or [])]

    async def list_stage_skip_windows(self, run_id: str) -> List[StageSkipWindowRecord]:
        """Fetch all recorded stage skip eligibility windows for a run."""
        query = """
            SELECT id,
                   run_id,
                   stage,
                   opened_at,
                   opened_reason,
                   closed_at,
                   closed_reason,
                   created_at,
                   updated_at
            FROM rp_stage_skip_windows
            WHERE run_id = %s
            ORDER BY opened_at ASC, id ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [StageSkipWindowRecord(**row) for row in (rows or [])]
