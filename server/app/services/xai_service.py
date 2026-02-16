"""xAI service implemented via the OpenAI LangChain service."""

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import settings
from app.models import LLMModel
from app.services.langchain_llm_service import LangChainLLMService
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    LLMModel(
        id="grok-4-1-fast-reasoning",
        provider="xai",
        label="Grok 4.1 Fast Reasoning",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=2_000_000,
    ),
    LLMModel(
        id="grok-4-1-fast-non-reasoning",
        provider="xai",
        label="Grok 4.1 Fast Non Reasoning",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=2_000_000,
    ),
    LLMModel(
        id="grok-4-fast-reasoning",
        provider="xai",
        label="Grok 4 Fast Reasoning",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=2_000_000,
    ),
    LLMModel(
        id="grok-4-fast-non-reasoning",
        provider="xai",
        label="Grok 4 Fast Non Reasoning",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=2_000_000,
    ),
    LLMModel(
        id="grok-4-0709",
        provider="xai",
        label="Grok 4",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=256_000,
    ),
]


class XAIService(OpenAIService):
    """Service for interacting with xAI's Grok API using the OpenAI-compatible path."""

    def __init__(self) -> None:
        self._xai_api_key = settings.xai_api_key
        if not self._xai_api_key:
            raise ValueError("XAI_API_KEY environment variable is required")
        LangChainLLMService.__init__(
            self,
            provider_name="xai",
            supported_models=SUPPORTED_MODELS,
        )

    def _build_chat_model(self, *, model_id: str) -> ChatOpenAI:
        logger.debug("Initializing xAI model '%s'", model_id)
        return ChatOpenAI(
            model=model_id,
            api_key=SecretStr(self._xai_api_key),
            base_url="https://api.x.ai/v1",
            temperature=0,
            streaming=True,
            stream_usage=True,
        )
