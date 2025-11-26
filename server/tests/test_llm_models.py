#!/usr/bin/env python3
"""
Basic capability tests for non-chat model methods across all providers.

Covers:
- generate_project_draft (streaming, text-only)
- summarize_document (non-streaming)
- summarize_image (non-streaming, only for models with supports_images)

These are marked as integration tests and require real API keys.
"""

import os
from pathlib import Path
from typing import List, Tuple, Union

import pytest
from dotenv import load_dotenv
from pytest import mark

from app.models import LLMModel
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.anthropic_service import AnthropicService
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.grok_service import GrokService
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS
from app.services.openai_service import OpenAIService
from app.services.summarizer_service import SummarizerService


# Ensure tests don't fail due to missing conversation memories
@pytest.fixture(autouse=True)
def _patch_mem0_memories(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.mem0_service import Mem0Service

    def _fake_retrieve(self: Mem0Service, conversation_id: int) -> str:
        return (
            "1. Testing context: evaluating provider models for project draft generation\n"
            "2. Project scope: transform short chats into structured drafts\n"
            "3. Constraints: concise, information-dense output; stream-friendly"
        )

    monkeypatch.setattr(
        Mem0Service,
        "retrieve_project_creation_memories",
        _fake_retrieve,
        raising=True,
    )


# IMPORTANT: Set test database URL BEFORE any imports that load settings
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_db"

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")


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
    return [f"{provider}-{model.id}" for provider, model in models]


def _check_api_key_available(provider: str) -> None:
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
    if provider == "openai":
        return OpenAIService(summarizer_service=SummarizerService())
    if provider == "anthropic":
        return AnthropicService(summarizer_service=SummarizerService())
    if provider == "grok":
        return GrokService(summarizer_service=SummarizerService())
    raise ValueError(f"Unknown provider: {provider}")


@mark.integration
@mark.parametrize("provider,model", ALL_MODELS, ids=_generate_model_ids(ALL_MODELS))
async def test_generate_project_draft_basic(provider: str, model: LLMModel) -> None:
    """Ensure generate_project_draft streams at least one chunk for every model."""
    print(f"\n🧪 Testing generate_project_draft: {provider}/{model.id}")
    _check_api_key_available(provider)
    service = _get_service(provider)

    chunks: List[str] = []
    async for piece in service.generate_project_draft(
        llm_model=model.id,
        conversation_text="Short conversation for generating a project draft.",
        user_id=0,
        conversation_id=0,
    ):
        chunks.append(piece)

    combined = "".join(chunks)
    print(f"📄 Draft received ({len(combined)} chars): {combined}")
    assert len(chunks) > 0, f"No chunks streamed for {provider}/{model.id}"


@mark.integration
@mark.parametrize("provider,model", ALL_MODELS, ids=_generate_model_ids(ALL_MODELS))
async def test_summarize_document_basic(provider: str, model: LLMModel) -> None:
    """Ensure summarize_document returns non-empty text for every model."""
    print(f"\n🧪 Testing summarize_document: {provider}/{model.id}")
    _check_api_key_available(provider)
    service = _get_service(provider)

    summary = await service.summarize_document(
        llm_model=model,
        content="""
        Artificial General Intelligence (AGI) represents a significant milestone in the field of computer science and artificial intelligence. Unlike narrow AI systems that excel at specific tasks such as image recognition or natural language processing, AGI aims to create machines that possess human-level cognitive abilities across a wide range of domains.

        The development of AGI involves several key challenges. First, researchers must address the problem of knowledge representation and reasoning. Current AI systems often struggle with common-sense reasoning and the ability to transfer knowledge from one domain to another. Second, AGI systems must be capable of learning efficiently from limited data, much like humans do. This requires advances in few-shot learning and meta-learning techniques.

        Another critical aspect is the development of robust and safe AI systems. As AGI systems become more powerful, ensuring their alignment with human values and preventing unintended consequences becomes paramount. This has led to increased research in AI safety, interpretability, and control mechanisms.

        The timeline for achieving AGI remains uncertain, with experts providing estimates ranging from decades to potentially never. However, recent advances in large language models, multimodal AI, and reinforcement learning have accelerated progress in the field. Companies and research institutions worldwide are investing heavily in AGI research, recognizing its potential to revolutionize industries and solve complex global challenges.

        The implications of successfully developing AGI are profound, potentially affecting every aspect of human society, from healthcare and education to economic systems and governance structures.
        """.strip(),
    )
    print(f"📄 Summary ({len(summary)} chars): {summary}")
    assert isinstance(summary, str)
    assert summary.strip() != "", f"Empty summary for {provider}/{model.id}"


@mark.integration
@mark.parametrize(
    "provider,model",
    [(p, m) for p, m in ALL_MODELS if m.supports_images],
    ids=_generate_model_ids([(p, m) for p, m in ALL_MODELS if m.supports_images]),
)
async def test_summarize_image_basic(provider: str, model: LLMModel) -> None:
    """Ensure summarize_image returns non-empty text for models that support images."""
    print(f"\n🧪 Testing summarize_image: {provider}/{model.id}")
    _check_api_key_available(provider)
    service = _get_service(provider)

    image_url = "https://bci-public-resources.s3.us-west-1.amazonaws.com/message.png"
    caption = await service.summarize_image(
        llm_model=model,
        image_url=image_url,
    )
    print(f"📄 Caption ({len(caption)} chars): {caption}")
    assert isinstance(caption, str)
    assert caption.strip() != "", f"Empty image caption for {provider}/{model.id}"
