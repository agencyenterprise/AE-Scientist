"""
Database helpers for research pipeline artifacts.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider


class ResearchPipelineArtifact(NamedTuple):
    id: int
    run_id: str
    artifact_type: str
    filename: str
    file_size: int
    file_type: str
    s3_key: str
    source_path: Optional[str]
    created_at: datetime


class ResearchPipelineArtifactsMixin(ConnectionProvider):
    """Helpers to read and write artifact metadata stored in rp_artifacts."""

    async def upsert_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        filename: str,
        file_size: int,
        file_type: str,
        s3_key: str,
        source_path: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> tuple[int, datetime]:
        """Insert or update an artifact record and return its ID and created_at timestamp."""
        if created_at is None:
            created_at = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_artifacts
                        (run_id, artifact_type, filename, file_size, file_type, s3_key, source_path, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (s3_key)
                    DO UPDATE SET
                        artifact_type = EXCLUDED.artifact_type,
                        filename = EXCLUDED.filename,
                        file_size = EXCLUDED.file_size,
                        file_type = EXCLUDED.file_type,
                        source_path = EXCLUDED.source_path
                    RETURNING id, created_at
                    """,
                    (
                        run_id,
                        artifact_type,
                        filename,
                        file_size,
                        file_type,
                        s3_key,
                        source_path,
                        created_at,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to upsert artifact")
                return int(result["id"]), result["created_at"]

    async def list_run_artifacts(self, run_id: str) -> List[ResearchPipelineArtifact]:
        query = """
            SELECT id, run_id, artifact_type, filename, file_size, file_type, s3_key,
                   source_path, created_at
            FROM rp_artifacts
            WHERE run_id = %s AND artifact_type != 'plot'
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall() or []
        return [ResearchPipelineArtifact(**row) for row in rows]

    async def get_run_artifact(self, artifact_id: int) -> Optional[ResearchPipelineArtifact]:
        query = """
            SELECT id, run_id, artifact_type, filename, file_size, file_type, s3_key,
                   source_path, created_at
            FROM rp_artifacts
            WHERE id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (artifact_id,))
                row = await cursor.fetchone()
        if not row:
            return None
        return ResearchPipelineArtifact(**row)
