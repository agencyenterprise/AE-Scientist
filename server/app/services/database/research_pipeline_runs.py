import logging
from datetime import datetime, timezone
from typing import Any, List, NamedTuple, Optional, cast

from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Composed
from psycopg.types.json import Jsonb

from .base import ConnectionProvider

logger = logging.getLogger(__name__)

PIPELINE_RUN_STATUSES = ("pending", "initializing", "running", "failed", "completed")

# Shared SQL CTE for calculating progress across pipeline runs.
# Combines stage progress and paper generation events, then calculates overall progress
# as completed-stages-only buckets (0, 0.2, 0.4, 0.6, 0.8, 1.0).
_PROGRESS_CTE_SQL = SQL(
    """
    all_progress AS (
        SELECT run_id, stage, progress, best_metric, created_at
        FROM rp_run_stage_progress_events
        UNION ALL
        SELECT run_id, '5_paper_generation'::text, progress, NULL::text, created_at
        FROM rp_paper_generation_events
    ),
    latest_progress AS (
        SELECT DISTINCT ON (run_id)
            run_id,
            stage,
            progress,
            best_metric,
            created_at
        FROM all_progress
        ORDER BY run_id, created_at DESC
    ),
    progress_with_calculations AS (
        SELECT
            run_id,
            stage,
            best_metric,
            -- Calculate overall progress as completed-stages-only buckets.
            -- If the *current* stage is incomplete, the displayed progress reflects
            -- only the number of fully-completed stages (0, 0.2, 0.4, 0.6, 0.8, 1.0).
            CASE
                WHEN stage ~ '^[1-5]_' THEN
                    CAST(substring(stage FROM 1 FOR 1) AS numeric) * 0.2 -
                    CASE WHEN progress >= 1 THEN 0 ELSE 0.2 END
                ELSE progress
            END AS overall_progress
        FROM latest_progress
    ),
    artifact_counts AS (
        SELECT run_id, COUNT(*) as count
        FROM rp_artifacts
        GROUP BY run_id
    )
"""
)


class PodUpdateInfo(NamedTuple):
    pod_id: str
    pod_name: str
    gpu_type: str
    cost: float
    public_ip: Optional[str] = None
    pod_host_id: Optional[str] = None
    ssh_port: Optional[str] = None


class ResearchPipelineRun(NamedTuple):
    id: int
    run_id: str
    idea_id: int
    idea_version_id: int
    status: str
    initialization_status: str
    pod_id: Optional[str]
    pod_name: Optional[str]
    gpu_type: Optional[str]
    public_ip: Optional[str]
    ssh_port: Optional[str]
    pod_host_id: Optional[str]
    container_disk_gb: Optional[int]
    volume_disk_gb: Optional[int]
    error_message: Optional[str]
    cost: float
    started_running_at: Optional[datetime]
    start_deadline_at: Optional[datetime]
    last_heartbeat_at: Optional[datetime]
    heartbeat_failures: int
    last_billed_at: datetime
    webhook_token_hash: Optional[str]
    created_at: datetime
    updated_at: datetime


class ResearchPipelineRunEvent(NamedTuple):
    id: int
    run_id: str
    event_type: str
    metadata: dict
    occurred_at: datetime


class ResearchPipelineRunsMixin(ConnectionProvider):

    async def create_research_pipeline_run(
        self,
        *,
        run_id: str,
        idea_id: int,
        idea_version_id: int,
        status: str,
        start_deadline_at: Optional[datetime],
        cost: float,
        last_billed_at: datetime,
        container_disk_gb: int,
        volume_disk_gb: int,
        webhook_token_hash: str,
        started_running_at: Optional[datetime] = None,
    ) -> int:
        if status not in PIPELINE_RUN_STATUSES:
            raise ValueError(f"Invalid status '{status}'")
        now = datetime.now(timezone.utc)
        deadline = start_deadline_at
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO research_pipeline_runs (
                        run_id,
                        idea_id,
                        idea_version_id,
                        status,
                        cost,
                        start_deadline_at,
                        last_billed_at,
                        container_disk_gb,
                        volume_disk_gb,
                        webhook_token_hash,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        run_id,
                        idea_id,
                        idea_version_id,
                        status,
                        cost,
                        deadline,
                        last_billed_at,
                        container_disk_gb,
                        volume_disk_gb,
                        webhook_token_hash,
                        now,
                        now,
                    ),
                )
                new_id_row = await cursor.fetchone()
                if not new_id_row:
                    raise ValueError("Failed to create research pipeline run (missing id).")
                new_id = int(new_id_row["id"])
                await self._insert_run_event_with_cursor(
                    cursor=cursor,
                    run_id=run_id,
                    event_type="created",
                    metadata={
                        "status": status,
                        "idea_id": idea_id,
                        "idea_version_id": idea_version_id,
                        "cost": cost,
                        "start_deadline_at": deadline.isoformat() if deadline else None,
                        "started_running_at": (
                            started_running_at.isoformat() if started_running_at else None
                        ),
                    },
                    occurred_at=now,
                )

                await cursor.execute(
                    "SELECT conversation_id FROM ideas WHERE id = %s",
                    (idea_id,),
                )
                idea_row = await cursor.fetchone()
                if idea_row:
                    conversation_id = idea_row["conversation_id"]
                    await cursor.execute(
                        """
                        UPDATE conversations
                        SET status = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        ("with_research", now, conversation_id),
                    )

                await conn.commit()
                return new_id

    async def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
        initialization_status: Optional[str] = None,
        pod_update_info: Optional[PodUpdateInfo] = None,
        error_message: Optional[str] = None,
        last_heartbeat_at: Optional[datetime] = None,
        heartbeat_failures: Optional[int] = None,
        start_deadline_at: Optional[datetime] = None,
        last_billed_at: Optional[datetime] = None,
        started_running_at: Optional[datetime] = None,
    ) -> None:
        fields = []
        values: list[object] = []
        if status is not None:
            if status not in PIPELINE_RUN_STATUSES:
                raise ValueError(f"Invalid status '{status}'")
            fields.append("status = %s")
            values.append(status)
        if initialization_status is not None:
            fields.append("initialization_status = %s")
            values.append(initialization_status[:500])
        if pod_update_info is not None:
            for column, value in pod_update_info._asdict().items():
                if value is None:
                    continue
                fields.append(f"{column} = %s")
                values.append(value)
        if error_message is not None:
            fields.append("error_message = %s")
            values.append(error_message[:2000])
        if last_heartbeat_at is not None:
            fields.append("last_heartbeat_at = %s")
            values.append(last_heartbeat_at)
        if heartbeat_failures is not None:
            fields.append("heartbeat_failures = %s")
            values.append(heartbeat_failures)
        if start_deadline_at is not None:
            fields.append("start_deadline_at = %s")
            values.append(start_deadline_at)
        if last_billed_at is not None:
            fields.append("last_billed_at = %s")
            values.append(last_billed_at)
        if started_running_at is not None:
            fields.append("started_running_at = %s")
            values.append(started_running_at)
        fields.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(run_id)
        set_clause = ", ".join(fields)
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    SQL("UPDATE research_pipeline_runs SET {} WHERE run_id = %s").format(
                        SQL(set_clause)
                    ),
                    tuple(values),
                )
                await conn.commit()

    async def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: dict[str, object],
        occurred_at: datetime,
    ) -> None:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await self._insert_run_event_with_cursor(
                    cursor=cursor,
                    run_id=run_id,
                    event_type=event_type,
                    metadata=metadata,
                    occurred_at=occurred_at,
                )
                await conn.commit()

    async def list_research_pipeline_run_events(
        self, run_id: str
    ) -> list[ResearchPipelineRunEvent]:
        query = """
            SELECT id, run_id, event_type, metadata, occurred_at
            FROM research_pipeline_run_events
            WHERE run_id = %s
            ORDER BY occurred_at ASC, id ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall() or []
        return [ResearchPipelineRunEvent(**row) for row in rows]

    async def _insert_run_event_with_cursor(
        self,
        *,
        cursor: AsyncCursor[Any],
        run_id: str,
        event_type: str,
        metadata: dict[str, object],
        occurred_at: datetime,
    ) -> None:
        await cursor.execute(
            """
            INSERT INTO research_pipeline_run_events (run_id, event_type, metadata, occurred_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                run_id,
                event_type,
                Jsonb(self._normalize_metadata(metadata)),
                occurred_at,
            ),
        )

    @staticmethod
    def _normalize_metadata(metadata: dict[str, object]) -> dict[str, object]:
        def _convert(value: object) -> object:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: _convert(val) for key, val in value.items()}
            if isinstance(value, list):
                return [_convert(item) for item in value]
            return value

        return {key: _convert(value) for key, value in metadata.items()}

    async def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]:
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT * FROM research_pipeline_runs WHERE run_id = %s",
                    (run_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_run(row)

    async def list_active_research_pipeline_runs(self) -> list[ResearchPipelineRun]:
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT * FROM research_pipeline_runs
                    WHERE status IN ('pending', 'initializing', 'running')
                    """
                )
                rows = await cursor.fetchall() or []
        return [self._row_to_run(row) for row in rows]

    async def list_research_runs_for_conversation(
        self, conversation_id: int
    ) -> list[ResearchPipelineRun]:
        query = """
            SELECT r.*
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE i.conversation_id = %s
            ORDER BY r.created_at DESC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (conversation_id,))
                rows = await cursor.fetchall() or []
        return [self._row_to_run(row) for row in rows]

    async def get_run_for_conversation(
        self, *, run_id: str, conversation_id: int
    ) -> Optional[ResearchPipelineRun]:
        query = """
            SELECT r.*
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s AND i.conversation_id = %s
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id, conversation_id))
                row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_run(row)

    async def get_run_conversation_id(self, run_id: str) -> Optional[int]:
        query = """
            SELECT i.conversation_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                result = await cursor.fetchone()
        if not result:
            return None
        return int(result["conversation_id"])

    async def get_run_owner_user_id(self, run_id: str) -> Optional[int]:
        query = """
            SELECT i.created_by_user_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                result = await cursor.fetchone()
        if not result:
            return None
        return int(result["created_by_user_id"])

    async def get_run_webhook_token_hash(self, run_id: str) -> Optional[str]:
        query = """
            SELECT webhook_token_hash
            FROM research_pipeline_runs
            WHERE run_id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                result = await cursor.fetchone()
        if not result:
            return None
        return result.get("webhook_token_hash")

    async def get_run_idea_data(
        self, run_id: str, conn: Optional[AsyncConnection[Any]] = None
    ) -> Optional[dict]:
        """
        Get idea data for a research run.

        Args:
            run_id: Research run ID
            conn: Optional database connection (for use within existing transaction)

        Returns a dict with:
        - idea_id: The idea ID
        - conversation_id: The conversation ID
        - title: The idea title from idea_versions
        - idea_markdown: The idea markdown content from idea_versions

        Returns None if the run doesn't exist.
        """
        query = """
            SELECT
                rpr.idea_id,
                i.conversation_id,
                iv.title,
                iv.idea_markdown
            FROM research_pipeline_runs rpr
            JOIN ideas i ON i.id = rpr.idea_id
            JOIN idea_versions iv ON iv.id = rpr.idea_version_id
            WHERE rpr.run_id = %s
        """
        if conn is not None:
            # Use provided connection (within existing transaction)
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                result = await cursor.fetchone()
        else:
            # Create new connection
            async with self.aget_connection() as new_conn:
                async with new_conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(query, (run_id,))
                    result = await cursor.fetchone()
        if not result:
            return None
        return dict(result)

    def _row_to_run(self, row: dict) -> ResearchPipelineRun:
        return ResearchPipelineRun(
            id=row["id"],
            run_id=row["run_id"],
            idea_id=row["idea_id"],
            idea_version_id=row["idea_version_id"],
            status=row["status"],
            initialization_status=cast(str, row.get("initialization_status") or "pending"),
            pod_id=row.get("pod_id"),
            pod_name=row.get("pod_name"),
            gpu_type=row.get("gpu_type"),
            public_ip=row.get("public_ip"),
            ssh_port=row.get("ssh_port"),
            pod_host_id=row.get("pod_host_id"),
            container_disk_gb=row.get("container_disk_gb"),
            volume_disk_gb=row.get("volume_disk_gb"),
            error_message=row.get("error_message"),
            cost=float(row.get("cost", 0)),
            started_running_at=row.get("started_running_at"),
            start_deadline_at=row.get("start_deadline_at"),
            last_heartbeat_at=row.get("last_heartbeat_at"),
            heartbeat_failures=row.get("heartbeat_failures", 0),
            last_billed_at=row.get("last_billed_at") or row["created_at"],
            webhook_token_hash=row.get("webhook_token_hash"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_enriched_research_pipeline_run(self, run_id: str) -> Optional[dict]:
        """
        Get a single research pipeline run with enriched data from related tables.

        Returns a dict with the same fields as list_all_research_pipeline_runs,
        or None if not found.
        """
        query = SQL(
            "WITH {progress_cte}"
            """
            SELECT
                r.run_id,
                r.status,
                r.initialization_status,
                r.gpu_type,
                r.error_message,
                r.cost,
                r.created_at,
                r.updated_at,
                iv.title,
                iv.idea_markdown,
                u.name AS created_by_name,
                u.id AS created_by_user_id,
                pc.stage AS current_stage,
                pc.overall_progress AS progress,
                pc.best_metric,
                COALESCE(ac.count, 0) AS artifacts_count,
                i.conversation_id,
                c.url AS conversation_url,
                c.parent_run_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            LEFT JOIN conversations c ON i.conversation_id = c.id
            LEFT JOIN progress_with_calculations pc ON r.run_id = pc.run_id
            LEFT JOIN artifact_counts ac ON r.run_id = ac.run_id
            WHERE r.run_id = %s
        """
        ).format(progress_cte=_PROGRESS_CTE_SQL)
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

    async def list_all_research_pipeline_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> tuple[list[dict], int]:
        """
        List all research pipeline runs with enriched data from related tables.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            search: Search term to filter by run_id, idea_title, idea_hypothesis, or created_by_name
            status: Filter by status (pending, running, completed, failed)
            user_id: Filter by creator user ID

        Returns a tuple of (list of run dicts, total count).
        Each dict contains:
        - run_id, status, gpu_type, cost, error_message, created_at, updated_at
        - idea_title, idea_hypothesis from idea_versions
        - created_by_name from users
        - current_stage from latest stage/paper generation event (stages 1-5)
        - progress as overall pipeline progress (0.0-1.0, calculated based on stage)
        - best_metric from latest rp_run_stage_progress_events
        - artifacts_count from rp_artifacts
        - conversation_id from ideas
        """
        # Build WHERE clauses
        where_clauses: List[Composable] = []
        params: List[object] = []

        if search:
            where_clauses.append(
                SQL(
                    """
                    (r.run_id ILIKE %s
                    OR iv.title ILIKE %s
                    OR u.name ILIKE %s)
                """
                )
            )
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if status:
            where_clauses.append(SQL("r.status = %s"))
            params.append(status)

        if user_id:
            where_clauses.append(SQL("i.created_by_user_id = %s"))
            params.append(user_id)

        where_clause_sql: Composed = cast(Composed, SQL(""))
        if where_clauses:
            composed_clauses = SQL(" AND ").join(where_clauses)
            where_clause_sql = SQL(" WHERE ") + composed_clauses

        query = SQL(
            "WITH {progress_cte}"
            """
            SELECT
                r.run_id,
                r.status,
                r.initialization_status,
                r.gpu_type,
                r.cost,
                r.error_message,
                r.created_at,
                r.updated_at,
                iv.title,
                iv.idea_markdown,
                u.name AS created_by_name,
                u.id AS created_by_user_id,
                pc.stage AS current_stage,
                pc.overall_progress AS progress,
                pc.best_metric,
                COALESCE(ac.count, 0) AS artifacts_count,
                i.conversation_id,
                c.url AS conversation_url,
                c.parent_run_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            LEFT JOIN conversations c ON i.conversation_id = c.id
            LEFT JOIN progress_with_calculations pc ON r.run_id = pc.run_id
            LEFT JOIN artifact_counts ac ON r.run_id = ac.run_id
            {where_clause}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
        """
        ).format(progress_cte=_PROGRESS_CTE_SQL, where_clause=where_clause_sql)

        count_query = SQL(
            """
            SELECT COUNT(*)
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            {where_clause}
        """
        ).format(where_clause=where_clause_sql)

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(count_query, params)
                total_row = await cursor.fetchone()
                total = int(total_row["count"]) if total_row else 0

                await cursor.execute(query, params + [limit, offset])
                rows = await cursor.fetchall() or []

        return [dict(row) for row in rows], total
