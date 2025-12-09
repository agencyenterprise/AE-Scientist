from typing import Dict, NamedTuple

from app.models import LLMModel
from app.services import AnthropicService, GrokService, OpenAIService
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.langchain_llm_service import LangChainLLMService
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS


class LLMProviderConfig(NamedTuple):
    service: LangChainLLMService
    models_by_id: Dict[str, LLMModel]


openai_service = OpenAIService()
anthropic_service = AnthropicService()
grok_service = GrokService()

LLM_PROVIDER_REGISTRY: Dict[str, LLMProviderConfig] = {
    "openai": LLMProviderConfig(
        service=openai_service,
        models_by_id={model.id: model for model in OPENAI_MODELS},
    ),
    "anthropic": LLMProviderConfig(
        service=anthropic_service,
        models_by_id={model.id: model for model in ANTHROPIC_MODELS},
    ),
    "grok": LLMProviderConfig(
        service=grok_service,
        models_by_id={model.id: model for model in GROK_MODELS},
    ),
}


def get_llm_service_by_provider(provider: str) -> LangChainLLMService:
    provider_config = LLM_PROVIDER_REGISTRY.get(provider)
    if not provider_config:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return provider_config.service
