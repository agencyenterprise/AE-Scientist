"""
Unit tests for ChatGPT import flow and summarization decision logic.

Covers:
- Scraping failures and 404s (no conversation created, clear streaming errors)
- Duplicate handling flows
- Generation happy path and summarization-accepted path
- _must_summarize token-budget decisions
- _process_import_background scheduling and callback behavior
"""

import asyncio
import json
from typing import AsyncGenerator, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.models import ImportedChatMessage


def _build_messages(total_chars: int) -> list[ImportedChatMessage]:
    first = total_chars // 2
    second = total_chars - first
    return [
        ImportedChatMessage(role="user", content=("u" * first)),
        ImportedChatMessage(role="assistant", content=("a" * second)),
    ]


def test_must_summarize_false_when_within_context() -> None:
    """_must_summarize returns False when planned tokens fit within context window."""
    # Tokens: message_tokens=400/4=100, system_prompt_tokens=400/4=100,
    # overhead=256, completion=200 -> total=656 <= context(2000) => False
    with (
        patch(
            "app.api.conversations.openai_service.get_context_window_tokens",
            return_value=2000,
        ),
        patch(
            "app.api.conversations.get_project_generation_prompt",
            return_value=("x" * 400),
        ),
        patch(
            "app.api.conversations.settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS",
            200,
        ),
    ):
        from app.api.conversations import _must_summarize

        db = MagicMock()
        messages = _build_messages(400)
        result = _must_summarize(
            db=db,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            messages=messages,
            memories_block="",
        )
        assert result is False


def test_must_summarize_true_when_exceeds_context() -> None:
    """_must_summarize returns True when planned tokens exceed context window."""
    # Same token planning as above but context_window=500 -> 656 > 500 => True
    with (
        patch(
            "app.api.conversations.openai_service.get_context_window_tokens",
            return_value=500,
        ),
        patch(
            "app.api.conversations.get_project_generation_prompt",
            return_value=("y" * 400),
        ),
        patch(
            "app.api.conversations.settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS",
            200,
        ),
    ):
        from app.api.conversations import _must_summarize

        db = MagicMock()
        messages = _build_messages(400)
        result = _must_summarize(
            db=db,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            messages=messages,
            memories_block="",
        )
        assert result is True


@pytest.mark.asyncio
async def test_process_import_background_must_summarize_schedules_summary_only_and_runs_callback() -> (
    None
):
    """Background import: schedules summarization only; callback triggers project draft generation from summary."""
    from app.api.conversations import _process_import_background

    db = MagicMock()
    db.store_memories_block.return_value = None

    messages = _build_messages(40)

    async def fake_create_imported_chat_summary(
        conversation_id: int,
        imported_chat_messages: list[ImportedChatMessage],
        callback_function: Callable[[str], Coroutine[object, object, None]],
    ) -> None:
        assert callback_function is not None
        await callback_function("summary text")

    with (
        patch("app.api.conversations._generate_imported_chat_keywords", return_value=""),
        patch("app.api.conversations.mem0_service.generate_project_creation_memories") as mock_mem0,
        patch("app.api.conversations._must_summarize", return_value=True),
        patch(
            "app.api.conversations.summarizer_service.create_imported_chat_summary",
            side_effect=fake_create_imported_chat_summary,
        ) as mock_sum,
        patch(
            "app.api.conversations._generate_project_draft_consuming_yields",
            new=AsyncMock(return_value=None),
        ) as mock_generate,
    ):
        created_tasks: list[asyncio.Task[None]] = []

        def capture_create_task(coro: Coroutine[object, object, None]) -> asyncio.Task[None]:
            loop = asyncio.get_running_loop()
            task: asyncio.Task[None] = loop.create_task(coro)
            created_tasks.append(task)
            return task

        with patch("app.api.conversations.asyncio.create_task", side_effect=capture_create_task):
            await _process_import_background(
                db=db,
                conversation_id=1,
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                imported_conversation_text="irrelevant",
                messages=messages,
                user_id=99,
            )

        mock_mem0.assert_not_called()
        assert db.store_memories_block.called
        _, kwargs = db.store_memories_block.call_args
        assert kwargs.get("memories_block") == []

        assert len(created_tasks) == 1
        for t in created_tasks:
            await t

        mock_generate.assert_called_once()
        _, g_kwargs = mock_generate.call_args
        assert g_kwargs.get("conversation_id") == 1
        assert g_kwargs.get("imported_conversation") == "summary text"
        assert mock_sum.called


@pytest.mark.asyncio
async def test_process_import_background_no_summarize_schedules_generate_and_summary() -> None:
    """Background import: schedules both direct generation and summarization when within context."""
    from app.api.conversations import _process_import_background

    db = MagicMock()
    db.store_memories_block.return_value = None

    messages = _build_messages(40)

    async def fake_sum(
        conversation_id: int,
        imported_chat_messages: list[ImportedChatMessage],
        callback_function: None,
    ) -> None:
        assert callback_function is None
        return None

    with (
        patch("app.api.conversations._generate_imported_chat_keywords", return_value="k1"),
        patch(
            "app.api.conversations.mem0_service.generate_project_creation_memories",
            return_value=([{"k": 1}], "memories-context"),
        ) as mock_mem0,
        patch("app.api.conversations._must_summarize", return_value=False),
        patch(
            "app.api.conversations.summarizer_service.create_imported_chat_summary",
            side_effect=fake_sum,
        ) as mock_sum,
        patch(
            "app.api.conversations._generate_project_draft_consuming_yields",
            new=AsyncMock(return_value=None),
        ) as mock_generate,
    ):
        created_tasks: list[asyncio.Task[None]] = []

        def capture_create_task(coro: Coroutine[object, object, None]) -> asyncio.Task[None]:
            loop = asyncio.get_running_loop()
            task: asyncio.Task[None] = loop.create_task(coro)
            created_tasks.append(task)
            return task

        with patch("app.api.conversations.asyncio.create_task", side_effect=capture_create_task):
            await _process_import_background(
                db=db,
                conversation_id=7,
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                imported_conversation_text="full conv",
                messages=messages,
                user_id=555,
            )

        assert mock_mem0.called
        assert db.store_memories_block.called
        _, kwargs = db.store_memories_block.call_args
        assert kwargs.get("memories_block") == [{"k": 1}]

        assert len(created_tasks) == 2
        for t in created_tasks:
            await t

        assert mock_generate.called
        _, g_kwargs = mock_generate.call_args
        assert g_kwargs.get("conversation_id") == 7
        assert g_kwargs.get("imported_conversation") == "full conv"
        assert mock_sum.called


@pytest.mark.asyncio
async def test_import_chatgpt_parse_error_does_not_create_conversation(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Import: when ChatGPT scraping fails (generic error), no conversation is created.

    - parser_service.parse_conversation returns ParseErrorResult(success=False)
    - Endpoint should stream an error line and stop
    - DB.create_conversation must not be called
    """

    client = authed_client

    # Import targets inside module where used
    with (patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,):
        db_mock = patch_conversations_get_database

        # Build ParseErrorResult like models specify
        from app.models import ParseErrorResult

        mock_parse.return_value = ParseErrorResult(
            success=False, error="Failed to parse conversation with all browsers"
        )

        payload = {
            "url": "https://chatgpt.com/share/12345678-1234-1234-1234-1234567890ab",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "accept_summarization": False,
            "duplicate_resolution": "create_new",
        }
        with client.stream(method="POST", url="/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        # Expect an error line with the specific error message and no DB creation
        error_lines = [line for line in lines if line.get("type") == "error"]
        assert error_lines, "Expected an error line"
        assert error_lines[0].get("data") == "Failed to parse conversation with all browsers"
        db_mock.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_import_existing_conflict_streams_conflict_prompt(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Import: when conversation already exists and duplicate_resolution=prompt -> conflict line.

    Endpoint should stream a conflict event listing existing conversations and stop without parsing.
    """

    client = authed_client

    url = "https://chatgpt.com/share/aaaaaaaa-1234-1234-1234-1234567890ab"

    with (patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,):
        db_mock = patch_conversations_get_database

        # Prepare existing matching conversation
        from datetime import datetime, timezone

        existing = MagicMock()
        existing.id = 77
        existing.title = "Existing conversation"
        existing.updated_at = datetime.now(timezone.utc)
        existing.url = url
        db_mock.list_conversations_by_url.return_value = [existing]

        payload = {
            "url": url,
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "accept_summarization": False,
            "duplicate_resolution": "prompt",
        }

        with client.stream("POST", "/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        conflict_lines = [line for line in lines if line.get("type") == "conflict"]
        assert conflict_lines, "Expected a conflict line"
        data = conflict_lines[0].get("data")
        assert isinstance(data, dict)
        conversations = data.get("conversations")
        assert isinstance(conversations, list) and len(conversations) == 1
        assert conversations[0].get("id") == 77
        assert conversations[0].get("url") == url

        mock_parse.assert_not_called()
        db_mock.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_import_update_existing_replaces_messages_and_streams_done(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    client = authed_client

    with (
        patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,
        patch(
            "app.api.conversations.summarizer_service.drop_imported_chat_summary_job"
        ) as mock_drop,
        patch(
            "app.api.conversations.summarizer_service.create_imported_chat_summary"
        ) as mock_create_sum,
        patch("app.api.conversations.search_indexer.index_imported_chat") as mock_index,
        patch("app.api.conversations._generate_response_for_conversation") as mock_done,
    ):
        from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult

        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/aaaaaaaa-1234-1234-1234-1234567890ab",
                title="t",
                import_date="2024-01-01T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hi"),
                    ImportedChatMessage(role="assistant", content="yo"),
                ],
            ),
        )
        mock_parse.return_value = success

        async def fake_done(db: MagicMock, conversation_id: int) -> AsyncGenerator[str, None]:
            yield json.dumps({"type": "done", "data": {"conversation_id": conversation_id}}) + "\n"

        mock_done.side_effect = fake_done

        db = patch_conversations_get_database
        target_id = 555
        existing = MagicMock()
        existing.id = target_id
        db.list_conversations_by_url.return_value = [existing]

        payload = {
            "url": success.data.url,
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "duplicate_resolution": "update_existing",
            "target_conversation_id": target_id,
            "accept_summarization": False,
        }

        with client.stream("POST", "/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        assert any(line.get("type") == "done" for line in lines)
        db.update_conversation_messages.assert_called_once()
        mock_drop.assert_called_once()
        mock_create_sum.assert_called_once()
        mock_index.assert_called_once()


@pytest.mark.asyncio
async def test_import_happy_path_create_new_streams_generation_and_done(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    client = authed_client

    with (
        patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,
        patch("app.api.conversations._must_summarize", return_value=False),
        patch("app.api.conversations._generate_imported_chat_keywords", return_value=""),
        patch("app.api.conversations.openai_service.generate_project_draft") as mock_gen,
        patch(
            "app.api.conversations.openai_service._parse_project_draft_response"
        ) as mock_parse_pd,
        patch("app.api.conversations._generate_response_for_conversation") as mock_done,
        patch("app.api.conversations.search_indexer.index_imported_chat"),
        patch("app.api.conversations.search_indexer.index_active_project_draft"),
    ):
        from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult

        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/bbbbbbbb-1234-1234-1234-1234567890ab",
                title="Title",
                import_date="2024-01-02T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hello"),
                    ImportedChatMessage(role="assistant", content="world"),
                ],
            ),
        )
        mock_parse.return_value = success

        async def gen_chunks(*args: object, **kwargs: object) -> AsyncGenerator[str, None]:
            yield "chunk 1"
            yield "chunk 2"

        mock_gen.side_effect = gen_chunks

        parsed_pd = MagicMock()
        parsed_pd.title = "Draft Title"
        parsed_pd.description = "Draft Description"
        mock_parse_pd.return_value = parsed_pd

        async def fake_done(db: MagicMock, conversation_id: int) -> AsyncGenerator[str, None]:
            yield json.dumps({"type": "done", "data": {"conversation_id": conversation_id}}) + "\n"

        mock_done.side_effect = fake_done

        db = patch_conversations_get_database
        db.get_project_draft_by_conversation_id.return_value = None
        db.create_conversation.return_value = 1
        conv = MagicMock()
        conv.id = 1
        db.get_conversation_by_id.return_value = conv

        payload = {
            "url": success.data.url,
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "duplicate_resolution": "create_new",
            "accept_summarization": False,
        }

        with client.stream("POST", "/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        # Should contain generating state, content chunks, and done
        assert any(
            line.get("type") == "state" and line.get("data") == "generating" for line in lines
        )
        contents = [line.get("data") for line in lines if line.get("type") == "content"]
        assert "chunk 1" in contents and "chunk 2" in contents
        assert any(line.get("type") == "done" for line in lines)
        db.create_project_draft.assert_called_once()


@pytest.mark.asyncio
async def test_import_summarization_accept_creates_placeholder_and_streams_done(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Import flow with summarization accepted: emit summarizing state, create placeholder draft, and stream done."""
    client = authed_client

    with (
        patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,
        patch("app.api.conversations._must_summarize", return_value=True),
        patch("app.api.conversations._generate_imported_chat_keywords", return_value="k1"),
        patch(
            "app.api.conversations.mem0_service.generate_project_creation_memories",
            return_value=([], ""),
        ),
        patch("app.api.conversations.search_indexer.index_imported_chat"),
        patch("app.api.conversations.asyncio.create_task") as mock_create_task,
        patch("app.api.conversations._generate_response_for_conversation") as mock_done,
    ):
        from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult

        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/cccccccc-1234-1234-1234-1234567890ab",
                title="t",
                import_date="2024-01-01T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hi"),
                    ImportedChatMessage(role="assistant", content="yo"),
                ],
            ),
        )
        mock_parse.return_value = success

        async def fake_done(db: MagicMock, conversation_id: int) -> AsyncGenerator[str, None]:
            yield json.dumps({"type": "done", "data": {"conversation_id": conversation_id}}) + "\n"

        mock_done.side_effect = fake_done

        db = patch_conversations_get_database
        db.create_conversation.return_value = 321
        conv = MagicMock()
        conv.id = 321
        db.get_conversation_by_id.return_value = conv

        payload = {
            "url": success.data.url,
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "duplicate_resolution": "create_new",
            "accept_summarization": True,
        }

        with client.stream("POST", "/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

    # Expect summarizing state and done
    assert any(line.get("type") == "state" and line.get("data") == "summarizing" for line in lines)
    assert any(line.get("type") == "done" for line in lines)

    # Placeholder draft created
    assert db.create_project_draft.called
    args, kwargs = db.create_project_draft.call_args
    assert kwargs.get("conversation_id") == 321
    assert kwargs.get("title") == "Generating..."
    assert kwargs.get("description") == "Generating project draft..."

    # Background summarization scheduled
    assert mock_create_task.called


@pytest.mark.asyncio
async def test_import_chatgpt_404_does_not_create_conversation_and_returns_specific_code(
    authed_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_auth_user_session: object,
    parse_sse_lines: Callable[[httpx.Response], list[dict]],
) -> None:
    """Import: when ChatGPT conversation is 404 (ChatNotFound), do not create conversation.

    - parser_service.parse_conversation raises ChatNotFound
    - Endpoint streams an error with code CHAT_NOT_FOUND
    - DB.create_conversation must not be called
    """

    client = authed_client

    with (patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,):
        db_mock = patch_conversations_get_database

        from app.services.scraper.errors import ChatNotFound

        mock_parse.side_effect = ChatNotFound("not found")

        payload = {
            "url": "https://chatgpt.com/share/12345678-1234-1234-1234-1234567890ab",
            "llm_model": "gpt-4o-mini",
            "llm_provider": "openai",
            "accept_summarization": False,
            "duplicate_resolution": "create_new",
        }
        with client.stream(method="POST", url="/api/conversations/import", json=payload) as resp:
            assert resp.status_code == 200
            lines = parse_sse_lines(resp)

        error_lines = [line for line in lines if line.get("type") == "error"]
        assert error_lines, "Expected an error line"
        assert error_lines[0].get("code") == "CHAT_NOT_FOUND"
        db_mock.create_conversation.assert_not_called()
