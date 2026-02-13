"""
Configuration module that loads and validates all environment variables at startup.

Uses NamedTuples for type-safe, immutable configuration storage.
Fails fast at import time if required variables are missing.
"""

import os
import sys
from typing import List, NamedTuple, Tuple

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class DatabaseConfig(NamedTuple):
    """Database connection configuration."""

    url: str
    pool_min_conn: int
    pool_max_conn: int
    pool_usage_warn_threshold: float
    skip_connection: bool


class AWSConfig(NamedTuple):
    """AWS S3 configuration."""

    access_key_id: str
    secret_access_key: str
    region: str
    s3_bucket_name: str


class ClerkConfig(NamedTuple):
    """Clerk authentication configuration."""

    secret_key: str
    publishable_key: str


class LLMConfig(NamedTuple):
    """LLM provider API keys."""

    openai_api_key: str
    anthropic_api_key: str
    xai_api_key: str


class ServerConfig(NamedTuple):
    """Server runtime configuration."""

    project_name: str
    version: str
    api_title: str
    host: str
    port: int
    reload: bool
    log_level: str
    frontend_url: str
    cors_origins: Tuple[str, ...]
    cors_credentials: bool


class Settings(NamedTuple):
    """All application settings stored as immutable NamedTuple."""

    server: ServerConfig
    database: DatabaseConfig
    aws: AWSConfig
    clerk: ClerkConfig
    llm: LLMConfig
    sentry_dsn: str
    sentry_environment: str
    session_expire_hours: int

    @property
    def is_production(self) -> bool:
        return os.getenv("RAILWAY_ENVIRONMENT_NAME", "") == "production"


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

    def get_optional_float(name: str, default: float) -> float:
        value = os.getenv(name)
        if value is None or value == "":
            return default
        try:
            return float(value)
        except ValueError:
            return default

    # Server config
    project_name = get_optional("PROJECT_NAME", "AE Paper Review")
    server = ServerConfig(
        project_name=project_name,
        version=get_optional("VERSION", "1.0.0"),
        api_title=get_optional("API_TITLE", f"{project_name} API"),
        host=get_optional("HOST", "0.0.0.0"),
        port=get_optional_int("PORT", 8000),
        reload=get_optional_bool("SERVER_AUTO_RELOAD", False),
        log_level=get_optional("LOG_LEVEL", "INFO"),
        frontend_url=get_required("FRONTEND_URL"),
        cors_origins=get_required_list("CORS_ORIGINS"),
        cors_credentials=get_optional_bool("CORS_CREDENTIALS", True),
    )

    # Database config
    database = DatabaseConfig(
        url=get_required("DATABASE_URL"),
        pool_min_conn=get_optional_int("DB_POOL_MIN_CONN", 2),
        pool_max_conn=get_optional_int("DB_POOL_MAX_CONN", 10),
        pool_usage_warn_threshold=get_optional_float("DB_POOL_USAGE_WARN_THRESHOLD", 0.8),
        skip_connection=get_optional_bool("SKIP_DB_CONNECTION", False),
    )

    # AWS config
    aws = AWSConfig(
        access_key_id=get_required("AWS_ACCESS_KEY_ID"),
        secret_access_key=get_required("AWS_SECRET_ACCESS_KEY"),
        region=get_required("AWS_REGION"),
        s3_bucket_name=get_required("AWS_S3_BUCKET_NAME"),
    )

    # Clerk config
    clerk = ClerkConfig(
        secret_key=get_required("CLERK_SECRET_KEY"),
        publishable_key=get_required("CLERK_PUBLISHABLE_KEY"),
    )

    # LLM config
    llm = LLMConfig(
        openai_api_key=get_optional("OPENAI_API_KEY", ""),
        anthropic_api_key=get_optional("ANTHROPIC_API_KEY", ""),
        xai_api_key=get_optional("XAI_API_KEY", ""),
    )

    # Check for errors before proceeding
    if errors:
        error_list = "\n  - ".join(errors)
        raise ConfigError(
            f"Missing required environment variables:\n  - {error_list}\n\n"
            f"Please set these variables in your .env file or environment."
        )

    return Settings(
        server=server,
        database=database,
        aws=aws,
        clerk=clerk,
        llm=llm,
        sentry_dsn=get_optional("SENTRY_DSN", ""),
        sentry_environment=get_optional("SENTRY_ENVIRONMENT", "development"),
        session_expire_hours=get_optional_int("SESSION_EXPIRE_HOURS", 168),
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
