from typing import Dict, NamedTuple

from langchain.chat_models import BaseChatModel
from langchain.chat_models.base import _parse_model

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


def get_llm_model_by_id(provider: str, model_id: str) -> LLMModel:
    provider_config = LLM_PROVIDER_REGISTRY.get(provider)
    if not provider_config:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return provider_config.models_by_id[model_id]


def extract_model_name_and_provider(model: str | BaseChatModel) -> tuple[str, str]:
    """Extract the model name and provider from a model.

    Handles 'provider:model' format (LangChain's native format) and plain model names.
    """
    if isinstance(model, BaseChatModel):
        model_attr = getattr(model, "model", None)
        if model_attr is None:
            model_attr = getattr(model, "model_name", None)
        if model_attr is None:
            raise ValueError(f"Model {model} has no model or model_name attribute")
        model_str = str(model_attr)
    else:
        model_str = model

    # Handle provider:model format (LangChain's native format)
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
        return model_name, provider

    # Fall back to LangChain's inference for plain model names
    return _parse_model(model_str, None)
