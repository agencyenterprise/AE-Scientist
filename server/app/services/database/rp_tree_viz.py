"""
Database helpers for research pipeline tree visualizations.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
    """Helpers to read and write tree visualization payloads."""

    async def upsert_tree_viz(
        self,
        *,
        run_id: str,
        stage_id: str,
        viz: dict,
        version: int = 1,
    ) -> int:
        """Insert or update a tree visualization record and return its ID."""
        now = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_tree_viz (run_id, stage_id, viz, version, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, stage_id)
                    DO UPDATE SET
                        viz = EXCLUDED.viz,
                        version = EXCLUDED.version,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (run_id, stage_id, Jsonb(viz), version, now, now),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to upsert tree visualization")
                return int(result["id"])

    async def list_tree_viz_for_run(self, run_id: str) -> List[TreeVizRecord]:
        query = """
            SELECT id, run_id, stage_id, version, viz, created_at, updated_at
            FROM rp_tree_viz
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall() or []
        return [TreeVizRecord(**row) for row in rows]

    async def get_tree_viz(self, run_id: str, stage_id: str) -> Optional[TreeVizRecord]:
        query = """
            SELECT id, run_id, stage_id, version, viz, created_at, updated_at
            FROM rp_tree_viz
            WHERE run_id = %s AND stage_id = %s
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id, stage_id))
                row = await cursor.fetchone()
        if not row:
            return None
        return TreeVizRecord(**row)
