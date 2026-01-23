"""
Best-effort event persistence via webhooks.

Designed to be fork-safe: worker processes simply enqueue events while a single
writer thread in the launcher process performs webhook publishes.
"""

import json
import logging
import multiprocessing
import multiprocessing.queues  # noqa: F401  # Ensure multiprocessing.queues is imported
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast

import requests
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
        "token_usage": "/token-usage",
        "figure_reviews": "/figure-reviews",
    }
    _RUN_STARTED_PATH = "/run-started"
    _RUN_FINISHED_PATH = "/run-finished"
    _INITIALIZATION_PROGRESS_PATH = "/initialization-progress"
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
        logger.info("Publishing run started event for run_id=%s", self._run_id)
        return self._post(path=self._RUN_STARTED_PATH, payload={"run_id": self._run_id})

    def publish_initialization_progress(self, *, message: str) -> Future[None]:
        payload = {
            "run_id": self._run_id,
            "message": message,
        }
        return self._post(path=self._INITIALIZATION_PROGRESS_PATH, payload=payload)

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


class EventPersistenceManager:
    """Owns the background worker that dispatches events via webhooks."""

    def __init__(
        self,
        *,
        run_id: str,
        webhook_client: WebhookClient,
        queue_maxsize: int = 1024,
    ) -> None:
        self._run_id = run_id
        self._webhook_client = webhook_client
        ctx = multiprocessing.get_context("spawn")
        # Use a multiprocessing.Manager-backed queue so spawned worker processes can
        # publish events safely without requiring queue inheritance.
        self._manager = ctx.Manager()
        self._queue = cast(
            multiprocessing.queues.Queue[PersistableEvent | None],
            self._manager.Queue(maxsize=queue_maxsize),
        )
        self._stop_sentinel: Optional[PersistableEvent] = None
        self._thread = threading.Thread(
            target=self._drain_queue,
            name="EventWebhookPublisher",
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
                self._publish_event(event=item)
            except requests.RequestException:
                logger.exception("Failed to publish event via webhook; dropping and continuing.")

    def _publish_event(self, *, event: PersistableEvent) -> None:
        """Publish event via webhook."""
        self._webhook_client.publish(kind=event.kind, payload=event.data)


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
