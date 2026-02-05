"""Local persistence using a queue for webhook publishing."""

import logging
import queue
import threading
from typing import Optional

from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    PersistableEvent,
    WebhookClient,
)

logger = logging.getLogger(__name__)


class LocalPersistence:
    """Queue-based persistence that publishes events via webhooks.

    Used by FakeRunner instead of database persistence.
    """

    def __init__(self, webhook_client: WebhookClient) -> None:
        self.queue: "queue.SimpleQueue[PersistableEvent | None]" = queue.SimpleQueue()
        self._webhook_client = webhook_client
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background thread that drains the queue."""
        self._thread = threading.Thread(
            target=self._drain_queue,
            name="LocalPersistenceWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread is not None:
            self.queue.put(None)  # Sentinel to wake up the thread
            self._thread.join(timeout=5)

    def _drain_queue(self) -> None:
        """Background loop that publishes events from the queue."""
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                self._webhook_client.publish(kind=item.kind, payload=item.data)
            except Exception:
                logger.exception("Failed to publish event via webhook; dropping event.")
