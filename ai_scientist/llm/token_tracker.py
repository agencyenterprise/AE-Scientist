import asyncio
import logging
import traceback
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar


class TokenTracker:
    def __init__(self) -> None:
        """
        Token counts for prompt, completion, reasoning, and cached.
        Reasoning tokens are included in completion tokens.
        Cached tokens are included in prompt tokens.
        Also tracks prompts, responses, and timestamps.
        We assume we get these from the LLM response, and we don't count
        the tokens by ourselves.
        """
        self.token_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "reasoning": 0, "cached": 0}
        )
        self.interactions: dict[str, list] = defaultdict(list)

        self.MODEL_PRICES = {
            "gpt-4o-2024-11-20": {
                "prompt": 2.5 / 1000000,  # $2.50 per 1M tokens
                "cached": 1.25 / 1000000,  # $1.25 per 1M tokens
                "completion": 10 / 1000000,  # $10.00 per 1M tokens
            },
            "gpt-4o-2024-08-06": {
                "prompt": 2.5 / 1000000,  # $2.50 per 1M tokens
                "cached": 1.25 / 1000000,  # $1.25 per 1M tokens
                "completion": 10 / 1000000,  # $10.00 per 1M tokens
            },
            "gpt-4o-2024-05-13": {  # this ver does not support cached tokens
                "prompt": 5.0 / 1000000,  # $5.00 per 1M tokens
                "completion": 15 / 1000000,  # $15.00 per 1M tokens
            },
            "gpt-4o-mini-2024-07-18": {
                "prompt": 0.15 / 1000000,  # $0.15 per 1M tokens
                "cached": 0.075 / 1000000,  # $0.075 per 1M tokens
                "completion": 0.6 / 1000000,  # $0.60 per 1M tokens
            },
            "o1-2024-12-17": {
                "prompt": 15 / 1000000,  # $15.00 per 1M tokens
                "cached": 7.5 / 1000000,  # $7.50 per 1M tokens
                "completion": 60 / 1000000,  # $60.00 per 1M tokens
            },
            "o1-preview-2024-09-12": {
                "prompt": 15 / 1000000,  # $15.00 per 1M tokens
                "cached": 7.5 / 1000000,  # $7.50 per 1M tokens
                "completion": 60 / 1000000,  # $60.00 per 1M tokens
            },
            "o3-mini-2025-01-31": {
                "prompt": 1.1 / 1000000,  # $1.10 per 1M tokens
                "cached": 0.55 / 1000000,  # $0.55 per 1M tokens
                "completion": 4.4 / 1000000,  # $4.40 per 1M tokens
            },
            "gpt-5": {
                "prompt": 1.25 / 1000000,  # $1.25 per 1M tokens
                "cached": 0.625 / 1000000,  # $0.625 per 1M tokens (50% discount)
                "completion": 10 / 1000000,  # $10.00 per 1M tokens
            },
            "gpt-5-2025-08-07": {
                "prompt": 1.25 / 1000000,  # $1.25 per 1M tokens
                "cached": 0.625 / 1000000,  # $0.625 per 1M tokens (50% discount)
                "completion": 10 / 1000000,  # $10.00 per 1M tokens
            },
            "gpt-5-mini": {
                "prompt": 0.25 / 1000000,  # $0.25 per 1M tokens
                "cached": 0.125 / 1000000,  # $0.125 per 1M tokens (50% discount)
                "completion": 2 / 1000000,  # $2.00 per 1M tokens
            },
        }

    def add_tokens(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int,
        cached_tokens: int,
    ) -> None:
        self.token_counts[model]["prompt"] += prompt_tokens
        self.token_counts[model]["completion"] += completion_tokens
        self.token_counts[model]["reasoning"] += reasoning_tokens
        self.token_counts[model]["cached"] += cached_tokens

    def add_interaction(
        self,
        model: str,
        system_message: str,
        prompt: str,
        response: str,
        timestamp: datetime,
    ) -> None:
        """Record a single interaction with the model."""
        self.interactions[model].append(
            {
                "system_message": system_message,
                "prompt": prompt,
                "response": response,
                "timestamp": timestamp,
            }
        )

    def get_interactions(self, model: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Get all interactions, optionally filtered by model."""
        if model:
            return {model: self.interactions[model]}
        return dict(self.interactions)

    def reset(self) -> None:
        """Reset all token counts and interactions."""
        self.token_counts = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "reasoning": 0, "cached": 0}
        )
        self.interactions = defaultdict(list)
        # self._encoders = {}

    def calculate_cost(self, model: str) -> float:
        """Calculate the cost for a specific model based on token usage."""
        if model not in self.MODEL_PRICES:
            logging.warning(f"Price information not available for model {model}")
            return 0.0

        prices = self.MODEL_PRICES[model]
        tokens = self.token_counts[model]

        # Calculate cost for prompt and completion tokens
        if "cached" in prices:
            prompt_cost = (tokens["prompt"] - tokens["cached"]) * prices["prompt"]
            cached_cost = tokens["cached"] * prices["cached"]
        else:
            prompt_cost = tokens["prompt"] * prices["prompt"]
            cached_cost = 0
        completion_cost = tokens["completion"] * prices["completion"]

        return prompt_cost + cached_cost + completion_cost

    def get_summary(self) -> dict[str, dict[str, int | float]]:
        """Get summary of token usage and costs for all models."""
        summary: dict[str, dict[str, int | float]] = {}
        for model, tokens in self.token_counts.items():
            summary[model] = {
                **{k: v for k, v in tokens.items()},
                "cost (USD)": self.calculate_cost(model),
            }
        return summary


# Global token tracker instance
token_tracker = TokenTracker()


T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def track_token_usage(func: F) -> F:
    @wraps(func)
    async def async_wrapper(*args: str, **kwargs: str) -> object:
        prompt = kwargs.get("prompt")
        system_message = kwargs.get("system_message")
        if not prompt and not system_message:
            logging.warning(
                "Token tracking skipped: both 'prompt' and 'system_message' are missing"
            )

        result = await func(*args, **kwargs)

        try:
            model = getattr(result, "model", "unknown-model")
            timestamp = getattr(result, "created", datetime.utcnow())

            if hasattr(result, "usage"):
                prompt_tokens = getattr(result.usage, "prompt_tokens", 0)
                completion_tokens = getattr(result.usage, "completion_tokens", 0)
                reasoning_tokens = getattr(
                    getattr(result.usage, "completion_tokens_details", None),
                    "reasoning_tokens",
                    0,
                )
                cached_tokens = getattr(
                    getattr(result.usage, "prompt_tokens_details", None),
                    "cached_tokens",
                    0,
                )

                token_tracker.add_tokens(
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    cached_tokens=cached_tokens,
                )
                # Add interaction details
                response_text = ""
                try:
                    response_text = result.choices[0].message.content or ""
                except Exception:
                    # Best effort; do not fail if response shape differs
                    pass
                token_tracker.add_interaction(
                    model=model,
                    system_message=system_message or "",
                    prompt=prompt or "",
                    response=response_text,
                    timestamp=timestamp,
                )
        except Exception:
            traceback.print_exc()
            logging.warning("Token tracking failed; continuing without tracking")
        return result

    @wraps(func)
    def sync_wrapper(*args: str, **kwargs: str) -> object:
        prompt = kwargs.get("prompt")
        system_message = kwargs.get("system_message")
        if not prompt and not system_message:
            logging.warning(
                "Token tracking skipped: both 'prompt' and 'system_message' are missing"
            )

        result = func(*args, **kwargs)

        try:
            model = getattr(result, "model", "unknown-model")
            timestamp = getattr(result, "created", datetime.utcnow())

            if hasattr(result, "usage"):
                prompt_tokens = getattr(result.usage, "prompt_tokens", 0)
                completion_tokens = getattr(result.usage, "completion_tokens", 0)
                reasoning_tokens = getattr(
                    getattr(result.usage, "completion_tokens_details", None),
                    "reasoning_tokens",
                    0,
                )
                cached_tokens = getattr(
                    getattr(result.usage, "prompt_tokens_details", None),
                    "cached_tokens",
                    0,
                )

                token_tracker.add_tokens(
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    cached_tokens=cached_tokens,
                )
                # Add interaction details
                response_text = ""
                try:
                    response_text = result.choices[0].message.content or ""
                except Exception:
                    # Best effort; do not fail if response shape differs
                    pass
                token_tracker.add_interaction(
                    model=model,
                    system_message=system_message or "",
                    prompt=prompt or "",
                    response=response_text,
                    timestamp=timestamp,
                )
        except Exception:
            traceback.print_exc()
            logging.warning("Token tracking failed; continuing without tracking")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]
