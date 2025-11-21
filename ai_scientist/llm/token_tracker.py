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
            return {
                model: [
                    self._json_safe_interaction(interaction=i) for i in self.interactions[model]
                ]
            }
        return {
            m: [self._json_safe_interaction(interaction=i) for i in interactions]
            for m, interactions in self.interactions.items()
        }

    def reset(self) -> None:
        """Reset all token counts and interactions."""
        self.token_counts = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "reasoning": 0, "cached": 0}
        )
        self.interactions = defaultdict(list)
        # self._encoders = {}

    def get_summary(self) -> dict[str, dict[str, int]]:
        """Get summary of token usage for all models."""
        summary: dict[str, dict[str, int]] = {}
        for model, tokens in self.token_counts.items():
            summary[model] = {k: v for k, v in tokens.items()}
        return summary

    def _json_safe_interaction(self, *, interaction: Dict[str, Any]) -> Dict[str, Any]:
        safe: Dict[str, Any] = dict(interaction)
        ts = safe.get("timestamp")
        if isinstance(ts, datetime):
            safe["timestamp"] = ts.isoformat()
        elif ts is not None:
            safe["timestamp"] = str(ts)
        else:
            safe["timestamp"] = None
        return safe


# Global token tracker instance
token_tracker = TokenTracker()


T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def track_token_usage(func: F) -> F:
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        result = func(*args, **kwargs)

        try:
            model_obj = kwargs.get("model", "unknown-model")
            model = str(model_obj)
            prompt = str(kwargs.get("prompt") or "")
            system_message = str(kwargs.get("system_message") or "")
            timestamp = datetime.utcnow()

            usage_md = getattr(result, "usage_metadata", {}) or {}
            prompt_tokens = int(usage_md.get("input_tokens", 0) or 0)
            completion_tokens = int(usage_md.get("output_tokens", 0) or 0)
            reasoning_tokens = int(usage_md.get("reasoning_tokens", 0) or 0)
            cached_tokens = int(usage_md.get("cached_tokens", 0) or 0)

            token_tracker.add_tokens(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                cached_tokens=cached_tokens,
            )

            response_text = ""
            try:
                # AIMessage.content can be text or a list of blocks; str(...) is robust.
                response_text = str(getattr(result, "content", ""))
            except Exception:
                # Best effort; do not fail if response shape differs
                pass

            token_tracker.add_interaction(
                model=model,
                system_message=str(system_message),
                prompt=str(prompt),
                response=response_text,
                timestamp=timestamp,
            )
        except Exception:
            traceback.print_exc()
            logging.warning("Token tracking failed; continuing without tracking")
        return result

    return wrapper  # type: ignore[return-value]
