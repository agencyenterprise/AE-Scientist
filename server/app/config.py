import json
import os
from typing import Dict, List

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _parse_price_map(raw_value: str) -> Dict[str, int]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    sanitized: Dict[str, int] = {}
    for key, value in parsed.items():
        try:
            sanitized[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return sanitized


class LLMPricing:
    """Provides access to LLM pricing information."""

    _pricing_data: Dict[str, Dict[str, int]]

    def __init__(self, raw_value: str):
        if not raw_value:
            raise ValueError(
                "JSON_MODEL_PRICE_PER_MILLION_IN_CENTS environment variable is not set."
            )

        try:
            pricing_data = json.loads(raw_value)
        except json.JSONDecodeError:
            raise ValueError("JSON_MODEL_PRICE_PER_MILLION_IN_CENTS is not a valid JSON string.")

        self._pricing_data = {}
        for models in pricing_data.values():
            for model_id, prices in models.items():
                self._pricing_data[model_id] = prices

    def get_input_price(self, model_id: str) -> int:
        """
        Get the input price for a specific model.

        Args:
            model_id: The ID of the model to get the price for.

        Returns:
            The price for the model in cents, for 1 million tokens, for input.
        """
        try:
            return self._pricing_data[model_id]["input"]
        except KeyError:
            raise ValueError(f"Input price not found for model '{model_id}'.")

    def get_output_price(self, model_id: str) -> int:
        """
        Get the output price for a specific model.

        Args:
            model_id: The ID of the model to get the price for.

        Returns:
            The price for the model in cents, for 1 million tokens, for output.
        """
        try:
            return self._pricing_data[model_id]["output"]
        except KeyError:
            raise ValueError(f"Output price not found for model '{model_id}'.")


class Settings:
    # Project info
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AE Scientist")
    VERSION: str = os.getenv("VERSION", "1.0.0")

    # API settings
    API_TITLE: str = os.getenv("API_TITLE", f"{PROJECT_NAME} API")

    # CORS settings
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    CORS_CREDENTIALS: bool = os.getenv("CORS_CREDENTIALS", "true").lower() == "true"
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = os.getenv("RELOAD", "true").lower() == "true"

    # Production settings
    RAILWAY_ENVIRONMENT_NAME: str = os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")

    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Anthropic settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # xAI/Grok settings
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # LLM generation constraints
    IDEA_MAX_COMPLETION_TOKENS: int = int(os.getenv("IDEA_MAX_COMPLETION_TOKENS", "8192"))

    # Database settings (PostgreSQL only)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ae_scientist")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Authentication settings
    SESSION_EXPIRE_HOURS: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))
    MIN_USER_CREDITS_FOR_CONVERSATION: int = int(
        os.getenv("MIN_USER_CREDITS_FOR_CONVERSATION", "1")
    )
    MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE: int = int(
        os.getenv("MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE", "30")
    )

    # Frontend URL for redirects
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Research pipeline webhook authentication
    TELEMETRY_WEBHOOK_TOKEN: str = os.getenv("TELEMETRY_WEBHOOK_TOKEN", "")

    # Stripe / billing configuration
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_CHECKOUT_SUCCESS_URL: str = os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", "")
    STRIPE_PRICE_TO_CREDITS: Dict[str, int] = _parse_price_map(
        os.getenv("STRIPE_PRICE_TO_CREDITS", "{}")
    )
    RESEARCH_RUN_CREDITS_PER_MINUTE: int = int(os.getenv("RESEARCH_RUN_CREDITS_PER_MINUTE", "1"))
    CHAT_MESSAGE_CREDIT_COST: int = int(os.getenv("CHAT_MESSAGE_CREDIT_COST", "1"))

    # LLM pricing configuration
    LLM_PRICING: LLMPricing = LLMPricing(os.getenv("JSON_MODEL_PRICE_PER_MILLION_IN_CENTS", ""))

    @property
    def is_production(self) -> bool:
        return self.RAILWAY_ENVIRONMENT_NAME == "production"


# Create settings instance
settings = Settings()
