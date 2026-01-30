"""Pytest configuration and shared fixtures."""

# Setup env before any app imports
import json
from typing import Callable, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import tests.conftest_setup  # noqa: F401  # pylint: disable=unused-import
from app.main import app
from app.services.database.users import UserData


@pytest.fixture
def app_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def authed_client(app_client: TestClient) -> TestClient:
    app_client.headers.update({"Authorization": "Bearer fake-session"})
    return app_client


@pytest.fixture
def mock_user_data() -> UserData:
    return UserData(
        id=123,
        clerk_user_id="clerk_test_user_123",
        email="unit@test.com",
        name="Unit Tester",
        is_active=True,
        created_at=None,  # type: ignore
        updated_at=None,  # type: ignore
    )


@pytest.fixture
def parse_sse_lines() -> Callable[[httpx.Response], list[dict[str, object]]]:
    def _parse(resp: httpx.Response) -> list[dict[str, object]]:
        return [json.loads(line) for line in resp.iter_lines() if line]

    return _parse


@pytest.fixture
def patch_conversations_get_database() -> Iterator[MagicMock]:
    """Patch conversations API get_database and yield a DB mock."""
    with patch("app.api.conversations.get_database") as mock_get_db:
        db_mock = MagicMock()
        # Sensible defaults for import tests
        db_mock.get_conversation_id_by_url.return_value = 0
        db_mock.list_conversations_by_url.return_value = []
        mock_get_db.return_value = db_mock
        yield db_mock


@pytest.fixture
def patch_auth_user_session(mock_user_data: UserData) -> Iterator[None]:
    """Patch AuthService.get_user_by_session to return mock_user_data."""
    with patch("app.services.auth_service.AuthService.get_user_by_session") as mock_get_user:
        mock_get_user.return_value = mock_user_data
        yield None
