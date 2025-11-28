"""
Tests to ensure tool calling works for our LangChain services.

Includes:
- Deterministic unit coverage with a fake model.
- Optional real smoke tests that hit provider APIs (skipped unless RUN_LLM_SMOKE=1).
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.config import settings
from app.models import LLMModel
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.anthropic_service import AnthropicService
from app.services.chat_models import StreamContentEvent, StreamDoneEvent, StreamIdeaUpdateEvent
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.grok_service import GrokService
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS
from app.services.openai_service import OpenAIService

_SERVER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_SERVER_DIR / ".env", override=True)


class FakeChatModel:
    """Minimal async chat model stub that returns predetermined AIMessage objects."""

    def __init__(self, *, responses: Iterable[AIMessage]) -> None:
        self._responses: List[AIMessage] = list(responses)

    def bind_tools(self, tools: List[object]) -> "FakeChatModel":
        self._bound_tools = tools  # noqa: SLF001 - stored for debugging/testing
        return self

    def bind(self, **_: object) -> "FakeChatModel":
        return self

    async def ainvoke(self, *args: object, **kwargs: object) -> AIMessage:
        del args, kwargs
        if not self._responses:
            raise AssertionError("FakeChatModel received too many invocations")
        return self._responses.pop(0)


def _tool_call_responses() -> List[AIMessage]:
    """Build the two-response sequence: tool call, then final content."""
    tool_arguments = json.dumps(
        {
            "title": "Smoke Title",
            "short_hypothesis": "Smoke hypothesis",
            "related_work": "Smoke related work",
            "abstract": "Smoke abstract",
            "experiments": ["E1"],
            "expected_outcome": "Smoke outcome",
            "risk_factors_and_limitations": ["Risk"],
        }
    )
    tool_message = AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "update_idea",
                        "arguments": tool_arguments,
                    },
                }
            ]
        },
    )
    final_message = AIMessage(content="Final response")
    return [tool_message, final_message]


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    env_attr: str
    service_factory: type
    model: LLMModel


PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        provider="openai",
        env_attr="OPENAI_API_KEY",
        service_factory=OpenAIService,
        model=OPENAI_MODELS[0],
    ),
    ProviderConfig(
        provider="anthropic",
        env_attr="ANTHROPIC_API_KEY",
        service_factory=AnthropicService,
        model=ANTHROPIC_MODELS[0],
    ),
    ProviderConfig(
        provider="grok",
        env_attr="XAI_API_KEY",
        service_factory=GrokService,
        model=GROK_MODELS[0],
    ),
]


def _fake_summarizer() -> MagicMock:
    summarizer = MagicMock()
    summarizer.get_chat_summary = AsyncMock(return_value=("", []))
    return summarizer


@dataclass(frozen=True)
class RealProviderConfig:
    provider: str
    env_var: str
    settings_attr: str
    service_factory: type
    model: LLMModel


def _find_model(models: List[LLMModel], model_id: str) -> LLMModel:
    for model in models:
        if model.id == model_id:
            return model
    raise ValueError(f"Model '{model_id}' not found.")


REAL_SMOKE_PROVIDERS: List[RealProviderConfig] = [
    RealProviderConfig(
        provider="openai",
        env_var="OPENAI_API_KEY",
        settings_attr="OPENAI_API_KEY",
        service_factory=OpenAIService,
        model=_find_model(OPENAI_MODELS, "gpt-4o"),
    ),
    RealProviderConfig(
        provider="grok",
        env_var="XAI_API_KEY",
        settings_attr="XAI_API_KEY",
        service_factory=GrokService,
        model=_find_model(GROK_MODELS, "grok-4-0709"),
    ),
    RealProviderConfig(
        provider="anthropic",
        env_var="ANTHROPIC_API_KEY",
        settings_attr="ANTHROPIC_API_KEY",
        service_factory=AnthropicService,
        model=_find_model(ANTHROPIC_MODELS, "claude-3-5-haiku-20241022"),
    ),
]


SMOKE_TEST_ENABLED = os.getenv("RUN_LLM_SMOKE") == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("config", PROVIDERS, ids=lambda cfg: cfg.provider)
async def test_chat_with_idea_invokes_update_tool(config: ProviderConfig) -> None:
    """Each provider should successfully execute the update_idea tool."""

    setattr(settings, config.env_attr, "test-key")

    service = config.service_factory(summarizer_service=_fake_summarizer())
    fake_model = FakeChatModel(responses=_tool_call_responses())
    with (
        patch("app.services.langchain_llm_service.get_s3_service", return_value=MagicMock()),
        patch("app.services.langchain_llm_service.PDFService", return_value=MagicMock()),
        patch("app.services.langchain_llm_service.get_database") as mock_get_db,
        patch.object(service, "get_or_create_model", return_value=fake_model),
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.create_idea_version = MagicMock()
        mock_get_db.return_value = db

        events: List[object] = []
        async for event in service.chat_with_idea_stream(
            llm_model=config.model,
            conversation_id=11,
            idea_id=22,
            user_message="Please use the tool.",
            chat_history=[],
            attached_files=[],
            user_id=33,
        ):
            events.append(event)

    db.create_idea_version.assert_called_once()
    kwargs = db.create_idea_version.call_args.kwargs
    assert kwargs["title"] == "Smoke Title"
    assert kwargs["short_hypothesis"] == "Smoke hypothesis"
    assert kwargs["created_by_user_id"] == 33

    assert any(isinstance(event, StreamIdeaUpdateEvent) for event in events)
    assert any(isinstance(event, StreamContentEvent) for event in events)
    done_events = [event for event in events if isinstance(event, StreamDoneEvent)]
    assert done_events, "Expected StreamDoneEvent"
    assert done_events[0].data.assistant_response == "Final response"


class UpdateIdeaToolArgs(BaseModel):
    title: str
    short_hypothesis: str
    related_work: str
    abstract: str
    experiments: List[str]
    expected_outcome: str
    risk_factors_and_limitations: List[str]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(
    not SMOKE_TEST_ENABLED,
    reason="Set RUN_LLM_SMOKE=1 (and provider API keys) to run real LLM smoke tests.",
)
@pytest.mark.parametrize("config", REAL_SMOKE_PROVIDERS, ids=lambda cfg: cfg.provider)
async def test_llm_tool_calls_real_smoke(config: RealProviderConfig) -> None:
    """Optional paid smoke test that verifies real providers emit tool calls."""

    api_key = os.getenv(config.env_var)
    if not api_key or api_key.strip().lower() in {"", "test", "fake"}:
        pytest.fail(
            f"{config.env_var} must be set to a real key when RUN_LLM_SMOKE=1 (missing for {config.provider})"
        )

    setattr(settings, config.settings_attr, api_key)

    expected_payload = {
        "title": "Smoke Title",
        "short_hypothesis": "Smoke hypothesis",
        "related_work": "Smoke related work",
        "abstract": "Smoke abstract",
        "experiments": ["Experiment A"],
        "expected_outcome": "Smoke outcome",
        "risk_factors_and_limitations": ["Risk"],
    }

    user_prompt = (
        "You are preparing an idea update for AE Scientist. "
        "You MUST call the `update_idea` tool exactly once using this JSON payload:\n"
        f"{json.dumps(expected_payload)}\n"
        "Do not include any assistant response outside of the tool call."
    )

    with (
        patch("app.services.langchain_llm_service.get_s3_service", return_value=MagicMock()),
        patch("app.services.langchain_llm_service.PDFService", return_value=MagicMock()),
        patch("app.services.langchain_llm_service.get_database") as mock_get_db,
    ):
        db = MagicMock()
        db.get_file_attachments_by_message_ids.return_value = []
        db.create_idea_version = MagicMock()
        mock_get_db.return_value = db

        service = config.service_factory(summarizer_service=_fake_summarizer())

        events: List[object] = []
        async for event in service.chat_with_idea_stream(
            llm_model=config.model,
            conversation_id=123,
            idea_id=456,
            user_message=user_prompt,
            chat_history=[],
            attached_files=[],
            user_id=1,
        ):
            events.append(event)

    db.create_idea_version.assert_called_once()
    kwargs = db.create_idea_version.call_args.kwargs
    for key, value in expected_payload.items():
        assert kwargs[key] == value, f"{config.provider} persisted {key} incorrectly"

    assert any(isinstance(event, StreamIdeaUpdateEvent) for event in events)
    done_events = [event for event in events if isinstance(event, StreamDoneEvent)]
    assert done_events, f"{config.provider} smoke test did not finish streaming"
