"""
Unit tests for Anthropic (Claude) ChatWithProjectDraftStream streaming behavior.

Covers analogous scenarios to the OpenAI tests:
- Basic content streaming and done event without tool calls
- Tool call flow for update_project_draft and subsequent completion
- Invalid tool args handling followed by completion
- No content yields done event
- Attachment handling in message construction (text, pdf, image)
- Exception path emits error event
- create_linear_project tool locks conversation
"""

import base64
import os
from typing import Any, Callable, Iterable, List, Optional, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import LLMModel
from app.services.base_llm_service import FileAttachmentData
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
)


def _llm_model(model_id: str) -> LLMModel:
    return LLMModel(
        id=model_id,
        provider="anthropic",
        label=model_id,
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    )


# Minimal event classes to simulate Anthropic streaming chunks
class _Delta:
    def __init__(
        self, type: str, text: Optional[str] = None, partial_json: Optional[str] = None
    ) -> None:
        self.type = type
        self.text = text
        self.partial_json = partial_json


class _ContentBlock:
    def __init__(self, type: str, id: Optional[str] = None, name: Optional[str] = None) -> None:
        self.type = type
        self.id = id
        self.name = name


class _Chunk:
    def __init__(
        self,
        type: str,
        delta: Optional[_Delta] = None,
        index: int = 0,
        content_block: Optional[_ContentBlock] = None,
    ) -> None:
        self.type = type
        self.delta = delta
        self.index = index
        self.content_block = content_block


class _Events:
    def __init__(self, chunks: Iterable[object]) -> None:
        self._chunks = list(chunks)
        self._i = 0

    def __aiter__(self) -> "_Events":
        return self

    async def __anext__(self) -> object:
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        v = self._chunks[self._i]
        self._i += 1
        return v


class _StreamContext:
    def __init__(self, events: _Events) -> None:
        self._events = events

    async def __aenter__(self) -> _Events:
        return self._events

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class RecordingAnthropicMessages:
    def __init__(self, event_factory: Callable[[int], Iterable[object]]) -> None:
        self._event_factory = event_factory
        self._call_count = 0
        self.last_messages: Optional[List[dict[str, Any]]] = None
        self.last_tools: Optional[List[dict[str, Any]]] = None
        self.last_system: Optional[str] = None

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: List[dict[str, Any]],
        tools: Optional[List[dict[str, Any]]] = None,
    ) -> _StreamContext:
        # Record call arguments for assertions
        self.last_messages = messages
        self.last_tools = tools
        self.last_system = system

        events = self._event_factory(self._call_count)
        self._call_count += 1
        return _StreamContext(_Events(events))


class RecordingAnthropicClient:
    def __init__(self, event_factory: Callable[[int], Iterable[object]]) -> None:
        self.messages = RecordingAnthropicMessages(event_factory)


@pytest.mark.asyncio
async def test_anthropic_chat_stream_basic_content_and_done() -> None:
    from app.services.anthropic_service import AnthropicService

    # First and only streaming call yields two text chunks
    def factory(call_index: int) -> Iterable[object]:
        if call_index == 0:
            return [
                _Chunk(type="content_block_delta", delta=_Delta("text_delta", text="Hello ")),
                _Chunk(type="content_block_delta", delta=_Delta("text_delta", text="world")),
            ]
        return []

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
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
async def test_anthropic_chat_stream_update_project_draft_toolcall() -> None:
    from app.services.anthropic_service import AnthropicService

    # First call: tool_use update_project_draft; Second call: normal content chunk
    def factory(call_index: int) -> Iterable[object]:
        if call_index == 0:
            return [
                _Chunk(
                    type="content_block_start",
                    content_block=_ContentBlock("tool_use", id="tc1", name="update_project_draft"),
                    index=0,
                ),
                _Chunk(
                    type="content_block_delta",
                    delta=_Delta(
                        "input_json_delta", partial_json='{"title":"T","description":"D"}'
                    ),
                    index=0,
                ),
                _Chunk(type="content_block_stop", index=0),
            ]
        return [
            _Chunk(type="content_block_delta", delta=_Delta("text_delta", text="Done")),
        ]

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.get_project_draft_by_conversation_id.return_value = MagicMock()
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=10,
            project_draft_id=20,
            user_message="please update",
            chat_history=[],
            attached_files=[],
            user_id=99,
        ):
            events.append(ev)

        assert db.create_project_draft_version.called
        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_anthropic_chat_stream_toolcall_invalid_json_args_continues() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        if call_index == 0:
            return [
                _Chunk(
                    type="content_block_start",
                    content_block=_ContentBlock(
                        "tool_use", id="tc-bad", name="update_project_draft"
                    ),
                    index=0,
                ),
                _Chunk(
                    type="content_block_delta",
                    delta=_Delta("input_json_delta", partial_json="{bad"),
                    index=0,
                ),
                _Chunk(type="content_block_stop", index=0),
            ]
        return [
            _Chunk(type="content_block_delta", delta=_Delta("text_delta", text="ok")),
        ]

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.get_project_draft_by_conversation_id.return_value = MagicMock()
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[],
            user_id=42,
        ):
            events.append(ev)

        assert any(isinstance(e, StreamDoneEvent) for e in events)


@pytest.mark.asyncio
async def test_anthropic_chat_stream_no_content_yields_done_with_empty_assistant() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        return []

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
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
async def test_anthropic_chat_stream_includes_text_file_content_in_user_message() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        return []

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
        patch(
            "app.services.anthropic_service.get_s3_service",
            return_value=MagicMock(
                download_file_content=MagicMock(return_value=b"HELLO_TEXT_FILE")
            ),
        ),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

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

        # Drive the stream to capture built messages
        async for _ in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[text_file],
            user_id=42,
        ):
            pass

        # Access the recorded messages from the fake client
        client = cast(RecordingAnthropicClient, service.client)
        msgs = client.messages.last_messages
        assert msgs is not None and len(msgs) >= 1
        # The final user message should be a plain string content including text file body
        last_user = msgs[-1]
        assert last_user.get("role") == "user"
        content = last_user.get("content")
        assert isinstance(content, str)
        assert "HELLO_TEXT_FILE" in content


@pytest.mark.asyncio
async def test_anthropic_chat_stream_includes_pdf_document_block_in_user_message() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        return []

    pdf_bytes = b"PDF_BYTES"
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
        patch(
            "app.services.anthropic_service.get_s3_service",
            return_value=MagicMock(download_file_content=MagicMock(return_value=pdf_bytes)),
        ),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

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

        async for _ in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=1,
            project_draft_id=2,
            user_message="hi",
            chat_history=[],
            attached_files=[pdf],
            user_id=42,
        ):
            pass

        client = cast(RecordingAnthropicClient, service.client)
        msgs = client.messages.last_messages
        assert msgs is not None and len(msgs) >= 1
        last_user = msgs[-1]
        assert last_user.get("role") == "user"
        content = last_user.get("content")
        assert isinstance(content, list)
        # First block is text
        assert content[0].get("type") == "text"
        assert content[0].get("text") == "hi"
        # There should be a document block with our base64 data
        doc_blocks = [b for b in content if b.get("type") == "document"]
        assert len(doc_blocks) == 1
        doc_src = doc_blocks[0].get("source", {})
        assert doc_src.get("type") == "base64"
        assert doc_src.get("media_type") == "application/pdf"
        assert doc_src.get("data") == pdf_b64


@pytest.mark.asyncio
async def test_anthropic_chat_stream_includes_image_block_in_user_message() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        return []

    image_bytes = b"IMG_BYTES"

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
        patch(
            "app.services.anthropic_service.get_s3_service",
            return_value=MagicMock(download_file_content=MagicMock(return_value=image_bytes)),
        ),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

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

        async for _ in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=1,
            project_draft_id=2,
            user_message="Describe this:",
            chat_history=[],
            attached_files=[image],
            user_id=42,
        ):
            pass

        client = cast(RecordingAnthropicClient, service.client)
        msgs = client.messages.last_messages
        assert msgs is not None and len(msgs) >= 1
        last_user = msgs[-1]
        assert last_user.get("role") == "user"
        content = last_user.get("content")
        assert isinstance(content, list)
        # First block should be text, then an image block
        assert content[0].get("type") == "text"
        assert content[0].get("text") == "Describe this:"
        img_blocks = [b for b in content if b.get("type") == "image"]
        assert len(img_blocks) == 1
        img_src = img_blocks[0].get("source", {})
        assert img_src.get("type") == "base64"
        assert img_src.get("media_type") == "image/png"


@pytest.mark.asyncio
async def test_anthropic_chat_stream_exception_emits_error_event() -> None:
    from app.services.anthropic_service import AnthropicService

    class RaisingMessages:
        def stream(self, *args: object, **kwargs: object) -> object:
            # Return a context manager that raises on enter
            class _Ctx:
                async def __aenter__(self) -> object:
                    raise RuntimeError("boom")

                async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    return False

            return _Ctx()

    class RaisingClient:
        def __init__(self) -> None:
            self.messages = RaisingMessages()

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic", return_value=RaisingClient()
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        mock_get_db.return_value = db

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=5,
            project_draft_id=6,
            user_message="x",
            chat_history=[],
            attached_files=[],
            user_id=1,
        ):
            events.append(ev)

        from app.services.chat_models import StreamErrorEvent

        assert any(isinstance(e, StreamErrorEvent) for e in events)


@pytest.mark.asyncio
async def test_anthropic_chat_stream_create_linear_project_tool_locks_conversation() -> None:
    from app.services.anthropic_service import AnthropicService

    def factory(call_index: int) -> Iterable[object]:
        if call_index == 0:
            return [
                _Chunk(
                    type="content_block_start",
                    content_block=_ContentBlock(
                        "tool_use", id="tc-lin", name="create_linear_project"
                    ),
                    index=0,
                ),
                _Chunk(
                    type="content_block_delta",
                    delta=_Delta("input_json_delta", partial_json="{}"),
                    index=0,
                ),
                _Chunk(type="content_block_stop", index=0),
            ]
        return []

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}),
        patch(
            "app.services.anthropic_service.anthropic.AsyncAnthropic",
            return_value=RecordingAnthropicClient(factory),
        ),
        patch("app.services.anthropic_service.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
        patch("app.services.anthropic_service.LinearService") as mock_linear,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.get_project_draft_by_conversation_id.return_value = MagicMock(title="T", description="D")
        mock_get_db.return_value = db

        # Mock Linear service
        linear_instance = MagicMock()
        linear_instance.create_project = AsyncMock(
            return_value=MagicMock(id="pid", name="pname", content="pcontent", url="http://u")
        )
        mock_linear.return_value = linear_instance

        summarizer = MagicMock()
        summarizer.get_chat_summary = AsyncMock(return_value=("", []))
        service = AnthropicService(summarizer)

        events: List[object] = []
        async for ev in service.chat_with_project_draft_stream(
            llm_model=_llm_model("claude-3-5-haiku-20241022"),
            conversation_id=77,
            project_draft_id=88,
            user_message="create linear",
            chat_history=[],
            attached_files=[],
            user_id=11,
        ):
            events.append(ev)

        assert linear_instance.create_project.awaited
        assert any(isinstance(e, StreamConversationLockedEvent) for e in events)
