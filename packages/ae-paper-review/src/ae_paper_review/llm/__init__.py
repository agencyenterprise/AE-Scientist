"""LLM and VLM wrapper modules for paper review."""

from .anthropic import AnthropicPDFProvider
from .base import LLMProvider, Provider
from .google import GooglePDFProvider
from .openai import OpenAIPDFProvider
from .token_tracking import TokenUsage, TokenUsageDetail, TokenUsageSummary
from .xai import XAIPDFProvider

_PROVIDERS: dict[Provider, type[LLMProvider]] = {
    Provider.ANTHROPIC: AnthropicPDFProvider,
    Provider.OPENAI: OpenAIPDFProvider,
    Provider.XAI: XAIPDFProvider,
    Provider.GOOGLE: GooglePDFProvider,
}


def get_provider(provider: Provider, model: str, usage: TokenUsage) -> LLMProvider:
    """Get the LLM provider instance.

    Args:
        provider: The provider enum value
        model: The model name (e.g., "claude-sonnet-4-20250514")
        usage: Token usage tracker for all LLM calls

    Returns:
        LLMProvider instance
    """
    provider_class = _PROVIDERS[provider]
    return provider_class(model=model, usage=usage)


__all__ = [
    "LLMProvider",
    "Provider",
    "get_provider",
    "TokenUsage",
    "TokenUsageDetail",
    "TokenUsageSummary",
]
