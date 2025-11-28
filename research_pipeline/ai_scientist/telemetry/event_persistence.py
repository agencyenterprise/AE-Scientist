"""
Best-effort event persistence into Postgres.

Designed to be fork-safe: worker processes simply enqueue events while a single
writer thread in the launcher process performs the inserts.
"""

# pylint: disable=broad-except


import json
import logging
import multiprocessing
import multiprocessing.queues  # noqa: F401  # Ensure multiprocessing.queues is imported
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
import psycopg2.extras
import requests
from psycopg2.extensions import connection as PGConnection

from ai_scientist.treesearch.events import BaseEvent, EventKind, PersistenceRecord

logger = logging.getLogger("ai-scientist.telemetry")


@dataclass(frozen=True)
class PersistableEvent:
    kind: EventKind
    data: dict[str, Any]


class WebhookClient:
    """Simple HTTP publisher for forwarding telemetry events to the server."""

    _EVENT_PATHS: dict[EventKind, str] = {
        "run_stage_progress": "/stage-progress",
        "run_log": "",
        "experiment_node_completed": "/experiment-node-completed",
    }
    _RUN_STARTED_PATH = "/run-started"
    _RUN_FINISHED_PATH = "/run-finished"
    _HEARTBEAT_PATH = "/heartbeat"

    def __init__(self, *, base_url: str, token: str, run_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._run_id = run_id

    def _post(self, *, path: str, payload: dict[str, Any]) -> None:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception(
                "Failed to publish telemetry webhook: url=%s auth=%s payload=%s",
                url,
                headers.get("Authorization"),
                payload,
            )

    def publish(self, *, kind: EventKind, payload: dict[str, Any]) -> None:
        if kind == "run_log":
            return
        endpoint = self._EVENT_PATHS.get(kind)
        if not endpoint:
            logger.debug("No webhook endpoint configured for kind=%s", kind)
            return
        body = {"run_id": self._run_id, "event": payload}
        self._post(path=endpoint, payload=body)

    def publish_run_started(self) -> None:
        self._post(path=self._RUN_STARTED_PATH, payload={"run_id": self._run_id})

    def publish_run_finished(self, *, success: bool, message: Optional[str] = None) -> None:
        payload: dict[str, Any] = {"run_id": self._run_id, "success": success}
        if message:
            payload["message"] = message
        self._post(path=self._RUN_FINISHED_PATH, payload=payload)

    def publish_heartbeat(self) -> None:
        self._post(path=self._HEARTBEAT_PATH, payload={"run_id": self._run_id})


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
        try:
            self._queue.close()
        except OSError:
            pass
        if self._manager is not None:
            self._manager.shutdown()

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
            else:
                self._insert_node_completed(connection=connection, payload=event.data)
        if self._webhook_client is not None:
            self._webhook_client.publish(kind=event.kind, payload=event.data)

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

    def _insert_node_completed(
        self, *, connection: psycopg2.extensions.connection, payload: dict[str, Any]
    ) -> None:
        summary = payload.get("summary") or {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rp_experiment_node_completed_events (
                    run_id,
                    stage,
                    node_id,
                    summary
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    payload.get("stage"),
                    payload.get("node_id"),
                    psycopg2.extras.Json(summary),
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
        if kind == "experiment_node_completed":
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
