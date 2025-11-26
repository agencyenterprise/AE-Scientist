"""
Unit tests for OpenAI ChatWithProjectDraftStream streaming behavior.

Covers:
- Basic content streaming and done event without tool calls
- Tool call flow for update_project_draft and subsequent completion
"""

from typing import Any, AsyncGenerator, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import AsyncOpenAI

from app.models import LLMModel
from app.services.base_llm_service import FileAttachmentData
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
    StreamingResult,
)


class _FakeCompletions:
    async def create(self, *args: object, **kwargs: object) -> object:
        # Returns a dummy stream object; the test patches _collect_streaming_response
        # to ignore this value and yield simulated events.
        class _Dummy:
            def __aiter__(self) -> "_Dummy":
                return self

            async def __anext__(self) -> object:
                raise StopAsyncIteration

        return _Dummy()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = MagicMock()
        self.chat.completions = _FakeCompletions()


def _llm_model(model_id: str) -> LLMModel:
    return LLMModel(
        id=model_id,
        provider="openai",
        label=model_id,
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=128_000,
    )


class RecordingCompletions:
    def __init__(self) -> None:
        self.last_messages: list[dict[str, Any]] | None = None

    async def create(self, *args: object, **kwargs: object) -> object:
        self.last_messages = cast(List[dict[str, Any]] | None, kwargs.get("messages"))

        class _Dummy:
            def __aiter__(self) -> "_Dummy":
                return self

            async def __anext__(self) -> object:
                raise StopAsyncIteration

        return _Dummy()


class RecordingClient:
    def __init__(self) -> None:
        self.chat = MagicMock()
        self.chat.completions = RecordingCompletions()


@pytest.mark.asyncio
async def test_openai_chat_stream_basic_content_and_done() -> None:
    """Stream emits content chunks and a done event when no tool calls are present."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    # Patch database access and summarizer
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response"
        ) as mock_collect,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        async def fake_collect(_response: object) -> AsyncGenerator[object, None]:
            yield StreamContentEvent("content", "Hello ")
            yield StreamContentEvent("content", "world")
            yield StreamingResult(collected_content="Hello world", valid_tool_calls=[])

        mock_collect.side_effect = fake_collect

        # Build service under test
        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[],
            user_id=42,
        ):
            events.append(ev)

        assert any(isinstance(e, StreamContentEvent) for e in events)
        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_openai_chat_stream_update_project_draft_toolcall() -> None:
    """Tool call 'update_project_draft' triggers DB update and stream completes."""
    from app.services.openai.chat_with_project_draft import (
        ChatWithProjectDraftStream,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    # Patch database and system prompt
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response"
        ) as mock_collect,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        # Required for _process_tool_calls success path
        db.get_project_draft_by_conversation_id.return_value = MagicMock()
        mock_get_db.return_value = db

        # Build a valid tool call object
        tool_call = ChoiceDeltaToolCall(
            index=0,
            id="tc1",
            type="function",
            function=ChoiceDeltaToolCallFunction(
                name="update_project_draft",
                arguments='{"title":"T","description":"D"}',
            ),
        )

        # First pass: yield a tool call; second pass: finish with no tools
        call_count = {"n": 0}

        async def fake_collect(_response: object) -> AsyncGenerator[object, None]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                yield StreamingResult(collected_content="", valid_tool_calls=[tool_call])
            else:
                yield StreamContentEvent("content", "Done")
                yield StreamingResult(collected_content="Done", valid_tool_calls=[])

        mock_collect.side_effect = fake_collect

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=10,
            project_draft_id=20,
            user_message="please update",
            chat_history=[],
            attached_files=[],
            user_id=99,
        ):
            events.append(ev)

        # DB update executed
        assert db.create_project_draft_version.called
        # Stream completes
        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_openai_chat_stream_toolcall_invalid_json_args_continues() -> None:
    """Invalid JSON in tool args is handled, then stream continues to completion."""
    from app.services.openai.chat_with_project_draft import (
        ChatWithProjectDraftStream,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response"
        ) as mock_collect,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.get_project_draft_by_conversation_id.return_value = MagicMock()
        mock_get_db.return_value = db

        # Malformed JSON arguments to trigger JSONDecodeError
        bad_tool = ChoiceDeltaToolCall(
            index=0,
            id="tc-bad",
            type="function",
            function=ChoiceDeltaToolCallFunction(name="update_project_draft", arguments="{bad"),
        )

        call_count = {"n": 0}

        async def fake_collect(_response: object) -> AsyncGenerator[object, None]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First pass: present invalid tool call
                yield StreamingResult(collected_content="", valid_tool_calls=[bad_tool])
            else:
                # Second pass: finish without tools
                yield StreamContentEvent("content", "ok")
                yield StreamingResult(collected_content="ok", valid_tool_calls=[])

        mock_collect.side_effect = fake_collect

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[],
            user_id=42,
        ):
            events.append(ev)

        # Should complete and not crash despite invalid tool args
        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_openai_chat_stream_no_content_yields_done_with_empty_assistant() -> None:
    """When no content chunks are produced, stream ends with done (empty response)."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response"
        ) as mock_collect,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        async def fake_collect(_response: object) -> AsyncGenerator[object, None]:
            # No StreamContentEvent, just final result
            yield StreamingResult(collected_content="", valid_tool_calls=[])

        mock_collect.side_effect = fake_collect

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=99,
            project_draft_id=100,
            user_message="hi",
            chat_history=[],
            attached_files=[],
            user_id=77,
        ):
            events.append(ev)

        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_openai_chat_stream_includes_pdf_text_in_user_message() -> None:
    """PDF attachments content is appended to user message text for chat completions."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    # Use shared RecordingClient helper
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft.format_pdf_content_for_context",
            return_value="\n\n--- PDF Documents ---\n\n**the.pdf:**\nPDF_MARK\n\n",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response",
            return_value=AsyncMock(),
        ) as mock_collect,
    ):

        async def _fake_collector() -> AsyncGenerator[object, None]:
            yield StreamingResult(collected_content="", valid_tool_calls=[])

        mock_collect.side_effect = _fake_collector

        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        pdf = FileAttachmentData(
            id=1,
            filename="the.pdf",
            file_type="application/pdf",
            file_size=2048,
            created_at=None,  # type: ignore
            chat_message_id=1,
            conversation_id=123,
            s3_key="k.pdf",
        )

        client = RecordingClient()
        async for _ in stream.chat_with_project_draft_stream(
            client=cast(AsyncOpenAI, client),
            model=_llm_model("gpt-4o-mini"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[pdf],
            user_id=42,
        ):
            pass

        msgs = client.chat.completions.last_messages
        assert msgs is not None and len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg.get("role") == "user"
        content = user_msg.get("content")
        assert isinstance(content, str)
        assert "PDF_MARK" in content


@pytest.mark.asyncio
async def test_openai_chat_stream_includes_text_file_content_in_user_message() -> None:
    """Text attachments are appended to user message via _format_text_content_for_context."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    # Use shared RecordingClient helper
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft.get_s3_service",
            return_value=MagicMock(
                download_file_content=MagicMock(return_value=b"HELLO_TEXT_FILE")
            ),
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response",
            return_value=AsyncMock(),
        ) as mock_collect,
    ):

        async def _fake_collector() -> AsyncGenerator[object, None]:
            yield StreamingResult(collected_content="", valid_tool_calls=[])

        mock_collect.side_effect = _fake_collector

        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        text_file = FileAttachmentData(
            id=2,
            filename="note.txt",
            file_type="text/plain",
            file_size=100,
            created_at=None,  # type: ignore
            chat_message_id=1,
            conversation_id=123,
            s3_key="t.txt",
        )

        client = RecordingClient()
        async for _ in stream.chat_with_project_draft_stream(
            client=cast(AsyncOpenAI, client),
            model=_llm_model("gpt-4o-mini"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[text_file],
            user_id=42,
        ):
            pass

        msgs = client.chat.completions.last_messages
        assert msgs is not None and len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg.get("role") == "user"
        content = user_msg.get("content")
        assert isinstance(content, str)
        # The formatted helper should include decoded text
        assert "HELLO_TEXT_FILE" in content


@pytest.mark.asyncio
async def test_openai_chat_stream_includes_image_urls_in_user_message_content_list() -> None:
    """Image attachments are represented as content list with text and image_url blocks."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    # Use shared RecordingClient helper
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft.get_s3_service",
            return_value=MagicMock(
                generate_download_url=MagicMock(return_value="https://img.example/x.png")
            ),
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response",
            return_value=AsyncMock(),
        ) as mock_collect,
    ):

        async def _fake_collector() -> AsyncGenerator[object, None]:
            yield StreamingResult(collected_content="", valid_tool_calls=[])

        mock_collect.side_effect = _fake_collector

        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        image = FileAttachmentData(
            id=3,
            filename="pic.png",
            file_type="image/png",
            file_size=1000,
            created_at=None,  # type: ignore
            chat_message_id=1,
            conversation_id=123,
            s3_key="i.png",
        )

        client = RecordingClient()
        async for _ in stream.chat_with_project_draft_stream(
            client=cast(AsyncOpenAI, client),
            model=_llm_model("gpt-4o-mini"),
            conversation_id=1,
            project_draft_id=2,
            user_message="Describe this:",
            chat_history=[],
            attached_files=[image],
            user_id=42,
        ):
            pass

        msgs = client.chat.completions.last_messages
        assert msgs is not None and len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg.get("role") == "user"
        content = user_msg.get("content")
        assert isinstance(content, list)
        # First block should be text, second an image_url block with our URL
        assert content[0].get("type") == "text"
        assert content[0].get("text") == "Describe this:"
        assert content[1].get("type") == "image_url"
        assert content[1].get("image_url", {}).get("url") == "https://img.example/x.png"


@pytest.mark.asyncio
async def test_openai_chat_stream_exception_emits_error_event() -> None:
    """Unexpected error in streaming path emits an error event."""
    from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream

    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response",
            side_effect=RuntimeError("boom"),
        ),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=5,
            project_draft_id=6,
            user_message="x",
            chat_history=[],
            attached_files=[],
            user_id=1,
        ):
            events.append(ev)

        # Expect an error event to be present
        from app.services.chat_models import StreamErrorEvent

        assert any(isinstance(e, StreamErrorEvent) for e in events)


@pytest.mark.asyncio
async def test_openai_chat_stream_create_linear_project_tool_locks_conversation() -> None:
    """Tool call 'create_linear_project' should create a project and emit conversation_locked."""
    from app.services.openai.chat_with_project_draft import (
        ChatWithProjectDraftStream,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch(
            "app.services.openai.chat_with_project_draft._collect_streaming_response"
        ) as mock_collect,
        patch("app.services.openai.chat_with_project_draft.LinearService") as mock_linear,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        # Required by tool to fetch current draft
        db.get_project_draft_by_conversation_id.return_value = MagicMock(title="T", description="D")
        mock_get_db.return_value = db

        # Mock Linear service to return a project object with url
        linear_instance = MagicMock()
        linear_instance.create_project = AsyncMock(
            return_value=MagicMock(id="pid", name="pname", content="pcontent", url="http://u")
        )
        mock_linear.return_value = linear_instance

        # First pass tool call, then end
        tool_call = ChoiceDeltaToolCall(
            index=0,
            id="tc-lin",
            type="function",
            function=ChoiceDeltaToolCallFunction(name="create_linear_project", arguments="{}"),
        )

        call_count = {"n": 0}

        async def fake_collect(_response: object) -> AsyncGenerator[object, None]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                yield StreamingResult(collected_content="", valid_tool_calls=[tool_call])
            else:
                yield StreamingResult(collected_content="", valid_tool_calls=[])

        mock_collect.side_effect = fake_collect

        fake_service = MagicMock()
        fake_summarizer = MagicMock()
        fake_summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        stream = ChatWithProjectDraftStream(fake_service, fake_summarizer)

        events: List[object] = []
        client = cast(AsyncOpenAI, _FakeClient())
        async for ev in stream.chat_with_project_draft_stream(
            client=client,
            model=_llm_model("gpt-4o-mini"),
            conversation_id=77,
            project_draft_id=88,
            user_message="create linear",
            chat_history=[],
            attached_files=[],
            user_id=11,
        ):
            events.append(ev)

        # Linear call performed and conversation locked event emitted
        assert linear_instance.create_project.awaited
        assert any(isinstance(e, StreamConversationLockedEvent) for e in events)
