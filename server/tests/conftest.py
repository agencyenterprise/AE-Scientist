"""
Pytest configuration and shared fixtures.
"""

import json
import os
import sys
from pathlib import Path
from typing import Callable, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Ensure app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Minimal env required for app initialization in tests
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("XAI_API_KEY", "test")
os.environ.setdefault("METACOGNITION_API_URL", "http://metacognition.test")
os.environ.setdefault("METACOGNITION_AUTH_TOKEN", "test")
os.environ.setdefault("MEM0_API_URL", "http://mem0.test")
os.environ.setdefault("MEM0_USER_ID", "user_test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "test")
os.environ.setdefault("AWS_S3_BUCKET_NAME", "test")
os.environ.setdefault("LINEAR_ACCESS_KEY", "test")

from app.main import app  # noqa: E402
from app.services.database.users import UserData  # noqa: E402


@pytest.fixture
def app_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def authed_client(app_client: TestClient) -> TestClient:
    app_client.cookies.set("session_token", "fake-session")
    return app_client


@pytest.fixture
def mock_user_data() -> UserData:
    return UserData(
        id=123,
        google_id="gid",
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
