"""
Database helpers for research pipeline telemetry events.
"""

# pylint: disable=not-async-context-manager

from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider


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
    eta_s: Optional[int]
    latest_iteration_time_s: Optional[int]
    created_at: datetime


class RunLogEvent(NamedTuple):
    id: int
    run_id: str
    message: str
    level: str
    created_at: datetime


class SubstageCompletedEvent(NamedTuple):
    id: int
    run_id: str
    stage: str
    summary: dict
    created_at: datetime


class SubstageSummaryEvent(NamedTuple):
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


class BestNodeReasoningEvent(NamedTuple):
    id: int
    run_id: str
    stage: str
    node_id: str
    reasoning: str
    created_at: datetime


class CodeExecutionEvent(NamedTuple):
    id: int
    run_id: str
    execution_id: str
    stage_name: str
    run_type: str
    code: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    exec_time: Optional[float]
    created_at: datetime
    updated_at: datetime


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


class ResearchPipelineEventsMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Methods to read pipeline telemetry events."""

    async def list_stage_progress_events(self, run_id: str) -> List[StageProgressEvent]:
        query = """
            SELECT id, run_id, stage, iteration, max_iterations, progress, total_nodes,
                   buggy_nodes, good_nodes, best_metric, eta_s, latest_iteration_time_s,
                   created_at
            FROM rp_run_stage_progress_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [StageProgressEvent(**row) for row in (rows or [])]

    async def list_run_log_events(
        self, run_id: str, limit: Optional[int] = None
    ) -> List[RunLogEvent]:
        query = """
            SELECT id, run_id, message, level, created_at
            FROM rp_run_log_events
            WHERE run_id = %s
            ORDER BY created_at DESC
        """
        params: list[object] = [run_id]
        if limit is not None and limit > 0:
            query += " LIMIT %s"
            params.append(limit)
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, tuple(params))
                rows = await cursor.fetchall()
        return [RunLogEvent(**row) for row in (rows or [])]

    async def list_substage_completed_events(self, run_id: str) -> List[SubstageCompletedEvent]:
        query = """
            SELECT id, run_id, stage, summary, created_at
            FROM rp_substage_completed_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [SubstageCompletedEvent(**row) for row in (rows or [])]

    async def list_substage_summary_events(self, run_id: str) -> List[SubstageSummaryEvent]:
        query = """
            SELECT id,
                   run_id,
                   stage,
                   summary,
                   created_at
            FROM rp_substage_summary_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [SubstageSummaryEvent(**row) for row in (rows or [])]

    async def get_latest_substage_summary(self, run_id: str) -> Optional[SubstageSummaryEvent]:
        query = """
            SELECT id,
                   run_id,
                   stage,
                   summary,
                   created_at
            FROM rp_substage_summary_events
            WHERE run_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        return SubstageSummaryEvent(**row) if row else None

    async def list_run_log_events_since(
        self, run_id: str, since: datetime, limit: int = 100
    ) -> List[RunLogEvent]:
        """Fetch log events created after the given timestamp."""
        query = """
            SELECT id, run_id, message, level, created_at
            FROM rp_run_log_events
            WHERE run_id = %s AND created_at > %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id, since, limit))
                rows = await cursor.fetchall()
        return [RunLogEvent(**row) for row in (rows or [])]

    async def list_run_log_events_after_id(
        self, run_id: str, last_id: int, *, limit: int = 100
    ) -> List[RunLogEvent]:
        query = """
            SELECT id, run_id, message, level, created_at
            FROM rp_run_log_events
            WHERE run_id = %s AND id > %s
            ORDER BY id ASC
            LIMIT %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id, last_id, limit))
                rows = await cursor.fetchall()
        return [RunLogEvent(**row) for row in (rows or [])]

    async def get_latest_stage_progress(self, run_id: str) -> Optional[StageProgressEvent]:
        """Fetch the most recent stage progress event for a run."""
        query = """
            SELECT id, run_id, stage, iteration, max_iterations, progress, total_nodes,
                   buggy_nodes, good_nodes, best_metric, eta_s, latest_iteration_time_s,
                   created_at
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

    async def list_best_node_reasoning_events(self, run_id: str) -> List[BestNodeReasoningEvent]:
        """Fetch reasoning emitted when the best node is chosen."""
        query = """
            SELECT id, run_id, stage, node_id, reasoning, created_at
            FROM rp_best_node_reasoning_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall()
        return [BestNodeReasoningEvent(**row) for row in (rows or [])]

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
                   code,
                   status,
                   started_at,
                   completed_at,
                   exec_time,
                   created_at,
                   updated_at
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
                   code,
                   status,
                   started_at,
                   completed_at,
                   exec_time,
                   created_at,
                   updated_at
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
