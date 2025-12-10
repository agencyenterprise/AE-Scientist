from app.api.llm_providers import LLM_PROVIDER_REGISTRY
from app.config import settings


def _validate_llm_pricing() -> None:
    """Validate that all models in the registry have pricing information."""
    pricing_data = settings.LLM_PRICING._pricing_data

    for provider, config in LLM_PROVIDER_REGISTRY.items():
        for model_id in config.models_by_id:
            if model_id not in pricing_data:
                raise ValueError(
                    f"Model '{model_id}' from provider '{provider}' not found in pricing information."
                )


def validate_configuration() -> None:
    """Run all configuration validation checks."""
    _validate_llm_pricing()
