"""Internal token usage tracking for paper review.

This module provides internal tracking that accumulates usage during a review.
The accumulated usage is returned alongside the review result.
"""

import logging
from datetime import datetime
from typing import NamedTuple

logger = logging.getLogger(__name__)


class TokenUsageSummary(NamedTuple):
    """Aggregated token usage across all LLM calls."""

    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int


class TokenUsageDetail(NamedTuple):
    """Token usage for a single LLM call."""

    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    created_at: datetime


class TokenUsage:
    """Accumulated token usage from LLM calls."""

    def __init__(self) -> None:
        self._usages: list[TokenUsageDetail] = []

    def add(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        cache_write_input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Add a single usage record."""
        logger.debug(
            "TokenUsage - add - provider=%s, model=%s, input_tokens=%d, "
            "cached_input_tokens=%d, cache_write_input_tokens=%d, output_tokens=%d",
            provider,
            model,
            input_tokens,
            cached_input_tokens,
            cache_write_input_tokens,
            output_tokens,
        )
        self._usages.append(
            TokenUsageDetail(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                cache_write_input_tokens=cache_write_input_tokens,
                output_tokens=output_tokens,
                created_at=datetime.now(),
            )
        )

    def get_total(self) -> TokenUsageSummary:
        """Get total token usage across all calls."""
        return TokenUsageSummary(
            input_tokens=sum(u.input_tokens for u in self._usages),
            cached_input_tokens=sum(u.cached_input_tokens for u in self._usages),
            cache_write_input_tokens=sum(u.cache_write_input_tokens for u in self._usages),
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
