"""
Configuration module that loads and validates all environment variables at startup.

Uses Pydantic Settings for type-safe, validated configuration.
Fails fast at import time if required variables are missing.
"""

import json
import sys
from typing import Tuple

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class LLMPricing:
    """Provides access to LLM pricing information.

    Prices are looked up using the "provider:model" format (e.g., "openai:gpt-5.2").
    """

    _pricing_data: dict[str, dict[str, int]]

    def __init__(self, raw_value: str):
        if not raw_value:
            raise ConfigError(
                "Required environment variable 'JSON_MODEL_PRICE_PER_MILLION_IN_CENTS' is not set"
            )

        try:
            pricing_data = json.loads(raw_value)
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"Environment variable 'JSON_MODEL_PRICE_PER_MILLION_IN_CENTS' is not valid JSON: {e}"
            )

        self._pricing_data = {}
        for provider, models in pricing_data.items():
            if not isinstance(models, dict):
                continue
            for model_name, prices in models.items():
                if not isinstance(prices, dict):
                    continue
                sanitized: dict[str, int] = {}
                for price_key, price_value in prices.items():
                    try:
                        sanitized[str(price_key)] = int(price_value)
                    except (TypeError, ValueError):
                        continue
                key = f"{provider}:{model_name}"
                self._pricing_data[key] = sanitized

    def get_input_price(self, model: str) -> int:
        """Get the input price for a specific model in cents per million tokens."""
        try:
            return int(self._pricing_data[model]["input"])
        except KeyError:
            raise ValueError(f"Input price not found for model '{model}'.")

    def get_cached_input_price(self, model: str) -> int:
        """Get the cached-input price, falling back to normal input price if not configured."""
        try:
            cached = self._pricing_data[model].get("cached_input")
        except KeyError:
            raise ValueError(f"Pricing not found for model '{model}'.")
        if cached is None:
            return self.get_input_price(model=model)
        return int(cached)

    def get_cache_write_input_price(self, model: str) -> int:
        """Get cache-write input price, falling back to normal input price."""
        try:
            cache_write = self._pricing_data[model].get("cache_write_input")
        except KeyError:
            raise ValueError(f"Pricing not found for model '{model}'.")
        if cache_write is None:
            return self.get_input_price(model=model)
        return int(cache_write)

    def get_output_price(self, model: str) -> int:
        """Get the output price for a specific model in cents per million tokens."""
        try:
            return int(self._pricing_data[model]["output"])
        except KeyError:
            raise ValueError(f"Output price not found for model '{model}'.")


def _parse_comma_list(value: str) -> Tuple[str, ...]:
    """Parse a comma-separated string into a tuple of stripped values."""
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


class Settings(BaseSettings):
    """All application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server config
    project_name: str = Field(default="AE Scientist", alias="PROJECT_NAME")
    version: str = Field(default="1.0.0", alias="VERSION")
    api_title: str = Field(default="", alias="API_TITLE")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    server_auto_reload: bool = Field(alias="SERVER_AUTO_RELOAD")
    log_level: str = Field(alias="LOG_LEVEL")
    railway_environment_name: str = Field(default="development", alias="RAILWAY_ENVIRONMENT_NAME")
    frontend_url: str = Field(alias="FRONTEND_URL")
    cors_origins_raw: str = Field(alias="CORS_ORIGINS")
    cors_credentials: bool = Field(alias="CORS_CREDENTIALS")

    # Database config
    database_url: str = Field(alias="DATABASE_URL")
    db_pool_min_conn: int = Field(alias="DB_POOL_MIN_CONN")
    db_pool_max_conn: int = Field(alias="DB_POOL_MAX_CONN")
    db_pool_usage_warn_threshold: float = Field(alias="DB_POOL_USAGE_WARN_THRESHOLD")
    skip_db_connection: bool = Field(default=False, alias="SKIP_DB_CONNECTION")

    # Redis config
    redis_url: str = Field(alias="REDIS_URL")
    redis_stream_maxlen: int = Field(default=1000, alias="REDIS_STREAM_MAXLEN")
    redis_stream_ttl_seconds: int = Field(default=86400, alias="REDIS_STREAM_TTL_SECONDS")

    # RunPod config
    runpod_api_key: str = Field(alias="RUNPOD_API_KEY")
    runpod_ssh_access_key: str = Field(alias="RUNPOD_SSH_ACCESS_KEY")
    runpod_supported_gpus_raw: str = Field(alias="RUNPOD_SUPPORTED_GPUS")
    fake_runpod_base_url: str = Field(default="", alias="FAKE_RUNPOD_BASE_URL")
    fake_runpod_graphql_url: str = Field(default="", alias="FAKE_RUNPOD_GRAPHQL_URL")

    # Research pipeline config
    pipeline_monitor_poll_interval_seconds: int = Field(
        alias="PIPELINE_MONITOR_POLL_INTERVAL_SECONDS"
    )
    pipeline_monitor_heartbeat_timeout_seconds: int = Field(
        alias="PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS"
    )
    pipeline_monitor_max_missed_heartbeats: int = Field(
        alias="PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS"
    )
    pipeline_monitor_startup_grace_seconds: int = Field(
        alias="PIPELINE_MONITOR_STARTUP_GRACE_SECONDS"
    )
    pipeline_monitor_max_runtime_hours: int = Field(alias="PIPELINE_MONITOR_MAX_RUNTIME_HOURS")
    pipeline_max_restart_attempts: int = Field(alias="PIPELINE_MAX_RESTART_ATTEMPTS")
    research_pipeline_path: str = Field(default="", alias="RESEARCH_PIPELINE_PATH")
    telemetry_webhook_url: str = Field(alias="TELEMETRY_WEBHOOK_URL")
    hf_token: str = Field(alias="HF_TOKEN")
    collect_disk_stats_paths: str = Field(default="", alias="COLLECT_DISK_STATS_PATHS")

    # AWS config
    aws_access_key_id: str = Field(alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(alias="AWS_REGION")
    aws_s3_bucket_name: str = Field(alias="AWS_S3_BUCKET_NAME")

    # Stripe config
    stripe_secret_key: str = Field(alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(alias="STRIPE_WEBHOOK_SECRET")
    stripe_checkout_success_url: str = Field(alias="STRIPE_CHECKOUT_SUCCESS_URL")
    stripe_price_ids_raw: str = Field(alias="STRIPE_PRICE_IDS")

    # Clerk config
    clerk_secret_key: str = Field(alias="CLERK_SECRET_KEY")
    clerk_publishable_key: str = Field(alias="CLERK_PUBLISHABLE_KEY")

    # LLM config
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    xai_api_key: str = Field(alias="XAI_API_KEY")

    # Billing limits
    min_balance_cents_for_research_pipeline: int = Field(
        alias="MIN_BALANCE_CENTS_FOR_RESEARCH_PIPELINE"
    )
    min_balance_cents_for_chat_message: int = Field(alias="MIN_BALANCE_CENTS_FOR_CHAT_MESSAGE")
    min_balance_cents_for_paper_review: int = Field(alias="MIN_BALANCE_CENTS_FOR_PAPER_REVIEW")
    credit_cents_new_users: int = Field(default=0, alias="CREDIT_CENTS_NEW_USERS")

    # LLM Pricing (JSON)
    json_model_price_per_million_in_cents: str = Field(
        alias="JSON_MODEL_PRICE_PER_MILLION_IN_CENTS"
    )

    # Other settings
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="", alias="SENTRY_ENVIRONMENT")
    idea_max_completion_tokens: int = Field(default=8192, alias="IDEA_MAX_COMPLETION_TOKENS")
    session_expire_hours: int = Field(default=24, alias="SESSION_EXPIRE_HOURS")
    whitelist_emails_free_credit_raw: str = Field(default="", alias="WHITELIST_EMAILS_FREE_CREDIT")
    railway_git_commit_sha: str = Field(default="", alias="RAILWAY_GIT_COMMIT_SHA")

    # Computed fields (built in model_validator)
    _cors_origins: Tuple[str, ...] = ()
    _runpod_supported_gpus: Tuple[str, ...] = ()
    _stripe_price_ids: Tuple[str, ...] = ()
    _whitelist_emails_free_credit: Tuple[str, ...] = ()
    _llm_pricing: LLMPricing | None = None
    _resolved_api_title: str = ""

    @field_validator("stripe_price_ids_raw")
    @classmethod
    def validate_stripe_price_ids(cls, v: str) -> str:
        """Ensure at least one price ID is provided."""
        if not v or not any(item.strip() for item in v.split(",")):
            raise ValueError("STRIPE_PRICE_IDS must contain at least one price ID")
        return v

    @model_validator(mode="after")
    def build_computed_fields(self) -> "Settings":
        """Build computed fields after validation."""
        object.__setattr__(self, "_cors_origins", _parse_comma_list(self.cors_origins_raw))
        object.__setattr__(
            self, "_runpod_supported_gpus", _parse_comma_list(self.runpod_supported_gpus_raw)
        )
        object.__setattr__(self, "_stripe_price_ids", _parse_comma_list(self.stripe_price_ids_raw))
        object.__setattr__(
            self,
            "_whitelist_emails_free_credit",
            _parse_comma_list(self.whitelist_emails_free_credit_raw),
        )
        object.__setattr__(
            self,
            "_llm_pricing",
            LLMPricing(self.json_model_price_per_million_in_cents),
        )
        object.__setattr__(
            self,
            "_resolved_api_title",
            self.api_title if self.api_title else f"{self.project_name} API",
        )
        return self

    @property
    def cors_origins(self) -> Tuple[str, ...]:
        return self._cors_origins

    @property
    def runpod_supported_gpus(self) -> Tuple[str, ...]:
        return self._runpod_supported_gpus

    @property
    def stripe_price_ids(self) -> Tuple[str, ...]:
        return self._stripe_price_ids

    @property
    def whitelist_emails_free_credit(self) -> Tuple[str, ...]:
        return self._whitelist_emails_free_credit

    @property
    def llm_pricing(self) -> LLMPricing:
        assert self._llm_pricing is not None
        return self._llm_pricing

    @property
    def resolved_api_title(self) -> str:
        return self._resolved_api_title

    @property
    def is_production(self) -> bool:
        return self.railway_environment_name == "production"

    @property
    def uses_fake_runpod(self) -> bool:
        return bool(self.fake_runpod_base_url)


# Load settings at import time - fails fast if configuration is invalid
try:
    settings = Settings()  # pyright: ignore[reportCallIssue]
except Exception as e:
    print(f"\n{'=' * 60}", file=sys.stderr)
    print("CONFIGURATION ERROR", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(str(e), file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)
    sys.exit(1)
