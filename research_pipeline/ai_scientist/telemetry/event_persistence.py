"""
Best-effort event persistence into Postgres.

Designed to be fork-safe: worker processes simply enqueue events while a single
writer thread in the launcher process performs the inserts.
"""

import json
import logging
import multiprocessing
import multiprocessing.queues  # noqa: F401  # Ensure multiprocessing.queues is imported
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional, cast
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
import psycopg2.extras
import requests
from psycopg2.extensions import connection as PGConnection
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ai_scientist.treesearch.events import BaseEvent, EventKind, PersistenceRecord

# pylint: disable=broad-except


logger = logging.getLogger("ai-scientist.telemetry")


@dataclass(frozen=True)
class PersistableEvent:
    kind: EventKind
    data: dict[str, Any]


class WebhookClient:
    """Simple HTTP publisher for forwarding telemetry events to the server."""

    _EVENT_PATHS: dict[EventKind, str] = {
        "run_stage_progress": "/stage-progress",
        "run_log": "/run-log",
        # Sub-stage completion events are also forwarded to the web server.
        "substage_completed": "/substage-completed",
        "substage_summary": "/substage-summary",
        "paper_generation_progress": "/paper-generation-progress",
        "best_node_selection": "/best-node-selection",
        "tree_viz_stored": "/tree-viz-stored",
        "running_code": "/running-code",
        "run_completed": "/run-completed",
        "stage_skip_window": "/stage-skip-window",
        "artifact_uploaded": "/artifact-uploaded",
        "review_completed": "/review-completed",
        "codex_event": "/codex-event",
    }
    _RUN_STARTED_PATH = "/run-started"
    _RUN_FINISHED_PATH = "/run-finished"
    _HEARTBEAT_PATH = "/heartbeat"
    _HW_STATS_PATH = "/hw-stats"
    _GPU_SHORTAGE_PATH = "/gpu-shortage"

    def __init__(self, *, base_url: str, token: str, run_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._run_id = run_id

    def _post(self, *, path: str, payload: dict[str, Any]) -> Future[None]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        future: Future[None] = Future()
        thread = threading.Thread(
            target=self._post_async,
            kwargs={
                "url": url,
                "headers": headers,
                "payload": payload,
                "future": future,
            },
            name=f"WebhookPost:{path}",
            daemon=True,
        )
        thread.start()
        return future

    def _post_async(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        future: Future[None],
    ) -> None:
        try:
            self._post_with_retry(url=url, headers=headers, payload=payload)
        except Exception as exc:
            logger.exception(
                "Failed to publish telemetry webhook after retries: url=%s auth=%s payload=%s",
                url,
                headers.get("Authorization"),
                payload,
            )
            if not future.done():
                future.set_exception(exception=exc)
        else:
            if not future.done():
                future.set_result(result=None)

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    def _post_with_retry(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=1200,  # 20 minutes
        )
        response.raise_for_status()

    def publish(self, *, kind: EventKind, payload: dict[str, Any]) -> Optional[Future[None]]:
        endpoint = self._EVENT_PATHS.get(kind)
        if not endpoint:
            logger.debug("No webhook endpoint configured for kind=%s", kind)
            return None
        body = {"run_id": self._run_id, "event": payload}
        return self._post(path=endpoint, payload=body)

    def publish_run_started(self) -> Future[None]:
        return self._post(path=self._RUN_STARTED_PATH, payload={"run_id": self._run_id})

    def publish_run_finished(
        self,
        *,
        success: bool,
        message: Optional[str] = None,
    ) -> Future[None]:
        payload: dict[str, Any] = {"run_id": self._run_id, "success": success}
        if message:
            payload["message"] = message
        return self._post(path=self._RUN_FINISHED_PATH, payload=payload)

    def publish_heartbeat(self) -> Future[None]:
        payload = {
            "run_id": self._run_id,
        }
        return self._post(path=self._HEARTBEAT_PATH, payload=payload)

    def publish_hw_stats(self, *, partitions: list[dict[str, int | str]]) -> Optional[Future[None]]:
        if not partitions:
            return None
        payload = {
            "run_id": self._run_id,
            "partitions": partitions,
        }
        return self._post(path=self._HW_STATS_PATH, payload=payload)

    def publish_gpu_shortage(
        self,
        *,
        required_gpus: int,
        available_gpus: int,
        message: Optional[str] = None,
    ) -> Future[None]:
        payload: dict[str, Any] = {
            "run_id": self._run_id,
            "required_gpus": required_gpus,
            "available_gpus": available_gpus,
        }
        if message:
            payload["message"] = message
        return self._post(path=self._GPU_SHORTAGE_PATH, payload=payload)


def _sanitize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure payload can be serialized to JSON."""
    try:
        json.dumps(data, default=str)
        return data
    except TypeError:
        sanitized_raw = json.dumps(data, default=str)
        sanitized: dict[str, Any] = json.loads(sanitized_raw)
        return sanitized


def _parse_database_url(database_url: str) -> dict[str, Any]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")
    db_name = parsed.path.lstrip("/")
    if not db_name:
        raise ValueError("Database name missing in DATABASE_URL")
    pg_config: dict[str, Any] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": db_name,
    }
    if parsed.username:
        pg_config["user"] = unquote(parsed.username)
    if parsed.password:
        pg_config["password"] = unquote(parsed.password)
    query_params = parse_qs(parsed.query)
    for key, value in query_params.items():
        if value:
            pg_config[key] = value[-1]
    return pg_config


class EventPersistenceManager:
    """Owns the background worker that dispatches events to optional sinks."""

    def __init__(
        self,
        *,
        database_url: Optional[str],
        run_id: str,
        webhook_client: Optional[WebhookClient] = None,
        queue_maxsize: int = 1024,
    ) -> None:
        self._pg_config = _parse_database_url(database_url) if database_url else None
        self._run_id = run_id
        self._webhook_client = webhook_client
        ctx = multiprocessing.get_context("spawn")
        self._manager = ctx.Manager()
        self._queue = cast(
            multiprocessing.queues.Queue[PersistableEvent | None],
            self._manager.Queue(maxsize=queue_maxsize),
        )
        self._stop_sentinel: Optional[PersistableEvent] = None
        self._thread = threading.Thread(
            target=self._drain_queue,
            name="EventPersistenceWriter",
            daemon=True,
        )
        self._started = False

    @property
    def queue(self) -> multiprocessing.queues.Queue[PersistableEvent | None]:
        return self._queue

    def start(self) -> None:
        if self._started:
            return
        self._thread.start()
        self._started = True

    def stop(self, timeout: float = 5.0) -> None:
        if not self._started:
            return
        try:
            self._queue.put(self._stop_sentinel)
            self._thread.join(timeout=timeout)
        finally:
            self._started = False
        self._close_queue()
        if self._manager is not None:
            self._manager.shutdown()

    def _close_queue(self) -> None:
        def _invoke(obj: object, method_name: str) -> bool:
            method = getattr(obj, method_name, None)
            if callable(method):
                try:
                    method()
                    return True
                except (OSError, AttributeError):
                    return False
            return False

        if not _invoke(self._queue, "close"):
            _invoke(self._queue, "_close")
        _invoke(self._queue, "cancel_join_thread")

    def _drain_queue(self) -> None:
        conn: Optional[psycopg2.extensions.connection] = None
        while True:
            try:
                item = self._queue.get()
            except (EOFError, OSError):
                break
            if item is self._stop_sentinel:
                break
            if item is None:
                continue
            try:
                if self._pg_config and conn is None:
                    conn = self._connect()
                self._persist_event(connection=conn, event=item)
            except (psycopg2.Error, RuntimeError, requests.RequestException):
                logger.exception("Failed to persist event; dropping and continuing.")
                if conn:
                    try:
                        conn.close()
                    except psycopg2.Error:
                        pass
                    conn = None
        if conn:
            try:
                conn.close()
            except psycopg2.Error:
                pass

    def _connect(self) -> PGConnection:
        if self._pg_config is None:
            raise RuntimeError("Attempted to connect without database configuration.")
        conn = cast(PGConnection, psycopg2.connect(**self._pg_config))
        conn.autocommit = True
        return conn

    def _persist_event(
        self,
        *,
        connection: Optional[psycopg2.extensions.connection],
        event: PersistableEvent,
    ) -> None:
        if self._pg_config and connection is not None:
            if event.kind == "run_stage_progress":
                self._insert_stage_progress(connection=connection, payload=event.data)
            elif event.kind == "run_log":
                self._insert_run_log(connection=connection, payload=event.data)
            elif event.kind == "substage_completed":
                self._insert_substage_completed(connection=connection, payload=event.data)
            elif event.kind == "substage_summary":
                self._insert_substage_summary(connection=connection, payload=event.data)
            elif event.kind == "paper_generation_progress":
                self._insert_paper_generation_progress(connection=connection, payload=event.data)
            elif event.kind == "best_node_selection":
                self._insert_best_node_reasoning(connection=connection, payload=event.data)
            elif event.kind == "running_code":
                self._upsert_code_execution_event(
                    connection=connection,
                    payload=event.data,
                    is_completion=False,
                )
            elif event.kind == "run_completed":
                self._upsert_code_execution_event(
                    connection=connection,
                    payload=event.data,
                    is_completion=True,
                )
            elif event.kind == "stage_skip_window":
                self._upsert_stage_skip_window(connection=connection, payload=event.data)
            elif event.kind == "codex_event":
                self._insert_codex_event(connection=connection, payload=event.data)
        if self._webhook_client is not None:
            self._webhook_client.publish(kind=event.kind, payload=event.data)

    @staticmethod
    def _coerce_timestamp(*, value: str | None) -> Optional[datetime]:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _upsert_code_execution_event(
        self,
        *,
        connection: psycopg2.extensions.connection,
        payload: dict[str, Any],
        is_completion: bool,
    ) -> None:
        execution_id = payload.get("execution_id")
        stage_name = payload.get("stage_name")
        run_type = payload.get("run_type") or "main_execution"
        code = payload.get("code")
        started_at = self._coerce_timestamp(value=payload.get("started_at"))
        completed_at = self._coerce_timestamp(value=payload.get("completed_at"))
        status = payload.get("status") if is_completion else "running"
        exec_time = payload.get("exec_time")

        upsert_code = code if not is_completion else None
        upsert_started_at = started_at if not is_completion else None
        upsert_completed_at = completed_at if is_completion else None
        upsert_exec_time = exec_time if is_completion else None

        with connection.cursor() as cursor:
            if is_completion and (upsert_code is None or upsert_started_at is None):
                cursor.execute(
                    """
                    SELECT code, started_at
                    FROM rp_code_execution_events
                    WHERE run_id = %s AND execution_id = %s AND run_type = %s
                    LIMIT 1
                    """,
                    (self._run_id, execution_id, run_type),
                )
                existing = cursor.fetchone()
                if existing is None:
                    logger.warning(
                        "Dropping completion event for run_id=%s execution_id=%s; missing prior running_code record.",
                        self._run_id,
                        execution_id,
                    )
                    return
                existing_code, existing_started_at = existing
                if upsert_code is None:
                    upsert_code = existing_code
                if upsert_started_at is None:
                    upsert_started_at = existing_started_at
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
                ON CONFLICT (run_id, execution_id, run_type)
                DO UPDATE SET
                    stage_name = COALESCE(EXCLUDED.stage_name, rp_code_execution_events.stage_name),
                    code = COALESCE(EXCLUDED.code, rp_code_execution_events.code),
                    started_at = COALESCE(EXCLUDED.started_at, rp_code_execution_events.started_at),
                    status = EXCLUDED.status,
                    completed_at = COALESCE(EXCLUDED.completed_at, rp_code_execution_events.completed_at),
                    exec_time = COALESCE(EXCLUDED.exec_time, rp_code_execution_events.exec_time),
                    updated_at = now()
                """,
                (
                    self._run_id,
                    execution_id,
                    stage_name,
                    run_type,
                    upsert_code,
                    upsert_started_at,
                    status,
                    upsert_completed_at,
                    upsert_exec_time,
                ),
            )

    def _upsert_stage_skip_window(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        stage = payload.get("stage")
        state = (payload.get("state") or "").strip().lower()
        timestamp = self._coerce_timestamp(value=payload.get("timestamp")) or datetime.now(
            timezone.utc
        )
        reason = payload.get("reason")
        if not stage:
            logger.debug("Dropping stage_skip_window event without stage name: %s", payload)
            return
        with connection.cursor() as cursor:
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
                    (timestamp, reason, self._run_id, stage),
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
                        (self._run_id, stage, timestamp, reason),
                    )
            elif state == "closed":
                cursor.execute(
                    """
                    WITH pending AS (
                        SELECT id
                        FROM rp_stage_skip_windows
                        WHERE run_id = %s AND stage = %s AND closed_at IS NULL
                        ORDER BY opened_at DESC
                        LIMIT 1
                    )
                    UPDATE rp_stage_skip_windows
                    SET closed_at = %s,
                        closed_reason = COALESCE(%s, closed_reason),
                        updated_at = now()
                    WHERE id IN (SELECT id FROM pending)
                    """,
                    (self._run_id, stage, timestamp, reason),
                )
                if cursor.rowcount == 0:
                    logger.warning(
                        "No open stage_skip_window row found to close (run_id=%s stage=%s).",
                        self._run_id,
                        stage,
                    )
            else:
                logger.warning(
                    "Unknown stage_skip_window state '%s' for run_id=%s stage=%s",
                    state,
                    self._run_id,
                    stage,
                )

    def _insert_stage_progress(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_run_stage_progress_events (
                    run_id,
                    stage,
                    iteration,
                    max_iterations,
                    progress,
                    total_nodes,
                    buggy_nodes,
                    good_nodes,
                    best_metric,
                    eta_s,
                    latest_iteration_time_s
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    payload.get("iteration"),
                    payload.get("max_iterations"),
                    payload.get("progress"),
                    payload.get("total_nodes"),
                    payload.get("buggy_nodes"),
                    payload.get("good_nodes"),
                    payload.get("best_metric"),
                    payload.get("eta_s"),
                    payload.get("latest_iteration_time_s"),
                ),
            )

    def _insert_run_log(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_run_log_events (run_id, message, level)
                VALUES (%s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("message"),
                    payload.get("level", "info"),
                ),
            )

    def _insert_codex_event(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_codex_events (
                    run_id,
                    stage,
                    node,
                    event_type,
                    event_content
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    payload.get("node"),
                    payload.get("event_type"),
                    payload.get("event_content"),
                ),
            )

    def _insert_substage_completed(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        summary = payload.get("summary") or {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_substage_completed_events (
                    run_id,
                    stage,
                    summary
                )
                VALUES (%s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    psycopg2.extras.Json(summary),
                ),
            )

    def _insert_substage_summary(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        summary = payload.get("summary") or {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_substage_summary_events (
                    run_id,
                    stage,
                    summary
                )
                VALUES (%s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    psycopg2.extras.Json(summary),
                ),
            )

    def _insert_paper_generation_progress(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        details = payload.get("details") or {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_paper_generation_events (
                    run_id,
                    step,
                    substep,
                    progress,
                    step_progress,
                    details
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("step"),
                    payload.get("substep"),
                    payload.get("progress"),
                    payload.get("step_progress"),
                    psycopg2.extras.Json(details),
                ),
            )

    def _insert_best_node_reasoning(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_best_node_reasoning_events (
                    run_id,
                    stage,
                    node_id,
                    reasoning
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    payload.get("node_id"),
                    payload.get("reasoning"),
                ),
            )


@dataclass
class EventQueueEmitter:
    """Callable event handler that logs locally and enqueues for persistence."""

    queue: Optional[multiprocessing.queues.Queue[PersistableEvent | None]]
    fallback: Callable[[BaseEvent], None]

    def __call__(self, event: BaseEvent) -> None:
        try:
            self.fallback(event)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to execute fallback event logger.")
        if self.queue is None:
            return
        record = cast(Optional[PersistenceRecord], cast(Any, event).persistence_record())
        if record is None:
            return
        kind, payload_data = record
        if kind == "substage_completed":
            payload_data = {
                **payload_data,
                "summary": _sanitize_payload(payload_data.get("summary") or {}),
            }
        try:
            self.queue.put_nowait(PersistableEvent(kind=kind, data=payload_data))
        except queue.Full:
            logger.warning("Event queue is full; dropping telemetry event.")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to enqueue telemetry event.")
