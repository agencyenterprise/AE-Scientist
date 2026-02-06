"""
Best-effort event persistence via webhooks.

Designed to be fork-safe: worker processes simply enqueue events while a single
writer thread in the launcher process performs webhook publishes.
"""

import logging
import multiprocessing
import multiprocessing.queues  # noqa: F401  # Ensure multiprocessing.queues is imported
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, cast

import requests
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ai_scientist.api_types import (
    GPUShortagePayload,
    HardwareStatsPartition,
    HardwareStatsPayload,
    InitializationProgressPayload,
    RunFinishedPayload,
)
from ai_scientist.treesearch.events import BaseEvent, EventKind, PersistenceRecord

# Batching configuration for codex events
CODEX_BATCH_SIZE = 200  # Max events per batch
CODEX_BATCH_INTERVAL_SECONDS = 30.0  # Max time to wait before flushing

# pylint: disable=broad-except


logger = logging.getLogger("ai-scientist.telemetry")


@dataclass(frozen=True)
class PersistableEvent:
    kind: EventKind
    data: BaseModel


class CodexEventItem(BaseModel):
    """Single codex event for bulk insertion (matches server schema)."""

    stage: str
    node: int
    event_type: str
    event_content: dict[str, Any]
    occurred_at: str  # ISO format timestamp


class CodexEventsBulkPayload(BaseModel):
    """Payload for bulk codex event ingestion."""

    events: List[CodexEventItem]


class WebhookClient:
    """Simple HTTP publisher for forwarding telemetry events to the server."""

    _EVENT_PATHS: dict[EventKind, str] = {
        "run_stage_progress": "/stage-progress",
        "run_log": "/run-log",
        # Sub-stage completion events are also forwarded to the web server.
        "substage_completed": "/substage-completed",
        "substage_summary": "/substage-summary",
        "paper_generation_progress": "/paper-generation-progress",
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

    def __init__(self, *, base_url: str, token: str, run_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._run_id = run_id

    def _post(self, *, path: str, payload: dict[str, Any]) -> Future[None]:
        url = f"{self._base_url}/{self._run_id}{path}"
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

    def publish(self, *, kind: EventKind, payload: BaseModel) -> Optional[Future[None]]:
        endpoint = self._EVENT_PATHS.get(kind)
        if not endpoint:
            logger.debug("No webhook endpoint configured for kind=%s", kind)
            return None
        body = {"event": payload.model_dump()}
        return self._post(path=endpoint, payload=body)

    def publish_run_started(self) -> Future[None]:
        logger.info("Publishing run started event for run_id=%s", self._run_id)
        return self._post(path="/run-started", payload={})

    def publish_initialization_progress(self, *, message: str) -> Future[None]:
        payload = InitializationProgressPayload(message=message)
        return self._post(path="/initialization-progress", payload=payload.model_dump())

    def publish_run_finished(
        self,
        *,
        success: bool,
        message: Optional[str] = None,
    ) -> Future[None]:
        payload = RunFinishedPayload(success=success, message=message)
        return self._post(path="/run-finished", payload=payload.model_dump(exclude_none=True))

    def publish_heartbeat(self) -> Future[None]:
        return self._post(path="/heartbeat", payload={})

    def publish_hw_stats(self, *, partitions: list[dict[str, int | str]]) -> Optional[Future[None]]:
        if not partitions:
            return None
        typed_partitions = [
            HardwareStatsPartition(
                partition=str(p["partition"]),
                used_bytes=int(p["used_bytes"]),
            )
            for p in partitions
        ]
        payload = HardwareStatsPayload(partitions=typed_partitions)
        return self._post(path="/hw-stats", payload=payload.model_dump())

    def publish_gpu_shortage(
        self,
        *,
        required_gpus: int,
        available_gpus: int,
        message: Optional[str] = None,
    ) -> Future[None]:
        payload = GPUShortagePayload(
            required_gpus=required_gpus,
            available_gpus=available_gpus,
            message=message,
        )
        return self._post(path="/gpu-shortage", payload=payload.model_dump(exclude_none=True))

    def publish_codex_events_bulk(self, *, events: List[CodexEventItem]) -> Optional[Future[None]]:
        """Publish multiple codex events in a single request."""
        if not events:
            return None
        payload = CodexEventsBulkPayload(events=events)
        return self._post(path="/codex-events-bulk", payload=payload.model_dump())


@dataclass
class CodexEventBuffer:
    """Buffer for batching codex events."""

    events: List[CodexEventItem] = field(default_factory=list)
    last_flush_time: float = field(default_factory=time.monotonic)

    def add(self, event: CodexEventItem) -> None:
        self.events.append(event)

    def should_flush(self) -> bool:
        if not self.events:
            return False
        if len(self.events) >= CODEX_BATCH_SIZE:
            return True
        elapsed = time.monotonic() - self.last_flush_time
        if elapsed >= CODEX_BATCH_INTERVAL_SECONDS:
            return True
        return False

    def flush(self) -> List[CodexEventItem]:
        events = self.events
        self.events = []
        self.last_flush_time = time.monotonic()
        return events


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
        self._codex_buffer = CodexEventBuffer()

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
                # Use timeout to periodically flush codex buffer even with no new events
                try:
                    item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    # No new event, but check if we need to flush codex buffer
                    self._maybe_flush_codex_buffer()
                    continue
            except (EOFError, OSError):
                break
            if item is self._stop_sentinel:
                # Flush any remaining codex events before stopping
                self._flush_codex_buffer()
                break
            if item is None:
                continue
            try:
                self._publish_event(event=item)
            except requests.RequestException:
                logger.exception("Failed to publish event via webhook; dropping and continuing.")
            # Check if codex buffer needs flushing after each event
            self._maybe_flush_codex_buffer()

    def _maybe_flush_codex_buffer(self) -> None:
        """Flush codex buffer if it meets flush criteria."""
        if self._codex_buffer.should_flush():
            self._flush_codex_buffer()

    def _flush_codex_buffer(self) -> None:
        """Flush all buffered codex events."""
        events = self._codex_buffer.flush()
        if not events:
            return
        try:
            logger.debug("Flushing %d codex events in bulk", len(events))
            self._webhook_client.publish_codex_events_bulk(events=events)
        except requests.RequestException:
            logger.exception(
                "Failed to publish %d codex events via bulk webhook; dropping.",
                len(events),
            )

    def _publish_event(self, *, event: PersistableEvent) -> None:
        """Publish event via webhook, buffering codex events for batch sending."""
        if event.kind == "codex_event":
            # Buffer codex events for batch sending
            data = event.data.model_dump()
            codex_item = CodexEventItem(
                stage=data.get("stage", ""),
                node=data.get("node", 0),
                event_type=data.get("event_type", ""),
                event_content=data,  # Store full payload as content
                occurred_at=data.get("occurred_at", ""),
            )
            self._codex_buffer.add(codex_item)
        else:
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
        kind, payload_model = record
        try:
            self.queue.put_nowait(PersistableEvent(kind=kind, data=payload_model))
        except queue.Full:
            logger.warning("Event queue is full; dropping telemetry event.")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to enqueue telemetry event.")
