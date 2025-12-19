import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, NamedTuple, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import cursor as PsycopgCursor

from .base import ConnectionProvider

logger = logging.getLogger(__name__)

PIPELINE_RUN_STATUSES = ("pending", "running", "failed", "completed")


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
    pod_id: Optional[str]
    pod_name: Optional[str]
    gpu_type: Optional[str]
    public_ip: Optional[str]
    ssh_port: Optional[str]
    pod_host_id: Optional[str]
    error_message: Optional[str]
    cost: float
    started_running_at: Optional[datetime]
    start_deadline_at: Optional[datetime]
    last_heartbeat_at: Optional[datetime]
    heartbeat_failures: int
    last_billed_at: datetime
    created_at: datetime
    updated_at: datetime


class ResearchPipelineRunEvent(NamedTuple):
    id: int
    run_id: str
    event_type: str
    metadata: dict
    occurred_at: datetime


class ResearchPipelineRunsMixin(ConnectionProvider):
    if TYPE_CHECKING:
        # Type hint for method provided by ConversationsMixin (via DatabaseManager)
        def _update_conversation_status_with_cursor(
            self, cursor: PsycopgCursor, conversation_id: int, status: str
        ) -> None:
            """Update conversation status within existing transaction."""
            del cursor, conversation_id, status
            raise NotImplementedError

    def create_research_pipeline_run(
        self,
        *,
        run_id: str,
        idea_id: int,
        idea_version_id: int,
        status: str,
        start_deadline_at: Optional[datetime],
        cost: float,
        last_billed_at: datetime,
        started_running_at: Optional[datetime] = None,
    ) -> int:
        if status not in PIPELINE_RUN_STATUSES:
            raise ValueError(f"Invalid status '{status}'")
        now = datetime.now(timezone.utc)
        deadline = start_deadline_at
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_pipeline_runs (
                        run_id,
                        idea_id,
                        idea_version_id,
                        status,
                        cost,
                        start_deadline_at,
                        last_billed_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        now,
                        now,
                    ),
                )
                new_id_row = cursor.fetchone()
                if not new_id_row:
                    raise ValueError("Failed to create research pipeline run (missing id).")
                new_id = new_id_row[0]
                self._insert_run_event_with_cursor(
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

                # Get conversation_id from the idea and update its status to 'with_research'
                cursor.execute(
                    "SELECT conversation_id FROM ideas WHERE id = %s",
                    (idea_id,),
                )
                idea_row = cursor.fetchone()
                if idea_row:
                    conversation_id = idea_row[0]
                    # Call the helper method to update status within this transaction
                    self._update_conversation_status_with_cursor(
                        cursor=cursor,
                        conversation_id=conversation_id,
                        status="with_research",
                    )

                conn.commit()
                return int(new_id)

    def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
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
        values.append(datetime.now())
        values.append(run_id)
        set_clause = ", ".join(fields)
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE research_pipeline_runs SET {set_clause} WHERE run_id = %s",
                    tuple(values),
                )
                conn.commit()

    def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: dict[str, object],
        occurred_at: datetime,
    ) -> None:
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                self._insert_run_event_with_cursor(
                    cursor=cursor,
                    run_id=run_id,
                    event_type=event_type,
                    metadata=metadata,
                    occurred_at=occurred_at,
                )
                conn.commit()

    def list_research_pipeline_run_events(self, run_id: str) -> list[ResearchPipelineRunEvent]:
        query = """
            SELECT id, run_id, event_type, metadata, occurred_at
            FROM research_pipeline_run_events
            WHERE run_id = %s
            ORDER BY occurred_at ASC, id ASC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                rows = cursor.fetchall() or []
        return [ResearchPipelineRunEvent(**row) for row in rows]

    def _insert_run_event_with_cursor(
        self,
        *,
        cursor: PsycopgCursor,
        run_id: str,
        event_type: str,
        metadata: dict[str, object],
        occurred_at: datetime,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO research_pipeline_run_events (run_id, event_type, metadata, occurred_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                run_id,
                event_type,
                psycopg2.extras.Json(self._normalize_metadata(metadata)),
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

    def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM research_pipeline_runs WHERE run_id = %s",
                    (run_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_run(row)

    def list_active_research_pipeline_runs(self) -> list[ResearchPipelineRun]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM research_pipeline_runs
                    WHERE status IN ('pending', 'running')
                    """
                )
                rows = cursor.fetchall() or []
        return [self._row_to_run(row) for row in rows]

    def list_research_runs_for_conversation(
        self, conversation_id: int
    ) -> list[ResearchPipelineRun]:
        query = """
            SELECT r.*
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE i.conversation_id = %s
            ORDER BY r.created_at DESC
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (conversation_id,))
                rows = cursor.fetchall() or []
        return [self._row_to_run(row) for row in rows]

    def get_run_for_conversation(
        self, *, run_id: str, conversation_id: int
    ) -> Optional[ResearchPipelineRun]:
        query = """
            SELECT r.*
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s AND i.conversation_id = %s
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id, conversation_id))
                row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_run(row)

    def get_run_conversation_id(self, run_id: str) -> Optional[int]:
        query = """
            SELECT i.conversation_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (run_id,))
                result = cursor.fetchone()
        if not result:
            return None
        return int(result[0])

    def get_run_owner_user_id(self, run_id: str) -> Optional[int]:
        query = """
            SELECT i.created_by_user_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            WHERE r.run_id = %s
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (run_id,))
                result = cursor.fetchone()
        if not result:
            return None
        return int(result[0])

    def _row_to_run(self, row: dict) -> ResearchPipelineRun:
        return ResearchPipelineRun(
            id=row["id"],
            run_id=row["run_id"],
            idea_id=row["idea_id"],
            idea_version_id=row["idea_version_id"],
            status=row["status"],
            pod_id=row.get("pod_id"),
            pod_name=row.get("pod_name"),
            gpu_type=row.get("gpu_type"),
            public_ip=row.get("public_ip"),
            ssh_port=row.get("ssh_port"),
            pod_host_id=row.get("pod_host_id"),
            error_message=row.get("error_message"),
            cost=float(row.get("cost", 0)),
            started_running_at=row.get("started_running_at"),
            start_deadline_at=row.get("start_deadline_at"),
            last_heartbeat_at=row.get("last_heartbeat_at"),
            heartbeat_failures=row.get("heartbeat_failures", 0),
            last_billed_at=row.get("last_billed_at") or row["created_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_enriched_research_pipeline_run(self, run_id: str) -> Optional[dict]:
        """
        Get a single research pipeline run with enriched data from related tables.

        Returns a dict with the same fields as list_all_research_pipeline_runs,
        or None if not found.
        """
        query = """
            WITH latest_stage_progress AS (
                SELECT DISTINCT ON (run_id)
                    run_id,
                    stage,
                    progress,
                    best_metric,
                    created_at
                FROM rp_run_stage_progress_events
                ORDER BY run_id, created_at DESC
            ),
            latest_paper_progress AS (
                SELECT DISTINCT ON (run_id)
                    run_id,
                    '5_paper_generation' AS stage,
                    progress,
                    NULL::text AS best_metric,
                    created_at
                FROM rp_paper_generation_events
                ORDER BY run_id, created_at DESC
            ),
            latest_progress AS (
                SELECT
                    COALESCE(pp.run_id, sp.run_id) AS run_id,
                    COALESCE(pp.stage, sp.stage) AS stage,
                    sp.best_metric,
                    -- Calculate overall progress as completed-stages-only buckets.
                    -- If the *current* stage is incomplete, the displayed progress reflects
                    -- only the number of fully-completed stages (0, 0.2, 0.4, 0.6, 0.8, 1.0).
                    CASE
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '1_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.2 ELSE 0.0 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '2_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.4 ELSE 0.2 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '3_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.6 ELSE 0.4 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '4_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.8 ELSE 0.6 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '5_%%' THEN
                            CASE WHEN COALESCE(pp.progress, 0) >= 1 THEN 1.0 ELSE 0.8 END
                        ELSE COALESCE(pp.progress, sp.progress)
                    END AS overall_progress
                FROM latest_stage_progress sp
                FULL OUTER JOIN latest_paper_progress pp ON sp.run_id = pp.run_id
            ),
            artifact_counts AS (
                SELECT run_id, COUNT(*) as count
                FROM rp_artifacts
                GROUP BY run_id
            )
            SELECT
                r.run_id,
                r.status,
                r.gpu_type,
                r.error_message,
                r.cost,
                r.created_at,
                r.updated_at,
                iv.title AS idea_title,
                iv.short_hypothesis AS idea_hypothesis,
                u.name AS created_by_name,
                u.id AS created_by_user_id,
                lp.stage AS current_stage,
                lp.overall_progress AS progress,
                lp.best_metric,
                COALESCE(ac.count, 0) AS artifacts_count,
                i.conversation_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            LEFT JOIN latest_progress lp ON r.run_id = lp.run_id
            LEFT JOIN artifact_counts ac ON r.run_id = ac.run_id
            WHERE r.run_id = %s
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def list_all_research_pipeline_runs(
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
        where_clauses: List[str] = []
        params: List[object] = []

        if search:
            where_clauses.append(
                """
                (r.run_id ILIKE %s
                OR iv.title ILIKE %s
                OR iv.short_hypothesis ILIKE %s
                OR u.name ILIKE %s)
            """
            )
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        if status:
            where_clauses.append("r.status = %s")
            params.append(status)

        if user_id:
            where_clauses.append("i.created_by_user_id = %s")
            params.append(user_id)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            WITH latest_stage_progress AS (
                SELECT DISTINCT ON (run_id)
                    run_id,
                    stage,
                    progress,
                    best_metric,
                    created_at
                FROM rp_run_stage_progress_events
                ORDER BY run_id, created_at DESC
            ),
            latest_paper_progress AS (
                SELECT DISTINCT ON (run_id)
                    run_id,
                    '5_paper_generation' AS stage,
                    progress,
                    NULL::text AS best_metric,
                    created_at
                FROM rp_paper_generation_events
                ORDER BY run_id, created_at DESC
            ),
            latest_progress AS (
                SELECT
                    COALESCE(pp.run_id, sp.run_id) AS run_id,
                    COALESCE(pp.stage, sp.stage) AS stage,
                    sp.best_metric,
                    -- Calculate overall progress as completed-stages-only buckets.
                    -- If the *current* stage is incomplete, the displayed progress reflects
                    -- only the number of fully-completed stages (0, 0.2, 0.4, 0.6, 0.8, 1.0).
                    CASE
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '1_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.2 ELSE 0.0 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '2_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.4 ELSE 0.2 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '3_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.6 ELSE 0.4 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '4_%%' THEN
                            CASE WHEN COALESCE(sp.progress, 0) >= 1 THEN 0.8 ELSE 0.6 END
                        WHEN COALESCE(pp.stage, sp.stage) LIKE '5_%%' THEN
                            CASE WHEN COALESCE(pp.progress, 0) >= 1 THEN 1.0 ELSE 0.8 END
                        ELSE COALESCE(pp.progress, sp.progress)
                    END AS overall_progress
                FROM latest_stage_progress sp
                FULL OUTER JOIN latest_paper_progress pp ON sp.run_id = pp.run_id
            ),
            artifact_counts AS (
                SELECT run_id, COUNT(*) as count
                FROM rp_artifacts
                GROUP BY run_id
            )
            SELECT
                r.run_id,
                r.status,
                r.gpu_type,
                r.cost,
                r.error_message,
                r.created_at,
                r.updated_at,
                iv.title AS idea_title,
                iv.short_hypothesis AS idea_hypothesis,
                u.name AS created_by_name,
                u.id AS created_by_user_id,
                lp.stage AS current_stage,
                lp.overall_progress AS progress,
                lp.best_metric,
                COALESCE(ac.count, 0) AS artifacts_count,
                i.conversation_id
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            LEFT JOIN latest_progress lp ON r.run_id = lp.run_id
            LEFT JOIN artifact_counts ac ON r.run_id = ac.run_id
            {where_sql}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
        """

        # Count query with same filters
        count_query = f"""
            SELECT COUNT(*)
            FROM research_pipeline_runs r
            JOIN ideas i ON r.idea_id = i.id
            JOIN idea_versions iv ON r.idea_version_id = iv.id
            JOIN users u ON i.created_by_user_id = u.id
            {where_sql}
        """

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(count_query, params)
                total_row = cursor.fetchone()
                total = int(total_row["count"]) if total_row else 0

                cursor.execute(query, params + [limit, offset])
                rows = cursor.fetchall() or []

        return [dict(row) for row in rows], total
