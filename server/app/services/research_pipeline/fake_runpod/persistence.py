from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


class FakeRunPodPersistence:
    """DB helper for the fake RunPod server."""

    def __init__(self, *, database_url: str, run_id: str) -> None:
        self._database_url = database_url
        self._run_id = run_id

    def _connect(self) -> Connection:
        return psycopg.connect(self._database_url)

    def record_code_execution_start(
        self,
        *,
        execution_id: str,
        stage_name: str,
        code: str,
        started_at: datetime,
        run_type: str,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rp_code_execution_events (
                        run_id,
                        execution_id,
                        stage_name,
                        run_type,
                        code,
                        started_at,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
                    ON CONFLICT (run_id, execution_id, run_type)
                    DO UPDATE SET
                        stage_name = EXCLUDED.stage_name,
                        code = EXCLUDED.code,
                        started_at = EXCLUDED.started_at,
                        status = EXCLUDED.status,
                        updated_at = now()
                    """,
                    (
                        self._run_id,
                        execution_id,
                        stage_name,
                        run_type,
                        code,
                        started_at,
                        "running",
                    ),
                )

    def record_code_execution_completion(
        self,
        *,
        execution_id: str,
        stage_name: str,
        completed_at: datetime,
        exec_time: float,
        status: str,
        run_type: str,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE rp_code_execution_events
                    SET
                        status = %s,
                        completed_at = %s,
                        exec_time = %s,
                        updated_at = now()
                    WHERE run_id = %s
                      AND execution_id = %s
                      AND run_type = %s
                    """,
                    (
                        status,
                        completed_at,
                        exec_time,
                        self._run_id,
                        execution_id,
                        run_type,
                    ),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO rp_code_execution_events (
                            run_id,
                            execution_id,
                            stage_name,
                            run_type,
                            code,
                            started_at,
                            status,
                            completed_at,
                            exec_time,
                            created_at,
                            updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                        """,
                        (
                            self._run_id,
                            execution_id,
                            stage_name,
                            run_type,
                            "synthetic completion fallback",
                            completed_at,
                            status,
                            completed_at,
                            exec_time,
                        ),
                    )

    def record_stage_skip_window(
        self,
        *,
        stage_name: str,
        state: str,
        timestamp: str,
        reason: str,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if state == "opened":
                    cursor.execute(
                        """
                        UPDATE rp_stage_skip_windows
                        SET
                            opened_at = %s,
                            opened_reason = %s,
                            closed_at = NULL,
                            closed_reason = NULL,
                            updated_at = now()
                        WHERE run_id = %s
                          AND stage = %s
                        """,
                        (timestamp, reason, self._run_id, stage_name),
                    )
                    if cursor.rowcount == 0:
                        cursor.execute(
                            """
                            INSERT INTO rp_stage_skip_windows (
                                run_id,
                                stage,
                                opened_at,
                                opened_reason,
                                created_at,
                                updated_at
                            )
                            VALUES (%s, %s, %s, %s, now(), now())
                            """,
                            (self._run_id, stage_name, timestamp, reason),
                        )
                elif state == "closed":
                    cursor.execute(
                        """
                        UPDATE rp_stage_skip_windows
                        SET
                            closed_at = %s,
                            closed_reason = %s,
                            updated_at = now()
                        WHERE run_id = %s
                          AND stage = %s
                        """,
                        (timestamp, reason, self._run_id, stage_name),
                    )
                    if cursor.rowcount == 0:
                        cursor.execute(
                            """
                            INSERT INTO rp_stage_skip_windows (
                                run_id,
                                stage,
                                opened_at,
                                opened_reason,
                                closed_at,
                                closed_reason,
                                created_at,
                                updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, now(), now())
                            """,
                            (
                                self._run_id,
                                stage_name,
                                timestamp,
                                reason,
                                timestamp,
                                reason,
                            ),
                        )

    def insert_tree_viz(
        self,
        *,
        stage_id: str,
        payload: dict[str, Any],
        version: int,
    ) -> int:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rp_tree_viz (run_id, stage_id, viz, version)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (run_id, stage_id)
                    DO UPDATE SET
                        viz = EXCLUDED.viz,
                        version = EXCLUDED.version,
                        updated_at = now()
                    RETURNING id
                    """,
                    (self._run_id, stage_id, Jsonb(payload), version),
                )
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("Failed to upsert rp_tree_viz")
                tree_viz_id = int(row[0])
                cursor.execute(
                    """
                    INSERT INTO research_pipeline_run_events (run_id, event_type, metadata, occurred_at)
                    VALUES (%s, %s, %s, now())
                    """,
                    (
                        self._run_id,
                        "tree_viz_stored",
                        Jsonb(
                            {"stage_id": stage_id, "tree_viz_id": tree_viz_id, "version": version}
                        ),
                    ),
                )
                return tree_viz_id

    def insert_best_node_reasoning(self, *, stage_name: str, node_id: str, reasoning: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rp_best_node_reasoning_events (run_id, stage, node_id, reasoning)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (self._run_id, stage_name, node_id, reasoning),
                )

    def insert_substage_summary(self, *, stage_name: str, summary: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rp_substage_summary_events (run_id, stage, summary)
                    VALUES (%s, %s, %s)
                    """,
                    (self._run_id, stage_name, Jsonb(summary)),
                )
