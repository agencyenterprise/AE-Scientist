"""
Database helpers for research pipeline artifacts.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras


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


class ResearchPipelineArtifactsMixin:
    """Helpers to read artifact metadata stored in rp_artifacts."""

    def list_run_artifacts(self, run_id: str) -> List[ResearchPipelineArtifact]:
        query = """
            SELECT id, run_id, artifact_type, filename, file_size, file_type, s3_key,
                   source_path, created_at
            FROM rp_artifacts
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [ResearchPipelineArtifact(**row) for row in rows]

    def get_run_artifact(self, artifact_id: int) -> Optional[ResearchPipelineArtifact]:
        query = """
            SELECT id, run_id, artifact_type, filename, file_size, file_type, s3_key,
                   source_path, created_at
            FROM rp_artifacts
            WHERE id = %s
        """
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (artifact_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return ResearchPipelineArtifact(**row)
