import logging
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class ResearchPipelineRunTermination(NamedTuple):
    run_id: str
    status: str
    requested_at: datetime
    started_at: Optional[datetime]
    updated_at: datetime
    completed_at: Optional[datetime]
    attempts: int
    last_error: Optional[str]
    artifacts_uploaded_at: Optional[datetime]
    pod_terminated_at: Optional[datetime]
    lease_owner: Optional[str]
    lease_expires_at: Optional[datetime]
    last_trigger: Optional[str]


class ResearchPipelineRunTerminationMixin(ConnectionProvider):
    def _row_to_run_termination(self, row: dict) -> ResearchPipelineRunTermination:
        return ResearchPipelineRunTermination(
            run_id=row["run_id"],
            status=row["status"],
            requested_at=row["requested_at"],
            started_at=row.get("started_at"),
            updated_at=row["updated_at"],
            completed_at=row.get("completed_at"),
            attempts=int(row.get("attempts", 0) or 0),
            last_error=row.get("last_error"),
            artifacts_uploaded_at=row.get("artifacts_uploaded_at"),
            pod_terminated_at=row.get("pod_terminated_at"),
            lease_owner=row.get("lease_owner"),
            lease_expires_at=row.get("lease_expires_at"),
            last_trigger=row.get("last_trigger"),
        )

    async def get_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
    ) -> Optional[ResearchPipelineRunTermination]:
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT * FROM research_pipeline_run_terminations WHERE run_id = %s",
                    (run_id,),
                )
                row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_run_termination(dict(row))

    async def enqueue_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        trigger: str,
    ) -> ResearchPipelineRunTermination:
        """
        Idempotently request termination for a run.

        - If status is terminated, do nothing.
        - If status is failed, re-queue as requested (keeping existing step timestamps).
        - If status is requested/in_progress, keep current status (no duplicate work).
        """
        query = """
            INSERT INTO research_pipeline_run_terminations (
                run_id,
                status,
                last_trigger,
                requested_at,
                updated_at
            )
            VALUES (%s, 'requested', %s, now(), now())
            ON CONFLICT (run_id) DO UPDATE
            SET
                updated_at = now(),
                last_trigger = EXCLUDED.last_trigger,
                status = CASE
                    WHEN research_pipeline_run_terminations.status = 'failed' THEN 'requested'
                    ELSE research_pipeline_run_terminations.status
                END,
                lease_owner = CASE
                    WHEN research_pipeline_run_terminations.status = 'failed' THEN NULL
                    ELSE research_pipeline_run_terminations.lease_owner
                END,
                lease_expires_at = CASE
                    WHEN research_pipeline_run_terminations.status = 'failed' THEN NULL
                    ELSE research_pipeline_run_terminations.lease_expires_at
                END
            WHERE research_pipeline_run_terminations.status <> 'terminated'
            RETURNING *
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id, trigger))
                row = await cursor.fetchone()
                await conn.commit()
        if not row:
            existing = await self.get_research_pipeline_run_termination(run_id=run_id)
            if existing is None:
                raise RuntimeError(f"Failed to enqueue termination for run {run_id}")
            return existing
        return self._row_to_run_termination(dict(row))

    async def claim_research_pipeline_run_termination(
        self,
        *,
        lease_owner: str,
        lease_seconds: int,
        stuck_seconds: int,
    ) -> Optional[ResearchPipelineRunTermination]:
        lease_delta = timedelta(seconds=lease_seconds)
        stuck_delta = timedelta(seconds=stuck_seconds)
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT run_id
                        FROM research_pipeline_run_terminations
                        WHERE status IN ('requested', 'in_progress')
                          AND (
                              status = 'requested'
                              OR lease_expires_at IS NULL
                              OR lease_expires_at < now()
                              OR updated_at < (now() - %s::interval)
                          )
                        ORDER BY requested_at ASC, run_id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE research_pipeline_run_terminations t
                    SET
                        status = 'in_progress',
                        started_at = COALESCE(t.started_at, now()),
                        updated_at = now(),
                        lease_owner = %s,
                        lease_expires_at = (now() + %s::interval)
                    FROM candidate
                    WHERE t.run_id = candidate.run_id
                    RETURNING t.*
                    """,
                    (
                        f"{int(stuck_delta.total_seconds())} seconds",
                        lease_owner,
                        f"{int(lease_delta.total_seconds())} seconds",
                    ),
                )
                row = await cursor.fetchone()
                await conn.commit()
        if not row:
            return None
        return self._row_to_run_termination(dict(row))

    async def reschedule_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        attempts: int,
        error: str,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE research_pipeline_run_terminations
                    SET
                        status = 'requested',
                        attempts = %s,
                        last_error = %s,
                        updated_at = now(),
                        lease_owner = NULL,
                        lease_expires_at = NULL
                    WHERE run_id = %s
                    """,
                    (attempts, error[:4000], run_id),
                )
                await conn.commit()

    async def mark_research_pipeline_run_termination_artifacts_uploaded(
        self,
        *,
        run_id: str,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE research_pipeline_run_terminations
                    SET
                        artifacts_uploaded_at = COALESCE(artifacts_uploaded_at, now()),
                        updated_at = now()
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                await conn.commit()

    async def mark_research_pipeline_run_termination_pod_terminated(
        self,
        *,
        run_id: str,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE research_pipeline_run_terminations
                    SET
                        pod_terminated_at = COALESCE(pod_terminated_at, now()),
                        updated_at = now()
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                await conn.commit()

    async def mark_research_pipeline_run_termination_terminated(
        self,
        *,
        run_id: str,
        attempts: int,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE research_pipeline_run_terminations
                    SET
                        status = 'terminated',
                        attempts = GREATEST(attempts, %s),
                        completed_at = COALESCE(completed_at, now()),
                        updated_at = now(),
                        lease_owner = NULL,
                        lease_expires_at = NULL
                    WHERE run_id = %s
                    """,
                    (attempts, run_id),
                )
                await conn.commit()

    async def mark_research_pipeline_run_termination_failed(
        self,
        *,
        run_id: str,
        attempts: int,
        error: str,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE research_pipeline_run_terminations
                    SET
                        status = 'failed',
                        attempts = %s,
                        last_error = %s,
                        completed_at = COALESCE(completed_at, now()),
                        updated_at = now(),
                        lease_owner = NULL,
                        lease_expires_at = NULL
                    WHERE run_id = %s
                    """,
                    (attempts, error[:4000], run_id),
                )
                await conn.commit()
