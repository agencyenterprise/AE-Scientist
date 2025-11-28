"""
Unit tests for `_must_summarize` helper in the conversations import flow.
"""

from unittest.mock import MagicMock, patch

from app.api.conversations import _must_summarize
from app.models import ImportedChatMessage


def _build_messages(total_chars: int) -> list[ImportedChatMessage]:
    first = total_chars // 2
    second = total_chars - first
    return [
        ImportedChatMessage(role="user", content="u" * first),
        ImportedChatMessage(role="assistant", content="a" * second),
    ]


def test_must_summarize_false_when_within_context() -> None:
    """_must_summarize returns False when the estimated tokens fit in the model window."""

    with (
        patch(
            "app.api.conversations.openai_service.get_context_window_tokens",
            return_value=2000,
        ),
        patch(
            "app.api.conversations.get_idea_generation_prompt",
            return_value="x" * 400,
        ),
        patch("app.api.conversations.settings.IDEA_MAX_COMPLETION_TOKENS", 200),
    ):
        db = MagicMock()
        messages = _build_messages(400)
        assert (
            _must_summarize(
                db=db,
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                messages=messages,
                memories_block="",
            )
            is False
        )


def test_must_summarize_true_when_planned_tokens_exceed_context() -> None:
    """_must_summarize returns True when the planned tokens exceed the context window."""

    with (
        patch(
            "app.api.conversations.openai_service.get_context_window_tokens",
            return_value=500,
        ),
        patch(
            "app.api.conversations.get_idea_generation_prompt",
            return_value="y" * 400,
        ),
        patch("app.api.conversations.settings.IDEA_MAX_COMPLETION_TOKENS", 200),
    ):
        db = MagicMock()
        messages = _build_messages(400)
        assert (
            _must_summarize(
                db=db,
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                messages=messages,
                memories_block="",
            )
            is True
        )
