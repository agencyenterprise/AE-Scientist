"""Internal token usage tracking for paper review.

This module provides internal tracking that accumulates usage during a review.
The accumulated usage is returned alongside the review result.
"""

import logging
from datetime import datetime
from typing import Any, NamedTuple, cast
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

logger = logging.getLogger(__name__)


class TokenUsageSummary(NamedTuple):
    """Aggregated token usage across all LLM calls."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class TokenUsageDetail(NamedTuple):
    """Token usage for a single LLM call."""

    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    created_at: datetime


class TokenUsage:
    """Accumulated token usage from LLM calls."""

    def __init__(self) -> None:
        self._usages: list[TokenUsageDetail] = []

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
        logger.debug(
            "TokenUsage - add - model=%s, input_tokens=%d, cached_input_tokens=%d, output_tokens=%d",
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        )
        self._usages.append(
            TokenUsageDetail(
                model=model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                created_at=datetime.now(),
            )
        )

    def get_total(self) -> TokenUsageSummary:
        """Get total token usage across all calls."""
        return TokenUsageSummary(
            input_tokens=sum(u.input_tokens for u in self._usages),
            cached_input_tokens=sum(u.cached_input_tokens for u in self._usages),
            output_tokens=sum(u.output_tokens for u in self._usages),
        )

    def get_detailed(self) -> list[TokenUsageDetail]:
        """Get detailed usage records."""
        return list(self._usages)

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Combine two TokenUsage instances by extending usage records.

        Args:
            other: Another TokenUsage instance to combine with

        Returns:
            A new TokenUsage instance containing records from both
        """
        result = TokenUsage()
        result._usages.extend(self._usages)
        result._usages.extend(other._usages)
        return result

    def __iadd__(self, other: "TokenUsage") -> "TokenUsage":
        """In-place addition - extends this instance's usage records.

        Args:
            other: Another TokenUsage instance to add records from

        Returns:
            Self with extended records
        """
        self._usages.extend(other._usages)
        return self


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
        usage: TokenUsage,
    ) -> None:
        """Initialize the callback handler.

        Args:
            model: Model string in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
            usage: Optional TokenUsage accumulator to use
        """
        self.model = model
        self.usage = usage
        logger.debug("TokenUsageCallbackHandler - model=%s", model)

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
                logger.warning(
                    "LangChain response has no generations - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            generation = response.generations[0]
            if not generation:
                logger.warning(
                    "LangChain response has empty generation list - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            last_generation = generation[0]
            if not last_generation:
                logger.warning(
                    "LangChain generation is None - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            if not isinstance(last_generation, ChatGeneration):
                logger.warning(
                    "LangChain generation is not ChatGeneration (type=%s) - cannot track tokens (model=%s)",
                    type(last_generation).__name__,
                    self.model,
                )
                return
            message = last_generation.message
            if not isinstance(message, AIMessage):
                logger.warning(
                    "LangChain message is not AIMessage (type=%s) - cannot track tokens (model=%s)",
                    type(message).__name__,
                    self.model,
                )
                return

            usage_metadata_raw = message.usage_metadata
            if not usage_metadata_raw:
                logger.warning(
                    "LangChain AIMessage has no usage_metadata - cannot track tokens (model=%s)",
                    self.model,
                )
                return

            usage_metadata: dict[str, object] = cast(dict[str, object], usage_metadata_raw)
            input_tokens = _usage_value_to_int(value=usage_metadata.get("input_tokens"))
            cached_input_tokens = _usage_value_to_int(
                value=usage_metadata.get("cached_input_tokens")
            )
            output_tokens = _usage_value_to_int(value=usage_metadata.get("output_tokens"))

            if input_tokens == 0 and output_tokens == 0:
                logger.warning(
                    "LangChain returned zero tokens (model=%s) - possible tracking issue",
                    self.model,
                )

            logger.info(
                "LangChain token usage: input=%d, cached=%d, output=%d (model=%s)",
                input_tokens,
                cached_input_tokens,
                output_tokens,
                self.model,
            )

            self.usage.add(
                model=self.model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.warning("Token tracking failed; continuing without tracking", exc_info=True)
