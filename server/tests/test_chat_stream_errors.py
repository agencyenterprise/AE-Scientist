"""
Unit tests for chat streaming error cases and empty outputs.

Validates that:
- Mid-stream exceptions emit a single error line (200 OK, in-stream error)
- Empty assistant responses are treated as errors and not persisted
- Placeholder test for summarization-required conflict behavior
"""

from typing import AsyncGenerator, Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult
from app.services.chat_models import StreamContentEvent, StreamDoneData, StreamDoneEvent


def _is_stream_error_with_message(line: dict[str, object], substring: str) -> bool:
    if line.get("type") != "error":
        return False
    data_obj = line.get("data")
    if not isinstance(data_obj, str):
        return False
    return data_obj.startswith("Stream error:") and (substring in data_obj)


@pytest.fixture
def patch_chat_stream_common(mock_user_data: object) -> Iterator[MagicMock]:
    with (
        patch("app.api.chat_stream.get_database") as mock_get_db,
        patch("app.api.chat_stream.get_current_user") as mock_get_user,
        patch("app.services.auth_service.AuthService.get_user_by_session") as mock_get_by_session,
        patch(
            "app.api.chat_stream.summarizer_service.add_messages_to_chat_summary",
            new=AsyncMock(return_value=None),
        ),
    ):
        db = MagicMock()
        db.get_conversation_by_id.return_value = MagicMock()
        db.get_idea_by_conversation_id.return_value = MagicMock(idea_id=1)
        db.create_idea.return_value = 1
        db.get_chat_messages.return_value = []
        db.create_chat_message.return_value = 101
        db.get_file_attachments_by_ids.return_value = []
        mock_get_db.return_value = db
        mock_get_user.return_value = mock_user_data
        mock_get_by_session.return_value = mock_user_data
        yield db


@pytest.mark.asyncio
async def test_stream_midstream_error_emits_single_error_line_openai(
    authed_client: TestClient,
    mock_user_data: object,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Chat stream: OpenAI mid-stream exception -> one error line, 200 OK.

    - Generator raises after first chunk
    - Endpoint should emit an in-stream error and stop
    """

    del mock_user_data, patch_chat_stream_common
    client = authed_client

    async def failing_generator(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamContentEvent("content", "Hello")
        raise RuntimeError("network fail")

    with patch(
        "app.api.chat_stream.openai_service.chat_with_idea_stream",
        side_effect=failing_generator,
    ):

        payload = {
            "message": "hi",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        # Last line should be an error
        assert any(line.get("type") == "error" for line in lines)
        # Error message should include the mid-stream failure reason
        assert any(_is_stream_error_with_message(line, "network fail") for line in lines)


@pytest.mark.asyncio
async def test_stream_immediate_exception_emits_error_openai(
    authed_client: TestClient,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    del patch_chat_stream_common
    client = authed_client

    class _FailingAsyncIter:
        def __aiter__(self) -> "_FailingAsyncIter":
            return self

        async def __anext__(self) -> object:
            raise RuntimeError("immediate fail")

    def _iterator_factory(*_args: object, **_kwargs: object) -> _FailingAsyncIter:
        return _FailingAsyncIter()

    with patch(
        "app.api.chat_stream.openai_service.chat_with_idea_stream",
        side_effect=_iterator_factory,
    ):
        payload = {
            "message": "hi",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

    assert any(line.get("type") == "error" for line in lines)
    assert any(_is_stream_error_with_message(line, "immediate fail") for line in lines)


@pytest.mark.asyncio
async def test_stream_midstream_error_emits_single_error_line_anthropic(
    authed_client: TestClient,
    mock_user_data: object,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Chat stream: Anthropic mid-stream exception -> one error line, 200 OK."""

    del mock_user_data, patch_chat_stream_common
    client = authed_client

    async def failing_generator(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamContentEvent("content", "Hello")
        raise RuntimeError("network fail")

    with patch(
        "app.api.chat_stream.anthropic_service.chat_with_idea_stream",
        side_effect=failing_generator,
    ):

        payload = {
            "message": "hi",
            "llm_model": "claude-3-5-haiku-20241022",
            "llm_provider": "anthropic",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        assert any(line.get("type") == "error" for line in lines)
        assert any(_is_stream_error_with_message(line, "network fail") for line in lines)


@pytest.mark.asyncio
async def test_stream_midstream_error_emits_single_error_line_grok(
    authed_client: TestClient,
    mock_user_data: object,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Chat stream: Grok mid-stream exception -> one error line, 200 OK."""

    del mock_user_data, patch_chat_stream_common
    client = authed_client

    async def failing_generator(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamContentEvent("content", "Hello")
        raise RuntimeError("network fail")

    with patch(
        "app.api.chat_stream.grok_service.chat_with_idea_stream",
        side_effect=failing_generator,
    ):

        payload = {
            "message": "hi",
            "llm_model": "grok-3",
            "llm_provider": "grok",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        assert any(line.get("type") == "error" for line in lines)
        assert any(_is_stream_error_with_message(line, "network fail") for line in lines)


@pytest.mark.asyncio
async def test_stream_empty_output_is_error_and_not_persisted(
    authed_client: TestClient,
    mock_user_data: object,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Chat stream: empty assistant response -> emit error, do not store message.

    - Provider yields a StreamDoneEvent with empty assistant_response
    - Endpoint emits an error line and returns without persisting
    """

    del mock_user_data
    client = authed_client

    async def done_empty(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamDoneEvent(
            "done",
            StreamDoneData(idea_updated=False, assistant_response=""),
        )

    with patch(
        "app.api.chat_stream.openai_service.chat_with_idea_stream",
        side_effect=done_empty,
    ):

        payload = {
            "message": "hi",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        assert lines, "expected at least one line"
        # Should contain an error line for empty model output
        assert any(
            line.get("type") == "error" and line.get("data") == "Empty model output"
            for line in lines
        )
        # Only the user message should be persisted; assistant message must not be persisted
        db = patch_chat_stream_common
        assert db.create_chat_message.call_count == 1
        args, kwargs = db.create_chat_message.call_args
        assert kwargs.get("role") == "user"


@pytest.mark.asyncio
async def test_stream_whitespace_output_is_error_and_not_persisted(
    authed_client: TestClient,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    client = authed_client

    async def done_space(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamDoneEvent(
            "done",
            StreamDoneData(idea_updated=False, assistant_response="   \n"),
        )

    with patch(
        "app.api.chat_stream.openai_service.chat_with_idea_stream",
        side_effect=done_space,
    ):
        payload = {
            "message": "hi",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

    assert any(
        line.get("type") == "error" and line.get("data") == "Empty model output" for line in lines
    )
    db = patch_chat_stream_common
    assert db.create_chat_message.call_count == 1
    _, kwargs = db.create_chat_message.call_args
    assert kwargs.get("role") == "user"


@pytest.mark.asyncio
async def test_import_summarization_required_placeholder(
    authed_client: TestClient,
    mock_user_data: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Placeholder: summarization-required behavior when accept_summarization is false.

    Currently, the endpoint emits a model_limit_conflict line and exits. This test
    documents the behavior; final contract to be decided.
    """

    client = authed_client

    with (
        patch("app.api.conversations.validate_import_chat_url", return_value=True),
        patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,
        patch("app.api.conversations.get_database") as mock_get_db,
        patch("app.api.conversations.get_current_user") as mock_get_user,
        patch("app.services.auth_service.AuthService.get_user_by_session") as mock_get_by_session,
        patch("app.api.conversations._must_summarize", return_value=True),
        patch("app.api.conversations._generate_imported_chat_keywords", return_value="k1, k2"),
        patch(
            "app.api.conversations.mem0_service.generate_project_creation_memories",
            return_value=([], ""),
        ),
    ):
        db = MagicMock()
        db.get_conversation_id_by_url.return_value = 0
        mock_get_db.return_value = db
        mock_get_user.return_value = mock_user_data
        mock_get_by_session.return_value = mock_user_data

        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/12345678-1234-1234-1234-1234567890ab",
                title="t",
                import_date="2024-01-01T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hi"),
                    ImportedChatMessage(role="assistant", content="yo"),
                ],
            ),
        )
        mock_parse.return_value = success

        payload = {
            "url": "https://chatgpt.com/share/12345678-1234-1234-1234-1234567890ab",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "duplicate_resolution": "create_new",
            "accept_summarization": False,
        }
        with client.stream("POST", "/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        # Expect a model_limit_conflict line per current behavior
        assert any(line.get("type") == "model_limit_conflict" for line in lines)
        # Validate the message content shown to the user
        conflict_lines = [line for line in lines if line.get("type") == "model_limit_conflict"]
        assert conflict_lines
        conflict = conflict_lines[0]
        assert isinstance(conflict.get("data"), dict)
        assert conflict["data"].get("message") == (
            "Imported chat is too long for the selected model context. Summarization is required and can take several minutes."
        )
        assert "suggestion" in conflict["data"]


@pytest.mark.asyncio
async def test_stream_done_then_exception_persists_assistant_and_emits_error(
    authed_client: TestClient,
    patch_chat_stream_common: MagicMock,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    client = authed_client

    async def gen_done_then_fail(*args: object, **kwargs: object) -> AsyncGenerator[object, None]:
        del args, kwargs
        yield StreamDoneEvent(
            "done",
            StreamDoneData(idea_updated=False, assistant_response="Answer A"),
        )
        raise RuntimeError("later failure")

    with patch(
        "app.api.chat_stream.openai_service.chat_with_idea_stream",
        side_effect=gen_done_then_fail,
    ):
        payload = {
            "message": "hi",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "attachment_ids": [],
        }
        with client.stream("POST", "/api/conversations/1/idea/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

    # Assistant message should be persisted despite later failure
    db = patch_chat_stream_common
    assert db.create_chat_message.call_count >= 2  # user + assistant
    roles = [call.kwargs.get("role") for call in db.create_chat_message.call_args_list]
    assert "assistant" in roles
    # Error line should also be emitted
    assert any(line.get("type") == "error" for line in lines)
