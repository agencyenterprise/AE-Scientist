#!/usr/bin/env python3
"""
LLM Model Capabilities Test Suite.

Tests all supported models across all providers to validate:
1. Model capability assumptions (supports_images, supports_pdfs) are correct
2. Our code handles unsupported capabilities gracefully without crashing
3. All models work for basic text-only scenarios

Run with: pytest tests/test_llm_model_capabilities.py -m integration
to run a single test use: pytest -s "tests/test_llm_model_capabilities.py::test_text_only_chat[openai-gpt-4o]" -m integration
"""

import json
import logging
import os
from pathlib import Path
from typing import Generator, List, Tuple, Union
from unittest.mock import MagicMock, patch

import psycopg2
import psycopg2.extras
import pytest
import requests
from dotenv import load_dotenv
from pytest import mark

# IMPORTANT: Set test database URL BEFORE any imports that load settings
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_db"

from app.models import LLMModel  # noqa: E402
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS  # noqa: E402
from app.services.anthropic_service import AnthropicService  # noqa: E402
from app.services.base_llm_service import FileAttachmentData  # noqa: E402
from app.services.chat_models import (  # noqa: E402
    StreamContentEvent,
    StreamDoneEvent,
    StreamErrorEvent,
)
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS  # noqa: E402
from app.services.grok_service import GrokService  # noqa: E402
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS  # noqa: E402
from app.services.openai_service import OpenAIService  # noqa: E402
from app.services.summarizer_service import SummarizerService  # noqa: E402

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# Test constants
TEST_MESSAGE = "Please analyze this content and provide feedback."
TEST_DB_NAME = "test_db"
TEST_FILES_DIR = Path(__file__).parent / "data"


class LLMCapabilityTester:
    """Test LLM model capabilities with a clean test database."""

    def __init__(self) -> None:
        """Initialize with test database configuration."""
        self.test_db_name = TEST_DB_NAME
        self.pg_config = {
            "host": "localhost",
            "port": 5432,
            "database": self.test_db_name,
            "user": "postgres",
            "password": "postgres",
        }
        self.test_user_id: int = 0
        self.test_conversation_id: int = 0
        self.test_project_draft_id: int = 0

    def setup_test_database(self) -> None:
        """Setup test database with clean data (fresh database created by Makefile)."""
        self.cleanup_test_database()

        # Create test data
        self.create_test_data()

    def create_test_data(self) -> None:
        """Create minimal test data for LLM capability testing."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[call-overload]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Create test user
                cursor.execute(
                    """
                    INSERT INTO users (google_id, email, name, is_active, created_at, updated_at)
                    VALUES ('test_llm_user', 'llm@test.com', 'LLM Test User', true, NOW(), NOW())
                    RETURNING id
                """
                )
                self.test_user_id = cursor.fetchone()["id"]

                # Create test conversation
                cursor.execute(
                    """
                    INSERT INTO conversations (
                        url, title, import_date, imported_chat,
                        created_at, updated_at, imported_by_user_id
                    )
                    VALUES (
                        'https://test.com/llm-conversation',
                        'LLM Capability Test Conversation',
                        NOW(),
                        %s,
                        NOW(),
                        NOW(),
                        %s
                    )
                    RETURNING id
                """,
                    [
                        json.dumps([{"role": "user", "content": "Test conversation content"}]),
                        self.test_user_id,
                    ],
                )
                self.test_conversation_id = cursor.fetchone()["id"]

                # Create project draft
                cursor.execute(
                    """
                    INSERT INTO project_drafts (conversation_id, created_by_user_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    RETURNING id
                """,
                    [self.test_conversation_id, self.test_user_id],
                )
                self.test_project_draft_id = cursor.fetchone()["id"]

                # Create project draft version
                cursor.execute(
                    """
                    INSERT INTO project_draft_versions (
                        project_draft_id, title, description,
                        is_manual_edit, version_number, created_by_user_id, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """,
                    [
                        self.test_project_draft_id,
                        "Test Project Draft",
                        "A test project draft for validating LLM model capabilities",
                        False,
                        1,
                        self.test_user_id,
                    ],
                )
                version_id = cursor.fetchone()["id"]

                # Set active version
                cursor.execute(
                    """
                    UPDATE project_drafts SET active_version_id = %s WHERE id = %s
                """,
                    [version_id, self.test_project_draft_id],
                )

                conn.commit()

    def cleanup_test_database(self) -> None:
        """Clean test database by truncating all tables."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[call-overload]
            with conn.cursor() as cursor:
                # Clear all test data efficiently
                cursor.execute(
                    "TRUNCATE TABLE users, conversations, project_drafts, project_draft_versions, chat_messages, file_attachments RESTART IDENTITY CASCADE"
                )
                conn.commit()


@pytest.fixture(scope="module")
def capability_tester() -> Generator[LLMCapabilityTester, None, None]:
    """Create and setup test environment for LLM capability testing."""
    tester = LLMCapabilityTester()
    tester.setup_test_database()

    yield tester

    # Cleanup
    tester.cleanup_test_database()


@pytest.fixture
def mock_s3_service() -> Generator[MagicMock, None, None]:
    """Mock S3 service to avoid actual file uploads during testing."""

    def mock_generate_download_url(s3_key: str) -> str:
        return "https://bci-public-resources.s3.us-west-1.amazonaws.com/message.png"

    def mock_download_file_content(s3_key: str) -> bytes:
        # Return correct bytes based on requested key (PDF vs image)
        if s3_key.endswith(".pdf") or "pdf" in s3_key:
            return (TEST_FILES_DIR / "a_pdf.pdf").read_bytes()
        # Default to real public image bytes for images/others
        url = "https://bci-public-resources.s3.us-west-1.amazonaws.com/message.png"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.content

    # Create a strict mock that will fail if unexpected methods are called
    from app.services.s3_service import S3Service

    mock_s3 = MagicMock(spec=S3Service)
    mock_s3.download_file_content.side_effect = mock_download_file_content
    mock_s3.generate_download_url.side_effect = mock_generate_download_url

    # Mock the PDF processing function directly to return test text
    def mock_format_pdf_content(
        pdf_files: List[FileAttachmentData], s3_service: MagicMock, pdf_service: MagicMock
    ) -> str:
        if not pdf_files:
            return ""
        return "\n\n--- PDF Documents ---\n\n**test_document.pdf:**\nThis is a test PDF document containing sample text for LLM model capability testing, the LLM is supposed to extract the key 'asa12143'.\n\n"

    # Add fail-fast functions that will raise exceptions if real S3 service is called
    def fail_fast_get_s3_service() -> None:
        raise Exception(
            "❌ MOCK FAILURE: Real get_s3_service() was called instead of mock! Check your patch targets."
        )

    # Use context managers for cleaner patch management
    with (
        patch("app.services.s3_service.get_s3_service", side_effect=fail_fast_get_s3_service),
        patch("app.services.openai.chat_with_project_draft.get_s3_service", return_value=mock_s3),
        patch("app.services.anthropic_service.get_s3_service", return_value=mock_s3),
        patch(
            "app.services.openai.chat_with_project_draft.format_pdf_content_for_context",
            side_effect=mock_format_pdf_content,
        ),
        patch(
            "app.services.prompts.format_pdf_content_for_context",
            side_effect=mock_format_pdf_content,
        ),
    ):
        yield mock_s3


def _get_test_file_content(s3_key: str) -> bytes:
    """Get test file content based on S3 key."""
    if "pdf" in s3_key or s3_key.endswith(".pdf"):
        # Read the actual test PDF file
        return (TEST_FILES_DIR / "a_pdf.pdf").read_bytes()
    raise ValueError(f"Unknown file type: {s3_key}")


# Collect all models from all providers
ALL_MODELS: List[Tuple[str, LLMModel]] = []
for provider, models in [
    ("openai", OPENAI_MODELS),
    ("anthropic", ANTHROPIC_MODELS),
    ("grok", GROK_MODELS),
]:
    for model in models:
        ALL_MODELS.append((provider, model))


def _generate_model_ids(models: List[Tuple[str, LLMModel]]) -> List[str]:
    """Generate descriptive test IDs for model parameters."""
    return [f"{provider}-{model.id}" for provider, model in models]


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize("provider,model", ALL_MODELS, ids=_generate_model_ids(ALL_MODELS))
async def test_text_only_chat(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Test basic text-only chat functionality - should always work."""
    print(f"\n🧪 Testing text-only chat: {provider}/{model.id}")

    # Check API key availability
    _check_api_key_available(provider)

    service = _get_service(provider)

    try:
        # Test basic text-only streaming chat
        events = []
        full_content = ""
        async for event in service.chat_with_project_draft_stream(
            llm_model=model,
            conversation_id=capability_tester.test_conversation_id,
            project_draft_id=capability_tester.test_project_draft_id,
            user_message=TEST_MESSAGE,
            chat_history=[],
            attached_files=[],
            user_id=capability_tester.test_user_id,
        ):
            events.append(event)
            if isinstance(event, StreamContentEvent):
                full_content += event.data
            # Let stream complete naturally to see full response
            if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
                break

        # Print actual content for debugging
        print(f"📄 Content received ({len(full_content)} chars): {full_content}")

        # Validate we got a proper response
        content_events = [e for e in events if isinstance(e, StreamContentEvent)]
        error_events = [e for e in events if isinstance(e, StreamErrorEvent)]

        print(f"📊 Events: {len(content_events)} content, {len(error_events)} errors")
        if error_events:
            print(f"❌ Errors: {error_events}")

        assert len(content_events) > 0, f"Expected content events for {provider}/{model.id}"

        # Validate no errors occurred
        assert (
            len(error_events) == 0
        ), f"Unexpected error events for {provider}/{model.id}: {error_events}"

        print(f"✅ Text-only chat works for {provider}/{model.id}")

    except Exception as e:
        pytest.fail(f"Text-only chat failed for {provider}/{model.id}: {str(e)}")


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize("provider,model", ALL_MODELS, ids=_generate_model_ids(ALL_MODELS))
async def test_tool_call_support(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Validate that the model can perform a tool call to update_project_draft."""
    print(f"\n🧪 Testing tool call support: {provider}/{model.id}")

    _check_api_key_available(provider)

    service = _get_service(provider)

    # # Patch internals so we can assert on the DB tool callback without a real DB
    # # We patch inside the target modules where they're looked up
    # from app.services.anthropic_service import AnthropicService as _AnthropicService  # type: ignore
    # from app.services.openai import chat_with_project_draft as openai_cwpd  # type: ignore

    update_called = {"called": False, "title": "", "description": ""}

    def fake_create_project_draft_version(
        project_draft_id: int,
        title: str,
        description: str,
        is_manual_edit: bool,
        created_by_user_id: int,
    ) -> None:
        update_called["called"] = True
        update_called["title"] = title
        update_called["description"] = description

    # Build a very explicit user instruction to invoke the tool
    user_prompt = (
        "I am testing your tool functionality so please call the update_project_draft tool "
        "with the title 'testTitle4' and decription 'testDescription2'"
    )

    # Use context managers for patching the database accessor used by services
    with (
        patch("app.services.openai.chat_with_project_draft.get_database") as mock_get_db,
        patch("app.services.anthropic_service.get_database") as mock_get_db_anthropic,
        patch(
            "app.services.openai.chat_with_project_draft.get_chat_system_prompt",
            return_value="system",
        ),
        patch("app.services.anthropic_service.get_chat_system_prompt", return_value="system"),
    ):
        db_mock = MagicMock()
        db_mock.create_project_draft_version.side_effect = fake_create_project_draft_version
        db_mock.get_project_draft_by_conversation_id.return_value = {
            "id": capability_tester.test_project_draft_id
        }

        mock_get_db.return_value = db_mock
        mock_get_db_anthropic.return_value = db_mock

        # Drive a minimal chat stream and let the model/tooling decide
        events = []
        async for event in service.chat_with_project_draft_stream(
            llm_model=model,
            conversation_id=capability_tester.test_conversation_id,
            project_draft_id=capability_tester.test_project_draft_id,
            user_message=user_prompt,
            chat_history=[],
            attached_files=[],
            user_id=capability_tester.test_user_id,
        ):
            events.append(event)
            if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
                break

    assert update_called["called"], f"Tool was not invoked by {provider}/{model.id}"
    assert update_called["title"] == "testTitle4"
    assert update_called["description"] == "testDescription2"


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize(
    "provider,model",
    [(p, m) for p, m in ALL_MODELS if m.supports_images],
    ids=_generate_model_ids([(p, m) for p, m in ALL_MODELS if m.supports_images]),
)
async def test_image_support(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Test image attachments with models that claim to support images."""
    print(f"\n🧪 Testing image support (positive): {provider}/{model.id}")

    # Check API key availability
    _check_api_key_available(provider)

    service = _get_service(provider)

    # Create mock image attachment
    image_attachment = FileAttachmentData(
        id=1,
        filename="test_image.png",
        file_type="image/png",
        file_size=1024,
        created_at=None,  # type: ignore
        chat_message_id=1,
        conversation_id=capability_tester.test_conversation_id,
        s3_key="test/image.png",
    )
    events = []
    full_content = ""
    async for event in service.chat_with_project_draft_stream(
        llm_model=model,
        conversation_id=capability_tester.test_conversation_id,
        project_draft_id=capability_tester.test_project_draft_id,
        user_message="What do you see in this image?",
        chat_history=[],
        attached_files=[image_attachment],
        user_id=capability_tester.test_user_id,
    ):
        events.append(event)
        if isinstance(event, StreamContentEvent):
            full_content += event.data
        # Let stream complete naturally to see full response
        if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
            break

    # Print actual content for debugging
    print(f"📄 Image content received ({len(full_content)} chars): {full_content}")

    # Validate response
    content_events = [e for e in events if isinstance(e, StreamContentEvent)]
    error_events = [e for e in events if isinstance(e, StreamErrorEvent)]

    print(f"📊 Events: {len(content_events)} content, {len(error_events)} errors")
    if error_events:
        print(f"❌ Errors: {error_events}")

    # Should work without errors
    assert len(error_events) == 0, f"Image support failed for {provider}/{model.id}: {error_events}"

    assert len(content_events) > 0, f"No content generated for image with {provider}/{model.id}"

    print(f"✅ Image support works for {provider}/{model.id}")


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize(
    "provider,model",
    [(p, m) for p, m in ALL_MODELS if not m.supports_images],
    ids=_generate_model_ids([(p, m) for p, m in ALL_MODELS if not m.supports_images]),
)
async def test_image_support_for_models_that_dont_support_images(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Test image attachments with models that don't support images"""
    print(f"\n🧪 Testing image support (negative): {provider}/{model.id}")

    # Check API key availability
    _check_api_key_available(provider)

    service = _get_service(provider)

    # Create mock image attachment
    image_attachment = FileAttachmentData(
        id=1,
        filename="test_image.png",
        file_type="image/png",
        file_size=1024,
        created_at=None,  # type: ignore
        chat_message_id=1,
        conversation_id=capability_tester.test_conversation_id,
        s3_key="test/image.png",
    )

    events = []
    full_content = ""
    async for event in service.chat_with_project_draft_stream(
        llm_model=model,
        conversation_id=capability_tester.test_conversation_id,
        project_draft_id=capability_tester.test_project_draft_id,
        user_message="What do you see in this image?",
        chat_history=[],
        attached_files=[image_attachment],
        user_id=capability_tester.test_user_id,
    ):
        events.append(event)
        if isinstance(event, StreamContentEvent):
            full_content += event.data
        # Let stream complete naturally to see full response
        if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
            break

    # Print actual content for debugging
    print(f"📄 Image content received ({len(full_content)} chars): {full_content}")

    # Analyze what happened
    content_events = [e for e in events if isinstance(e, StreamContentEvent)]
    error_events = [e for e in events if isinstance(e, StreamErrorEvent)]

    print(f"📊 Events: {len(content_events)} content, {len(error_events)} errors")
    if error_events:
        print(f"⚠️ Errors: {error_events}")
    assert len(error_events) > 0, f"Image support failed for {provider}/{model.id}: {error_events}"


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize(
    "provider,model",
    [(p, m) for p, m in ALL_MODELS if m.supports_pdfs],
    ids=_generate_model_ids([(p, m) for p, m in ALL_MODELS if m.supports_pdfs]),
)
async def test_pdf_support(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Test PDF attachments with models that claim to support PDFs."""
    print(f"\n🧪 Testing PDF support (positive): {provider}/{model.id}")

    # Check API key availability
    _check_api_key_available(provider)

    service = _get_service(provider)

    # Create mock PDF attachment
    pdf_attachment = FileAttachmentData(
        id=1,
        filename="test_document.pdf",
        file_type="application/pdf",
        file_size=2048,
        created_at=None,  # type: ignore
        chat_message_id=1,
        conversation_id=capability_tester.test_conversation_id,
        s3_key="test/document.pdf",
    )

    events = []
    full_content = ""
    async for event in service.chat_with_project_draft_stream(
        llm_model=model,
        conversation_id=capability_tester.test_conversation_id,
        project_draft_id=capability_tester.test_project_draft_id,
        user_message="Please read this attached PDF document, and reply with the key.",
        chat_history=[],
        attached_files=[pdf_attachment],
        user_id=capability_tester.test_user_id,
    ):
        events.append(event)
        if isinstance(event, StreamContentEvent):
            full_content += event.data
        # Let stream complete naturally to see full response
        if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
            break

    # Print actual content for debugging
    print(f"📄 PDF content received ({len(full_content)} chars): {full_content}")

    # Validate response
    content_events = [e for e in events if isinstance(e, StreamContentEvent)]
    error_events = [e for e in events if isinstance(e, StreamErrorEvent)]

    print(f"📊 Events: {len(content_events)} content, {len(error_events)} errors")
    if error_events:
        print(f"❌ Errors: {error_events}")

    # Should work without errors
    assert len(error_events) == 0, f"PDF support failed for {provider}/{model.id}: {error_events}"

    assert len(content_events) > 0, f"No content generated for PDF with {provider}/{model.id}"

    print(f"✅ PDF support works for {provider}/{model.id}")


@mark.integration  # Skip in CI unless --integration flag
@mark.parametrize(
    "provider,model",
    [(p, m) for p, m in ALL_MODELS if not m.supports_pdfs],
    ids=_generate_model_ids([(p, m) for p, m in ALL_MODELS if not m.supports_pdfs]),
)
async def test_pdf_support_for_models_that_dont_support_pdfs(
    capability_tester: LLMCapabilityTester,
    mock_s3_service: MagicMock,
    provider: str,
    model: LLMModel,
) -> None:
    """Test PDF attachments with models that don't support PDFs"""
    print(f"\n🧪 Testing PDF support (negative): {provider}/{model.id}")

    # Check API key availability
    _check_api_key_available(provider)

    service = _get_service(provider)

    # Create mock PDF attachment
    pdf_attachment = FileAttachmentData(
        id=1,
        filename="test_document.pdf",
        file_type="application/pdf",
        file_size=2048,
        created_at=None,  # type: ignore
        chat_message_id=1,
        conversation_id=capability_tester.test_conversation_id,
        s3_key="test/document.pdf",
    )

    events = []
    full_content = ""
    async for event in service.chat_with_project_draft_stream(
        llm_model=model,
        conversation_id=capability_tester.test_conversation_id,
        project_draft_id=capability_tester.test_project_draft_id,
        user_message="Please summarize this PDF document.",
        chat_history=[],
        attached_files=[pdf_attachment],
        user_id=capability_tester.test_user_id,
    ):
        events.append(event)
        if isinstance(event, StreamContentEvent):
            full_content += event.data
        # Let stream complete naturally to see full response
        if isinstance(event, (StreamDoneEvent, StreamErrorEvent)):
            break

    # Print actual content for debugging
    print(f"📄 PDF content received ({len(full_content)} chars): {full_content}")

    # Analyze what happened
    content_events = [e for e in events if isinstance(e, StreamContentEvent)]
    error_events = [e for e in events if isinstance(e, StreamErrorEvent)]

    print(f"📊 Events: {len(content_events)} content, {len(error_events)} errors")
    if error_events:
        print(f"⚠️ Errors: {error_events}")

    assert len(error_events) > 0, f"PDF support failed for {provider}/{model.id}: {error_events}"


def _check_api_key_available(provider: str) -> None:
    """Check if required API key is available, fail fast if not."""
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "grok": "XAI_API_KEY",
    }

    required_key = key_map.get(provider)
    if not required_key:
        pytest.fail(f"Unknown provider: {provider}")

    if not os.getenv(required_key):
        pytest.fail(f"Missing required environment variable: {required_key}")


def _get_service(provider: str) -> Union[OpenAIService, AnthropicService, GrokService]:
    """Get the appropriate service instance for the provider."""
    if provider == "openai":
        return OpenAIService(SummarizerService())
    elif provider == "anthropic":
        return AnthropicService(SummarizerService())
    elif provider == "grok":
        return GrokService(SummarizerService())
    else:
        raise ValueError(f"Unknown provider: {provider}")


if __name__ == "__main__":
    """Allow running the test file directly for development."""
    pytest.main([__file__, "--integration"])
