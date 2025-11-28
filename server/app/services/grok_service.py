"""Grok service implemented via the OpenAI LangChain service."""

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import settings
from app.models import LLMModel
from app.services import SummarizerService
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    LLMModel(
        id="grok-code-fast-1",
        provider="grok",
        label="Grok Code Fast 1",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=256_000,
    ),
    LLMModel(
        id="grok-4-0709",
        provider="grok",
        label="Grok 4 0709",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=256_000,
    ),
    LLMModel(
        id="grok-3",
        provider="grok",
        label="Grok 3",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=131_000,
    ),
    LLMModel(
        id="grok-3-mini",
        provider="grok",
        label="Grok 3 Mini",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=131_000,
    ),
]


class GrokService(OpenAIService):
    """Service for interacting with xAI's Grok API using the OpenAI-compatible path."""

    def __init__(self, *, summarizer_service: SummarizerService) -> None:
        self._xai_api_key = settings.XAI_API_KEY
        if not self._xai_api_key:
            raise ValueError("XAI_API_KEY environment variable is required")
        super().__init__(summarizer_service=summarizer_service)

    def _build_chat_model(self, *, model_id: str) -> ChatOpenAI:
        logger.info("Initializing Grok model '%s'", model_id)
        return ChatOpenAI(
            model=model_id,
            api_key=SecretStr(self._xai_api_key),
            base_url="https://api.x.ai/v1",
            temperature=0,
            streaming=True,
        )

    def get_context_window_tokens(self, llm_model: str) -> int:
        for model in SUPPORTED_MODELS:
            if model.id == llm_model:
                return model.context_window_tokens
        raise ValueError(f"Unknown Grok model for context window: {llm_model}")
