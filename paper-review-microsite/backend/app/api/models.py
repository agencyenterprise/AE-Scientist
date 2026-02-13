"""
Available models API endpoint.

Returns the list of available LLM models for paper reviews.
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(tags=["models"])


class ModelInfo(BaseModel):
    """Information about an available LLM model."""

    id: str = Field(..., description="Model identifier in provider:model format")
    provider: str = Field(..., description="LLM provider (anthropic, openai, xai)")
    name: str = Field(..., description="Human-readable model name")
    description: str = Field(..., description="Brief description of the model")


class ModelsResponse(BaseModel):
    """Response containing available models."""

    models: List[ModelInfo] = Field(..., description="List of available models")
    default: str = Field(..., description="Default model ID")


# Define available models - matching the main application
AVAILABLE_MODELS = [
    # Anthropic models
    ModelInfo(
        id="anthropic:claude-sonnet-4-5",
        provider="anthropic",
        name="Claude Sonnet 4.5",
        description="Anthropic's latest Claude Sonnet model - balanced performance and speed",
    ),
    ModelInfo(
        id="anthropic:claude-opus-4-5",
        provider="anthropic",
        name="Claude Opus 4.5",
        description="Anthropic's most capable model - highest quality reviews",
    ),
    ModelInfo(
        id="anthropic:claude-haiku-4-5",
        provider="anthropic",
        name="Claude Haiku 4.5",
        description="Fast and efficient model for quick reviews",
    ),
    # OpenAI models
    ModelInfo(
        id="openai:gpt-4o",
        provider="openai",
        name="GPT-4o",
        description="OpenAI's flagship multimodal model",
    ),
    ModelInfo(
        id="openai:gpt-4o-mini",
        provider="openai",
        name="GPT-4o Mini",
        description="Fast and cost-effective OpenAI model",
    ),
    ModelInfo(
        id="openai:gpt-4.1",
        provider="openai",
        name="GPT-4.1",
        description="OpenAI's GPT-4.1 with 1M context window",
    ),
    ModelInfo(
        id="openai:gpt-4.1-mini",
        provider="openai",
        name="GPT-4.1 Mini",
        description="Smaller GPT-4.1 variant",
    ),
    ModelInfo(
        id="openai:gpt-4.1-nano",
        provider="openai",
        name="GPT-4.1 Nano",
        description="Fastest GPT-4.1 variant",
    ),
    ModelInfo(
        id="openai:gpt-5",
        provider="openai",
        name="GPT-5",
        description="OpenAI's GPT-5 model",
    ),
    ModelInfo(
        id="openai:gpt-5.1",
        provider="openai",
        name="GPT-5.1",
        description="OpenAI's GPT-5.1 model",
    ),
    ModelInfo(
        id="openai:gpt-5-mini",
        provider="openai",
        name="GPT-5 Mini",
        description="Smaller GPT-5 variant",
    ),
    ModelInfo(
        id="openai:gpt-5-nano",
        provider="openai",
        name="GPT-5 Nano",
        description="Fastest GPT-5 variant",
    ),
    ModelInfo(
        id="openai:gpt-5.2",
        provider="openai",
        name="GPT-5.2",
        description="OpenAI's latest GPT-5.2 model",
    ),
    ModelInfo(
        id="openai:o1",
        provider="openai",
        name="o1",
        description="OpenAI's reasoning model",
    ),
    ModelInfo(
        id="openai:o3",
        provider="openai",
        name="o3",
        description="OpenAI's advanced reasoning model",
    ),
    ModelInfo(
        id="openai:o3-mini",
        provider="openai",
        name="o3 Mini",
        description="Faster o3 variant",
    ),
    # xAI models
    ModelInfo(
        id="xai:grok-4-1-fast-reasoning",
        provider="xai",
        name="Grok 4.1 Fast Reasoning",
        description="xAI's Grok 4.1 with reasoning capabilities",
    ),
    ModelInfo(
        id="xai:grok-4-1-fast-non-reasoning",
        provider="xai",
        name="Grok 4.1 Fast",
        description="xAI's fast Grok 4.1 model",
    ),
    ModelInfo(
        id="xai:grok-4-fast-reasoning",
        provider="xai",
        name="Grok 4 Fast Reasoning",
        description="xAI's Grok 4 with reasoning capabilities",
    ),
    ModelInfo(
        id="xai:grok-4-fast-non-reasoning",
        provider="xai",
        name="Grok 4 Fast",
        description="xAI's fast Grok 4 model",
    ),
    ModelInfo(
        id="xai:grok-4-0709",
        provider="xai",
        name="Grok 4",
        description="xAI's Grok 4 base model",
    ),
]

DEFAULT_MODEL = "openai:gpt-5.2"


def _filter_available_models() -> List[ModelInfo]:
    """Filter models based on configured API keys."""
    available = []
    for model in AVAILABLE_MODELS:
        if model.provider == "anthropic" and settings.llm.anthropic_api_key:
            available.append(model)
        elif model.provider == "openai" and settings.llm.openai_api_key:
            available.append(model)
        elif model.provider == "xai" and settings.llm.xai_api_key:
            available.append(model)
    return available


@router.get("/models", response_model=ModelsResponse)
async def get_available_models() -> ModelsResponse:
    """
    Get list of available LLM models for paper reviews.

    Returns models based on which API keys are configured.
    """
    available = _filter_available_models()

    # Use first available model as default if the default isn't available
    default = DEFAULT_MODEL
    available_ids = [m.id for m in available]
    if default not in available_ids and available:
        default = available[0].id

    return ModelsResponse(
        models=available,
        default=default,
    )
