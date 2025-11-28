import logging
import os
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

PIPELINE_RUN_STATUSES = ("pending", "running", "failed", "completed")


def _startup_grace_seconds() -> int:
    value = os.environ.get("PIPELINE_MONITOR_STARTUP_GRACE_SECONDS")
    if not value:
        raise RuntimeError(
            "PIPELINE_MONITOR_STARTUP_GRACE_SECONDS is required to create pipeline runs."
        )
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            "PIPELINE_MONITOR_STARTUP_GRACE_SECONDS must be an integer number of seconds."
        ) from exc


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
    start_deadline_at: Optional[datetime]
    last_heartbeat_at: Optional[datetime]
    heartbeat_failures: int
    created_at: datetime
    updated_at: datetime


class ResearchPipelineRunsMixin:
    def create_research_pipeline_run(
        self,
        *,
        run_id: str,
        idea_id: int,
        idea_version_id: int,
        status: str = "pending",
        start_deadline_at: Optional[datetime] = None,
    ) -> int:
        if status not in PIPELINE_RUN_STATUSES:
            raise ValueError(f"Invalid status '{status}'")
        now = datetime.now()
        deadline = start_deadline_at or (now + timedelta(seconds=_startup_grace_seconds()))
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_pipeline_runs (
                        run_id,
                        idea_id,
                        idea_version_id,
                        status,
                        start_deadline_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, idea_id, idea_version_id, status, deadline, now, now),
                )
                new_id = cursor.fetchone()[0]
                conn.commit()
                return int(new_id)

    def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
        pod_info: Optional[dict[str, Optional[str]]] = None,
        error_message: Optional[str] = None,
        last_heartbeat_at: Optional[datetime] = None,
        heartbeat_failures: Optional[int] = None,
        start_deadline_at: Optional[datetime] = None,
    ) -> None:
        fields = []
        values: list[object] = []
        if status is not None:
            if status not in PIPELINE_RUN_STATUSES:
                raise ValueError(f"Invalid status '{status}'")
            fields.append("status = %s")
            values.append(status)
        if pod_info is not None:
            for column in (
                "pod_id",
                "pod_name",
                "gpu_type",
                "public_ip",
                "ssh_port",
                "pod_host_id",
            ):
                if column in pod_info:
                    fields.append(f"{column} = %s")
                    values.append(pod_info[column])
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
        fields.append("updated_at = %s")
        values.append(datetime.now())
        values.append(run_id)
        set_clause = ", ".join(fields)
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE research_pipeline_runs SET {set_clause} WHERE run_id = %s",
                    tuple(values),
                )
                conn.commit()

    def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]:
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM research_pipeline_runs WHERE run_id = %s",
                    (run_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
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
                    start_deadline_at=row.get("start_deadline_at"),
                    last_heartbeat_at=row.get("last_heartbeat_at"),
                    heartbeat_failures=row.get("heartbeat_failures", 0),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

    def list_active_research_pipeline_runs(self) -> list[ResearchPipelineRun]:
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM research_pipeline_runs
                    WHERE status IN ('pending', 'running')
                    """
                )
                rows = cursor.fetchall() or []
        return [
            ResearchPipelineRun(
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
                start_deadline_at=row.get("start_deadline_at"),
                last_heartbeat_at=row.get("last_heartbeat_at"),
                heartbeat_failures=row.get("heartbeat_failures", 0),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
