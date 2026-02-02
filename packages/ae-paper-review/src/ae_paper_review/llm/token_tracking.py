"""Internal token usage tracking for paper review.

This module provides internal tracking that accumulates usage during a review.
The accumulated usage is returned alongside the review result.
"""

import logging
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

logger = logging.getLogger(__name__)


class TokenUsage:
    """Accumulated token usage from LLM calls."""

    def __init__(self) -> None:
        self.usages: list[dict[str, Any]] = []

    def add(
        self,
        *,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Add a single usage record.

        Args:
            model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
            input_tokens: Number of input tokens used
            cached_input_tokens: Number of cached input tokens
            output_tokens: Number of output tokens used
        """
        self.usages.append(
            {
                "model": model,
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "created_at": datetime.now(),
            }
        )

    def get_total(self) -> dict[str, int]:
        """Get total token usage across all calls."""
        return {
            "input_tokens": sum(u["input_tokens"] for u in self.usages),
            "cached_input_tokens": sum(u["cached_input_tokens"] for u in self.usages),
            "output_tokens": sum(u["output_tokens"] for u in self.usages),
        }

    def get_detailed(self) -> list[dict[str, Any]]:
        """Get detailed usage records."""
        return list(self.usages)


def _usage_value_to_int(*, value: object) -> int:
    """Convert a usage metadata value to an integer."""
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


class TrackCostCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that accumulates token usage."""

    def __init__(
        self,
        *,
        model: str,
        usage: TokenUsage | None = None,
    ) -> None:
        """Initialize the callback handler.

        Args:
            model: Model string in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
            usage: Optional TokenUsage accumulator to use
        """
        self.model = model
        self.usage = usage or TokenUsage()

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
                usage_metadata_raw = message.usage_metadata
                usage_metadata: dict[str, object] = (
                    cast(dict[str, object], usage_metadata_raw) if usage_metadata_raw else {}
                )
                input_tokens = _usage_value_to_int(value=usage_metadata.get("input_tokens"))
                cached_input_tokens = _usage_value_to_int(
                    value=usage_metadata.get("cached_input_tokens")
                )
                output_tokens = _usage_value_to_int(value=usage_metadata.get("output_tokens"))

                self.usage.add(
                    model=self.model,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                )
        except Exception:
            logger.warning("Token tracking failed; continuing without tracking", exc_info=True)
