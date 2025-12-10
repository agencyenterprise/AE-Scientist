"""
Database helpers for research pipeline telemetry events.
"""

from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

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


class PaperGenerationEvent(NamedTuple):
    id: int
    run_id: str
    step: str
    substep: Optional[str]
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]]
    created_at: datetime


class ResearchPipelineEventsMixin(ConnectionProvider):
    """Methods to read pipeline telemetry events."""

    def list_stage_progress_events(self, run_id: str) -> List[StageProgressEvent]:
        query = """
            SELECT id, run_id, stage, iteration, max_iterations, progress, total_nodes,
                   buggy_nodes, good_nodes, best_metric, eta_s, latest_iteration_time_s,
                   created_at
            FROM rp_run_stage_progress_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [StageProgressEvent(**row) for row in rows]

    def list_run_log_events(self, run_id: str, limit: Optional[int] = None) -> List[RunLogEvent]:
        query = """
            SELECT id, run_id, message, level, created_at
            FROM rp_run_log_events
            WHERE run_id = %s
            ORDER BY created_at DESC
        """
        params: tuple = (run_id,)
        if limit is not None and limit > 0:
            query += " LIMIT %s"
            params = (run_id, limit)
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall() or []
        return [RunLogEvent(**row) for row in rows]

    def list_substage_completed_events(self, run_id: str) -> List[SubstageCompletedEvent]:
        query = """
            SELECT id, run_id, stage, summary, created_at
            FROM rp_substage_completed_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [SubstageCompletedEvent(**row) for row in rows]

    def list_run_log_events_since(
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id, since, limit))
                rows = cursor.fetchall() or []
        return [RunLogEvent(**row) for row in rows]

    def get_latest_stage_progress(self, run_id: str) -> Optional[StageProgressEvent]:
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                row = cursor.fetchone()
        return StageProgressEvent(**row) if row else None

    def list_paper_generation_events(self, run_id: str) -> List[PaperGenerationEvent]:
        """Fetch all paper generation events for a run, ordered chronologically."""
        query = """
            SELECT id, run_id, step, substep, progress, step_progress, details, created_at
            FROM rp_paper_generation_events
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [PaperGenerationEvent(**row) for row in rows]

    def get_latest_paper_generation_event(self, run_id: str) -> Optional[PaperGenerationEvent]:
        """Fetch most recent paper generation event for a run."""
        query = """
            SELECT id, run_id, step, substep, progress, step_progress, details, created_at
            FROM rp_paper_generation_events
            WHERE run_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                row = cursor.fetchone()
        return PaperGenerationEvent(**row) if row else None
