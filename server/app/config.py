"""
Configuration module that loads and validates all environment variables at startup.

Uses NamedTuples for type-safe, immutable configuration storage.
Fails fast at import time if required variables are missing.
"""

import json
import os
import sys
from typing import Dict, List, NamedTuple, Tuple

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class LLMPricing:
    """Provides access to LLM pricing information.

    Prices are looked up using the "provider:model" format (e.g., "openai:gpt-5.2").
    """

    _pricing_data: Dict[str, Dict[str, int]]

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
                sanitized: Dict[str, int] = {}
                for price_key, price_value in prices.items():
                    try:
                        sanitized[str(price_key)] = int(price_value)
                    except (TypeError, ValueError):
                        continue
                # Store with "provider:model" key
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

    def get_output_price(self, model: str) -> int:
        """Get the output price for a specific model in cents per million tokens."""
        try:
            return int(self._pricing_data[model]["output"])
        except KeyError:
            raise ValueError(f"Output price not found for model '{model}'.")


class DatabaseConfig(NamedTuple):
    """Database connection configuration."""

    url: str
    pool_min_conn: int
    pool_max_conn: int
    pool_usage_warn_threshold: float
    skip_connection: bool


class RunPodConfig(NamedTuple):
    """RunPod API and SSH configuration."""

    api_key: str
    ssh_access_key: str
    supported_gpus: Tuple[str, ...]
    fake_base_url: str = ""
    fake_graphql_url: str = ""

    @property
    def uses_fake_runpod(self) -> bool:
        """Return True if fake RunPod is configured."""
        return bool(self.fake_base_url)


class ResearchPipelineConfig(NamedTuple):
    """Research pipeline configuration."""

    monitor_poll_interval_seconds: int
    monitor_heartbeat_timeout_seconds: int
    monitor_max_missed_heartbeats: int
    monitor_startup_grace_seconds: int
    monitor_max_runtime_hours: int
    max_restart_attempts: int
    path: str
    telemetry_webhook_url: str
    hf_token: str
    collect_disk_stats_paths: str


class AWSConfig(NamedTuple):
    """AWS S3 configuration."""

    access_key_id: str
    secret_access_key: str
    region: str
    s3_bucket_name: str


class StripeConfig(NamedTuple):
    """Stripe billing configuration."""

    secret_key: str
    webhook_secret: str
    checkout_success_url: str
    price_ids: Tuple[str, ...]


class ClerkConfig(NamedTuple):
    """Clerk authentication configuration."""

    secret_key: str
    publishable_key: str


class LLMConfig(NamedTuple):
    """LLM provider API keys."""

    openai_api_key: str
    anthropic_api_key: str
    xai_api_key: str


class BillingLimitsConfig(NamedTuple):
    """Minimum balance requirements in cents."""

    min_balance_cents_for_conversation: int
    min_balance_cents_for_research_pipeline: int
    min_balance_cents_for_chat_message: int
    min_balance_cents_for_paper_review: int


class ServerConfig(NamedTuple):
    """Server runtime configuration."""

    project_name: str
    version: str
    api_title: str
    host: str
    port: int
    reload: bool
    log_level: str
    railway_environment_name: str
    frontend_url: str
    cors_origins: Tuple[str, ...]
    cors_credentials: bool


class Settings(NamedTuple):
    """All application settings stored as immutable NamedTuple."""

    server: ServerConfig
    database: DatabaseConfig
    runpod: RunPodConfig
    research_pipeline: ResearchPipelineConfig
    aws: AWSConfig
    stripe: StripeConfig
    clerk: ClerkConfig
    llm: LLMConfig
    billing_limits: BillingLimitsConfig
    llm_pricing: LLMPricing
    sentry_dsn: str
    sentry_environment: str
    idea_max_completion_tokens: int
    session_expire_hours: int
    whitelist_emails_free_credit: Tuple[str, ...]
    railway_git_commit_sha: str

    @property
    def is_production(self) -> bool:
        return self.server.railway_environment_name == "production"


def _load_settings() -> Settings:
    """Load and validate all settings from environment variables.

    Raises ConfigError with a clear message listing all missing required variables.
    """
    errors: List[str] = []

    def get_required(name: str) -> str:
        value = os.getenv(name)
        if value is None or value == "":
            errors.append(name)
            return ""
        return value

    def get_optional(name: str, default: str) -> str:
        return os.getenv(name, default)

    def get_optional_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None or value == "":
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_required_int(name: str) -> int:
        value = os.getenv(name)
        if value is None or value == "":
            errors.append(name)
            return 0
        try:
            return int(value)
        except ValueError:
            errors.append(f"{name} (must be integer, got '{value}')")
            return 0

    def get_optional_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None or value == "":
            return default
        return value.lower() in ("true", "1", "yes")

    def get_required_list(name: str) -> Tuple[str, ...]:
        value = os.getenv(name)
        if value is None or value == "":
            errors.append(name)
            return ()
        return tuple(item.strip() for item in value.split(",") if item.strip())

    def get_required_bool(name: str) -> bool:
        value = os.getenv(name)
        if value is None or value == "":
            errors.append(name)
            return False
        return value.lower() in ("true", "1", "yes")

    def get_required_float(name: str) -> float:
        value = os.getenv(name)
        if value is None or value == "":
            errors.append(name)
            return 0.0
        try:
            return float(value)
        except ValueError:
            errors.append(f"{name} (must be a number, got '{value}')")
            return 0.0

    # Load all configuration
    # Server config
    project_name = get_optional("PROJECT_NAME", "AE Scientist")
    server = ServerConfig(
        project_name=project_name,
        version=get_optional("VERSION", "1.0.0"),
        api_title=get_optional("API_TITLE", f"{project_name} API"),
        host=get_optional("HOST", "0.0.0.0"),
        port=get_optional_int("PORT", 8000),
        reload=get_required_bool("SERVER_AUTO_RELOAD"),
        log_level=get_required("LOG_LEVEL"),
        railway_environment_name=get_optional("RAILWAY_ENVIRONMENT_NAME", "development"),
        frontend_url=get_required("FRONTEND_URL"),
        cors_origins=get_required_list("CORS_ORIGINS"),
        cors_credentials=get_required_bool("CORS_CREDENTIALS"),
    )

    # Database config (required)
    database = DatabaseConfig(
        url=get_required("DATABASE_URL"),
        pool_min_conn=get_required_int("DB_POOL_MIN_CONN"),
        pool_max_conn=get_required_int("DB_POOL_MAX_CONN"),
        pool_usage_warn_threshold=get_required_float("DB_POOL_USAGE_WARN_THRESHOLD"),
        skip_connection=get_optional_bool("SKIP_DB_CONNECTION", False),
    )

    # RunPod config (required)
    runpod = RunPodConfig(
        api_key=get_required("RUNPOD_API_KEY"),
        ssh_access_key=get_required("RUNPOD_SSH_ACCESS_KEY"),
        supported_gpus=get_required_list("RUNPOD_SUPPORTED_GPUS"),
        fake_base_url=get_optional("FAKE_RUNPOD_BASE_URL", ""),
        fake_graphql_url=get_optional("FAKE_RUNPOD_GRAPHQL_URL", ""),
    )

    # Research pipeline config (required)
    research_pipeline = ResearchPipelineConfig(
        monitor_poll_interval_seconds=get_required_int("PIPELINE_MONITOR_POLL_INTERVAL_SECONDS"),
        monitor_heartbeat_timeout_seconds=get_required_int(
            "PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS"
        ),
        monitor_max_missed_heartbeats=get_required_int("PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS"),
        monitor_startup_grace_seconds=get_required_int("PIPELINE_MONITOR_STARTUP_GRACE_SECONDS"),
        monitor_max_runtime_hours=get_required_int("PIPELINE_MONITOR_MAX_RUNTIME_HOURS"),
        max_restart_attempts=get_required_int("PIPELINE_MAX_RESTART_ATTEMPTS"),
        path=get_optional("RESEARCH_PIPELINE_PATH", ""),
        telemetry_webhook_url=get_required("TELEMETRY_WEBHOOK_URL"),
        hf_token=get_required("HF_TOKEN"),
        collect_disk_stats_paths=get_optional("COLLECT_DISK_STATS_PATHS", ""),
    )

    # AWS config (required)
    aws = AWSConfig(
        access_key_id=get_required("AWS_ACCESS_KEY_ID"),
        secret_access_key=get_required("AWS_SECRET_ACCESS_KEY"),
        region=get_required("AWS_REGION"),
        s3_bucket_name=get_required("AWS_S3_BUCKET_NAME"),
    )

    # Stripe config (required)
    stripe_price_ids_raw = get_required("STRIPE_PRICE_IDS")
    stripe_price_ids = tuple(
        item.strip() for item in stripe_price_ids_raw.split(",") if item.strip()
    )
    if not stripe_price_ids:
        errors.append("STRIPE_PRICE_IDS (must contain at least one price ID)")
    stripe = StripeConfig(
        secret_key=get_required("STRIPE_SECRET_KEY"),
        webhook_secret=get_required("STRIPE_WEBHOOK_SECRET"),
        checkout_success_url=get_required("STRIPE_CHECKOUT_SUCCESS_URL"),
        price_ids=stripe_price_ids,
    )

    # Clerk config (required)
    clerk = ClerkConfig(
        secret_key=get_required("CLERK_SECRET_KEY"),
        publishable_key=get_required("CLERK_PUBLISHABLE_KEY"),
    )

    # LLM config (required - at least keys must be set, even if empty for unused providers)
    llm = LLMConfig(
        openai_api_key=get_required("OPENAI_API_KEY"),
        anthropic_api_key=get_required("ANTHROPIC_API_KEY"),
        xai_api_key=get_required("XAI_API_KEY"),
    )

    # Billing limits (required)
    billing_limits = BillingLimitsConfig(
        min_balance_cents_for_conversation=get_required_int("MIN_BALANCE_CENTS_FOR_CONVERSATION"),
        min_balance_cents_for_research_pipeline=get_required_int(
            "MIN_BALANCE_CENTS_FOR_RESEARCH_PIPELINE"
        ),
        min_balance_cents_for_chat_message=get_required_int("MIN_BALANCE_CENTS_FOR_CHAT_MESSAGE"),
        min_balance_cents_for_paper_review=get_required_int("MIN_BALANCE_CENTS_FOR_PAPER_REVIEW"),
    )

    # LLM Pricing (required)
    llm_pricing_raw = get_required("JSON_MODEL_PRICE_PER_MILLION_IN_CENTS")

    # Check for errors before proceeding
    if errors:
        error_list = "\n  - ".join(errors)
        raise ConfigError(
            f"Missing required environment variables:\n  - {error_list}\n\n"
            f"Please set these variables in your .env file or environment."
        )

    # Parse LLM pricing (will raise ConfigError if invalid)
    llm_pricing = LLMPricing(llm_pricing_raw)

    # Optional settings
    whitelist_raw = get_optional("WHITELIST_EMAILS_FREE_CREDIT", "")
    whitelist_emails = tuple(email.strip() for email in whitelist_raw.split(",") if email.strip())

    return Settings(
        server=server,
        database=database,
        runpod=runpod,
        research_pipeline=research_pipeline,
        aws=aws,
        stripe=stripe,
        clerk=clerk,
        llm=llm,
        billing_limits=billing_limits,
        llm_pricing=llm_pricing,
        sentry_dsn=get_optional("SENTRY_DSN", ""),
        sentry_environment=get_optional("SENTRY_ENVIRONMENT", ""),
        idea_max_completion_tokens=get_optional_int("IDEA_MAX_COMPLETION_TOKENS", 8192),
        session_expire_hours=get_optional_int("SESSION_EXPIRE_HOURS", 24),
        whitelist_emails_free_credit=whitelist_emails,
        railway_git_commit_sha=get_optional("RAILWAY_GIT_COMMIT_SHA", ""),
    )


# Load settings at import time - fails fast if configuration is invalid
try:
    settings = _load_settings()
except ConfigError as e:
    print(f"\n{'=' * 60}", file=sys.stderr)
    print("CONFIGURATION ERROR", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(str(e), file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)
    sys.exit(1)
