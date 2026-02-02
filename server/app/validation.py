from app.api.llm_providers import LLM_PROVIDER_REGISTRY
from app.config import settings


def _validate_llm_pricing() -> None:
    """Validate that all models in the registry have pricing information."""
    pricing_data = settings.LLM_PRICING._pricing_data

    for provider, config in LLM_PROVIDER_REGISTRY.items():
        for model_id in config.models_by_id:
            # Pricing data uses "provider:model" format
            pricing_key = f"{provider}:{model_id}"
            if pricing_key not in pricing_data:
                raise ValueError(f"Model '{pricing_key}' not found in pricing information.")


def validate_configuration() -> None:
    """Run all configuration validation checks."""
    _validate_llm_pricing()
