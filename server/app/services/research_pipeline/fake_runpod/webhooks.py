import logging

from pydantic import BaseModel
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    WebhookClient,
)

logger = logging.getLogger(__name__)


class FakeRunPodWebhookPublisher:
    """Wrapper around WebhookClient with friendly helpers."""

    def __init__(self, *, client: WebhookClient | None, run_id: str) -> None:
        self._client = client
        self._run_id = run_id

    def _publish(self, kind: str, payload: BaseModel) -> None:
        if not self._client:
            logger.debug(
                "[FakeRunner %s] Skipping webhook publish (kind=%s) because client missing.",
                self._run_id[:8],
                kind,
            )
            return
        self._client.publish(kind=kind, payload=payload)

    def publish_running_code(self, payload: BaseModel) -> None:
        self._publish("running_code", payload)

    def publish_run_log(self, payload: BaseModel) -> None:
        self._publish("run_log", payload)

    def publish_run_completed(self, payload: BaseModel) -> None:
        self._publish("run_completed", payload)

    def publish_stage_skip_window(self, payload: BaseModel) -> None:
        self._publish("stage_skip_window", payload)

    def publish_tree_viz_stored(self, payload: BaseModel) -> None:
        self._publish("tree_viz_stored", payload)

    def publish_review_completed(self, payload: BaseModel) -> None:
        self._publish("review_completed", payload)

    def publish_figure_reviews(self, payload: BaseModel) -> None:
        self._publish("figure_reviews", payload)

    def publish_token_usage(self, payload: BaseModel) -> None:
        self._publish("token_usage", payload)
