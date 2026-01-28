"""
Persist tree visualization payloads from the research pipeline.
"""

import logging
from dataclasses import dataclass
from typing import Any

from ai_scientist.api_types import TreeVizStoredEvent
from ai_scientist.telemetry.event_persistence import WebhookClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TreeVizStore:
    webhook_url: str | None = None
    webhook_token: str | None = None
    run_id: str | None = None

    def _get_webhook_client(self) -> WebhookClient | None:
        """Create webhook client if configured."""
        if self.webhook_url and self.webhook_token and self.run_id:
            return WebhookClient(
                base_url=self.webhook_url,
                token=self.webhook_token,
                run_id=self.run_id,
            )
        return None

    def upsert(
        self,
        *,
        run_id: str,
        stage_id: str,
        viz: dict[str, Any],
        version: int,
    ) -> None:
        """
        Publish tree visualization payload via webhook.

        Database persistence is handled by the server webhook handler.
        """
        # Publish webhook event using WebhookClient if configured
        webhook_client = self._get_webhook_client()
        if webhook_client is not None:
            try:
                webhook_client.publish(
                    kind="tree_viz_stored",
                    payload=TreeVizStoredEvent(
                        stage_id=stage_id,
                        version=version,
                        viz=viz,
                    ),
                )
                logger.info(
                    "Published tree_viz_stored webhook: run=%s stage=%s",
                    run_id,
                    stage_id,
                )
            except Exception:
                logger.exception(
                    "Failed to publish tree_viz_stored webhook for run=%s stage=%s",
                    run_id,
                    stage_id,
                )
                raise
        else:
            logger.warning(
                "No webhook client configured for tree viz storage: run=%s stage=%s",
                run_id,
                stage_id,
            )
