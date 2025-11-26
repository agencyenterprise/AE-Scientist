"""
Tests for Slack import endpoint: /api/conversations/import-slack
"""

from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def patch_service_api_key() -> Iterator[None]:
    with patch("app.middleware.auth.AuthService.validate_service_key") as mock_validate:
        mock_validate.return_value = {"service_name": "test-service"}
        yield None


@pytest.fixture
def service_auth_headers() -> dict[str, str]:
    return {"x-api-key": "any-test-key"}


@pytest.mark.asyncio
async def test_slack_import_returns_existing_when_url_exists(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    # Existing conversation found
    patch_conversations_get_database.get_conversation_id_by_url.return_value = 42

    with patch("app.api.conversations.parser_service.parse_conversation") as mock_parse:
        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/u", "user_id": 99},
            headers=service_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 42
        assert data["message"] == "Conversation already exists"
        mock_parse.assert_not_called()


@pytest.mark.asyncio
async def test_slack_import_existing_short_circuit(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    # Existing conversation found should short-circuit without parsing
    patch_conversations_get_database.get_conversation_id_by_url.return_value = 99

    with patch("app.api.conversations.parser_service.parse_conversation") as mock_parse:
        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/x", "user_id": 1},
            headers=service_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 99
        assert data["message"] == "Conversation already exists"
        mock_parse.assert_not_called()


@pytest.mark.asyncio
async def test_slack_import_chat_not_found(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    from app.services.scraper.errors import ChatNotFound

    with patch("app.api.conversations.parser_service.parse_conversation") as mock_parse:
        mock_parse.side_effect = ChatNotFound("nope")
        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/missing", "user_id": 7},
            headers=service_auth_headers,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "CHAT_NOT_FOUND"


@pytest.mark.asyncio
async def test_slack_import_parse_error(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    from app.models import ParseErrorResult

    with patch("app.api.conversations.parser_service.parse_conversation") as mock_parse:
        mock_parse.return_value = ParseErrorResult(success=False, error="bad parse")
        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/err", "user_id": 7},
            headers=service_auth_headers,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "Parse failed"
        assert data["detail"] == "bad parse"


@pytest.mark.asyncio
async def test_slack_import_create_conversation_failure_returns_500(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult

    with patch("app.api.conversations.parser_service.parse_conversation") as mock_parse:
        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/s1",
                title="t",
                import_date="2024-01-01T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hi"),
                    ImportedChatMessage(role="assistant", content="yo"),
                ],
            ),
        )
        mock_parse.return_value = success
        patch_conversations_get_database.create_conversation.side_effect = RuntimeError("boom")

        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/s1", "user_id": 3},
            headers=service_auth_headers,
        )
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "Import failed"


@pytest.mark.asyncio
async def test_slack_import_success_creates_draft_and_schedules_background(
    app_client: TestClient,
    patch_conversations_get_database: MagicMock,
    patch_service_api_key: None,
    service_auth_headers: dict[str, str],
) -> None:
    client = app_client

    from app.models import ImportedChat, ImportedChatMessage, ParseSuccessResult

    with (
        patch("app.api.conversations.parser_service.parse_conversation") as mock_parse,
        patch("app.api.conversations.asyncio.create_task") as mock_create_task,
    ):
        success = ParseSuccessResult(
            success=True,
            data=ImportedChat(
                url="https://chatgpt.com/share/s2",
                title="t2",
                import_date="2024-01-02T00:00:00",
                content=[
                    ImportedChatMessage(role="user", content="hello"),
                    ImportedChatMessage(role="assistant", content="world"),
                ],
            ),
        )
        mock_parse.return_value = success
        patch_conversations_get_database.create_conversation.return_value = 123

        resp = client.post(
            "/api/conversations/import-slack",
            json={"url": "https://chatgpt.com/share/s2", "user_id": 8},
            headers=service_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 123
        assert data["message"] == "Conversation imported successfully"

        # Draft created
        assert patch_conversations_get_database.create_project_draft.called
        # Background task scheduled
        assert mock_create_task.called
