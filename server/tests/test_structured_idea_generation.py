import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncGenerator, List
from unittest.mock import MagicMock, patch

import pytest
from anthropic import BadRequestError as AnthropicBadRequestError
from dotenv import load_dotenv
from openai import BadRequestError as OpenAIBadRequestError

from app.api.conversations import _idea_sections_for_stream, _stream_structured_idea
from app.config import settings
from app.models import LLMModel
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.anthropic_service import AnthropicService
from app.services.base_llm_service import LLMIdeaGeneration
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.grok_service import GrokService
from app.services.langchain_llm_service import LangChainLLMService
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS
from app.services.openai_service import OpenAIService

RUN_LLM_SMOKE = os.getenv("RUN_LLM_SMOKE") == "1"
SMOKE_CONVERSATION = (
    "User: Let's extend retrieval augmented generation with a memory consolidation phase.\n"
    "Assistant: Explore nightly consolidation jobs that summarize the day's interactions."
)
_SERVER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_SERVER_DIR / ".env", override=True)


def _sample_payload() -> dict[str, Any]:
    return {
        "title": "Agentic Memory Consolidation",
        "short_hypothesis": "Combining episodic and semantic stores improves reasoning.",
        "related_work": "Builds on modern memory-augmented LLMs.",
        "abstract": "Longer description of the methodology and expectations.",
        "experiments": [
            "Experiment A: Measure retrieval quality after consolidation.",
            "Experiment B: Compare against naive rehearsal baselines.",
        ],
        "expected_outcome": "Consolidation reduces hallucinations by 30%.",
        "risk_factors_and_limitations": [
            "Risk: Overfitting to rehearsal data.",
            "Limitation: Requires expensive memory maintenance.",
        ],
    }


def _build_fake_stream(payload: str) -> AsyncGenerator[str, None]:
    async def _generator() -> AsyncGenerator[str, None]:
        yield payload

    return _generator()


def test_idea_sections_for_stream_formats_lists() -> None:
    idea = LLMIdeaGeneration(**_sample_payload())

    sections = _idea_sections_for_stream(idea=idea)
    combined = "".join(sections)

    assert "Title:\nAgentic Memory Consolidation" in combined
    assert "- Experiment A: Measure retrieval quality after consolidation." in combined
    assert "Risk Factors and Limitations" in combined


@pytest.mark.asyncio
async def test_stream_structured_idea_creates_new_idea() -> None:
    db = MagicMock()
    db.get_idea_by_conversation_id.return_value = None
    llm_service = MagicMock()
    llm_service._parse_idea_response.return_value = LLMIdeaGeneration(**_sample_payload())

    chunks: List[str] = []
    async for chunk in _stream_structured_idea(
        db=db,
        llm_service=llm_service,
        idea_stream=_build_fake_stream(json.dumps(_sample_payload())),
        conversation_id=1,
        user_id=2,
    ):
        chunks.append(chunk)

    db.create_idea.assert_called_once()
    db.update_idea_version.assert_not_called()
    assert chunks


@pytest.mark.asyncio
async def test_stream_structured_idea_updates_existing_idea() -> None:
    existing = SimpleNamespace(idea_id=11, version_id=22)
    db = MagicMock()
    db.get_idea_by_conversation_id.return_value = existing
    llm_service = MagicMock()
    llm_service._parse_idea_response.return_value = LLMIdeaGeneration(**_sample_payload())

    async for _ in _stream_structured_idea(
        db=db,
        llm_service=llm_service,
        idea_stream=_build_fake_stream(json.dumps(_sample_payload())),
        conversation_id=3,
        user_id=4,
    ):
        pass

    db.create_idea.assert_not_called()
    db.update_idea_version.assert_called_once_with(
        idea_id=existing.idea_id,
        version_id=existing.version_id,
        title=_sample_payload()["title"],
        short_hypothesis=_sample_payload()["short_hypothesis"],
        related_work=_sample_payload()["related_work"],
        abstract=_sample_payload()["abstract"],
        experiments=_sample_payload()["experiments"],
        expected_outcome=_sample_payload()["expected_outcome"],
        risk_factors_and_limitations=_sample_payload()["risk_factors_and_limitations"],
        is_manual_edit=False,
    )


def _find_model(models: List[LLMModel], model_id: str) -> LLMModel:
    for model in models:
        if model.id == model_id:
            return model
    raise ValueError(f"Model '{model_id}' not found.")


@dataclass(frozen=True)
class RealIdeaProviderConfig:
    provider: str
    env_var: str
    settings_attr: str
    service_factory: type[LangChainLLMService]
    model: LLMModel


REAL_PROVIDERS: List[RealIdeaProviderConfig] = [
    RealIdeaProviderConfig(
        provider="openai",
        env_var="OPENAI_API_KEY",
        settings_attr="OPENAI_API_KEY",
        service_factory=OpenAIService,
        model=_find_model(OPENAI_MODELS, "gpt-4o"),
    ),
    RealIdeaProviderConfig(
        provider="grok",
        env_var="XAI_API_KEY",
        settings_attr="XAI_API_KEY",
        service_factory=GrokService,
        model=_find_model(GROK_MODELS, "grok-4-0709"),
    ),
    RealIdeaProviderConfig(
        provider="anthropic",
        env_var="ANTHROPIC_API_KEY",
        settings_attr="ANTHROPIC_API_KEY",
        service_factory=AnthropicService,
        model=_find_model(ANTHROPIC_MODELS, "claude-3-5-haiku-20241022"),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("config", REAL_PROVIDERS, ids=lambda cfg: cfg.provider)
@pytest.mark.skipif(not RUN_LLM_SMOKE, reason="Set RUN_LLM_SMOKE=1 to run provider smoke tests.")
async def test_real_providers_emit_structured_ideas(config: RealIdeaProviderConfig) -> None:
    api_key = os.getenv(config.env_var)
    if not api_key:
        pytest.fail(f"{config.env_var} not configured")

    setattr(settings, config.settings_attr, api_key)
    service = config.service_factory(summarizer_service=MagicMock())  # type: ignore[call-arg]

    fake_db = MagicMock()
    fake_db.get_memories_block.return_value = SimpleNamespace(
        memories=[{"memory": "Connect ideas."}]
    )

    with patch("app.services.langchain_llm_service.get_database", return_value=fake_db):
        chunks: List[str] = []
        try:
            async for content_chunk in service.generate_idea(
                llm_model=config.model.id,
                conversation_text=SMOKE_CONVERSATION,
                _user_id=123,
                conversation_id=456,
            ):
                if content_chunk:
                    chunks.append(content_chunk)
        except AnthropicBadRequestError as exc:
            if config.provider == "anthropic" and "credit balance" in str(exc).lower():
                pytest.fail("Anthropic credits unavailable for smoke test")
            raise
        except OpenAIBadRequestError as exc:
            if config.provider == "grok" and "invalid request content" in str(exc).lower():
                pytest.fail("Grok API rejected payload; verify account access before running")
            raise

    assembled = "".join(chunks).strip()
    assert assembled, "Provider returned empty idea content"

    idea = service._parse_idea_response(content=assembled)
    assert idea.title
    assert idea.abstract
