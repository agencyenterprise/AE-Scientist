"""Integration layer between ae-paper-review and research_pipeline.

This module provides adapters that connect the standalone ae-paper-review package
with the research_pipeline's webhook-based telemetry and event systems.
"""

import logging
import os
from pathlib import Path
from typing import Callable

from ae_paper_review import (
    ReviewProgressEvent,
    ReviewResult,
    TokenUsage,
    TokenUsageDetail,
)
from ae_paper_review import perform_review as _perform_review

from ai_scientist.api_types import TokenUsageEvent
from ai_scientist.telemetry.event_persistence import WebhookClient
from ai_scientist.treesearch.events import (
    BaseEvent,
    PaperGenerationProgressEvent,
    PaperGenerationStep,
)

logger = logging.getLogger(__name__)


def _get_webhook_client() -> WebhookClient | None:
    """Get webhook client if configured."""
    run_id = os.environ.get("RUN_ID")
    webhook_url = os.environ.get("TELEMETRY_WEBHOOK_URL")
    webhook_token = os.environ.get("TELEMETRY_WEBHOOK_TOKEN")

    if webhook_url and webhook_token and run_id:
        return WebhookClient(base_url=webhook_url, token=webhook_token, run_id=run_id)
    return None


def _publish_token_usage(
    webhook_client: WebhookClient | None,
    token_usage_detailed: list[TokenUsageDetail],
) -> None:
    """Publish token usage records to webhook if available."""
    if not webhook_client:
        return

    for usage_record in token_usage_detailed:
        try:
            webhook_client.publish(
                kind="token_usage",
                payload=TokenUsageEvent(
                    model=usage_record.model,
                    input_tokens=usage_record.input_tokens,
                    cached_input_tokens=usage_record.cached_input_tokens,
                    output_tokens=usage_record.output_tokens,
                ),
            )
        except Exception:
            logger.exception("Failed to publish token usage webhook (non-fatal)")


def publish_token_usage(usage: TokenUsage) -> None:
    """Publish accumulated token usage to webhook if configured.

    Call this after completing VLM or LLM operations to report token usage
    to the telemetry system.

    Args:
        usage: TokenUsage accumulator containing usage records to publish
    """
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, usage.get_detailed())


def make_event_callback_adapter(
    run_id: str,
    callback: Callable[[BaseEvent], None],
) -> Callable[[ReviewProgressEvent], None]:
    """Create an adapter that converts ReviewProgressEvent to PaperGenerationProgressEvent.

    The review library emits granular steps (init, ensemble, meta_review, reflection)
    which are all part of the paper_review stage. This adapter maps them to the
    paper_review step and includes the original step name in the substep field.

    Args:
        run_id: The run ID for the event
        callback: The original callback that expects BaseEvent

    Returns:
        Adapted callback that accepts ReviewProgressEvent
    """

    def wrapper(event: ReviewProgressEvent) -> None:
        # All review steps (init, ensemble, meta_review, reflection) map to paper_review
        # Include the original step in substep for more detail
        substep = f"{event.step}: {event.substep}" if event.substep else event.step
        callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step=PaperGenerationStep.paper_review,
                substep=substep,
                progress=event.progress,
                step_progress=event.step_progress,
            )
        )

    return wrapper


def perform_review(
    pdf_path: Path,
    *,
    model: str,
    temperature: float,
    event_callback: Callable[[BaseEvent], None],
    run_id: str,
    num_reflections: int,
    num_reviews_ensemble: int,
) -> ReviewResult:
    """Perform paper review with research_pipeline integration.

    This wraps the ae-paper-review perform_review function with:
    - Automatic webhook-based token usage publishing when telemetry is configured
    - Event callback adaptation for PaperGenerationProgressEvent

    Args:
        pdf_path: Path to the PDF file to review
        model: LLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        event_callback: Callback for progress events (expects BaseEvent)
        run_id: Run ID for events
        num_reflections: Number of reflection rounds
        num_reviews_ensemble: Number of ensemble reviews

    Returns:
        ReviewResult containing review and token usage
    """
    # Adapt event callback for the package's ReviewProgressEvent type
    adapted_callback = make_event_callback_adapter(run_id, event_callback)

    # Perform the review (returns ReviewResult with token usage)
    result = _perform_review(
        pdf_path=pdf_path,
        model=model,
        temperature=temperature,
        event_callback=adapted_callback,
        num_reflections=num_reflections,
        num_fs_examples=1,
        num_reviews_ensemble=num_reviews_ensemble,
    )

    # Publish token usage to webhook if configured
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, result.token_usage_detailed)

    return result
