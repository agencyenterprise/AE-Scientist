"""Research-pipeline specific token tracking functions.

This module provides token tracking that publishes via webhooks or to files,
specific to the research_pipeline's telemetry system.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from langchain.chat_models import BaseChatModel
from langchain.chat_models.base import _parse_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ai_scientist.api_types import TokenUsageEvent
from ai_scientist.telemetry.event_persistence import WebhookClient

RUN_ID = os.environ.get("RUN_ID")
WEBHOOK_URL = os.environ.get("TELEMETRY_WEBHOOK_URL")
WEBHOOK_TOKEN = os.environ.get("TELEMETRY_WEBHOOK_TOKEN")


def _get_webhook_client() -> WebhookClient | None:
    """Get webhook client if configured."""
    if WEBHOOK_URL and WEBHOOK_TOKEN and RUN_ID:
        return WebhookClient(base_url=WEBHOOK_URL, token=WEBHOOK_TOKEN, run_id=RUN_ID)
    return None


def _should_use_webhook_tracking(run_id: str | None) -> bool:
    return run_id is not None and WEBHOOK_URL is not None and WEBHOOK_TOKEN is not None


def _usage_value_to_int(*, value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    try:
        return int(cast(Any, value))
    except Exception:
        return 0


def save_cost_track(
    model: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> None:
    """Save token usage either via webhook or to file depending on environment."""
    run_id = RUN_ID
    model_name, provider = extract_model_name_and_provider(model)
    now = datetime.now()
    if _should_use_webhook_tracking(run_id):
        save_webhook_cost_track(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )
    else:
        save_file_cost_track(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            now=now,
        )


def save_webhook_cost_track(
    *,
    provider: str,
    model_name: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> None:
    """Publish token usage via webhook. Server will look up conversation_id from run_id."""
    webhook_client = _get_webhook_client()
    if webhook_client is None:
        logging.warning("Webhook client not configured; skipping token usage tracking")
        return

    try:
        webhook_client.publish(
            kind="token_usage",
            payload=TokenUsageEvent(
                provider=provider,
                model=model_name,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
            ),
        )
    except Exception:
        logging.exception("Failed to publish token usage webhook (non-fatal)")


def save_file_cost_track(
    *,
    provider: str,
    model_name: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    now: datetime,
) -> None:
    """Save token usage to a CSV file."""
    file_path = Path(os.environ.get("WORKSPACE_DIR") or "") / "cost_track.csv"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        with file_path.open(mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "provider",
                    "model_name",
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "created_at",
                ]
            )
    with file_path.open(mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                provider,
                model_name,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                now,
            ]
        )


class TrackCostCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks token costs via webhook or file."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: object,
    ) -> None:
        del run_id, parent_run_id, kwargs  # Required by interface but unused
        try:
            if not response.generations:
                return
            generation = response.generations[0]
            if not generation:
                return
            last_generation = generation[0]
            if not last_generation:
                return
            if not isinstance(last_generation, ChatGeneration):
                return
            message = last_generation.message
            if isinstance(message, AIMessage):
                model_name = self.model or message.response_metadata.get("model_name")
                if not model_name:
                    raise ValueError(
                        "Model name not found in response metadata or provided in constructor"
                    )
                usage_metadata_raw = message.usage_metadata
                usage_metadata: dict[str, object] = (
                    cast(dict[str, object], usage_metadata_raw) if usage_metadata_raw else {}
                )
                input_tokens = _usage_value_to_int(value=usage_metadata.get("input_tokens"))
                cached_input_tokens = _usage_value_to_int(
                    value=usage_metadata.get("cached_input_tokens")
                )
                output_tokens = _usage_value_to_int(value=usage_metadata.get("output_tokens"))
                save_cost_track(
                    model=model_name,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                )
        except Exception:
            logging.warning("Token tracking failed; continuing without tracking")


def extract_model_name_and_provider(model: str | BaseChatModel) -> tuple[str, str]:
    """Extract the model name and provider from a model."""
    if isinstance(model, BaseChatModel):
        model_attr = getattr(model, "model", None)
        if model_attr is None:
            model_attr = getattr(model, "model_name", None)
        if model_attr is None:
            raise ValueError(f"Model {model} has no model or model_name attribute")
        model_name = str(model_attr)
    else:
        model_name = model
    return _parse_model(model_name, None)
