"""
Database helpers for research pipeline tree visualizations.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

from .base import ConnectionProvider


class TreeVizRecord(NamedTuple):
    id: int
    run_id: str
    stage_id: str
    version: int
    viz: dict
    created_at: datetime
    updated_at: datetime


class ResearchPipelineTreeVizMixin(ConnectionProvider):
    """Helpers to read tree visualization payloads."""

    def list_tree_viz_for_run(self, run_id: str) -> List[TreeVizRecord]:
        query = """
            SELECT id, run_id, stage_id, version, viz, created_at, updated_at
            FROM rp_tree_viz
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [TreeVizRecord(**row) for row in rows]

    def get_tree_viz(self, run_id: str, stage_id: str) -> Optional[TreeVizRecord]:
        query = """
            SELECT id, run_id, stage_id, version, viz, created_at, updated_at
            FROM rp_tree_viz
            WHERE run_id = %s AND stage_id = %s
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id, stage_id))
                row = cursor.fetchone()
        if not row:
            return None
        return TreeVizRecord(**row)
