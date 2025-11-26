"""Alembic environment configuration for AE Scientist"""

import logging
import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any, Dict

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


# Set the database URL from environment variables (avoiding settings cache issues)
def get_database_url() -> str:
    """Get the database URL from environment variables."""
    # Load .env file explicitly to ensure production credentials are available

    # Try to find .env file - first in current directory, then in parent
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path("../.env")
        if not env_file.exists():
            env_file = Path("backend/.env")

    load_dotenv(env_file if env_file.exists() else None)

    # Read environment variables directly (fresh from .env file)
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "ae_scientist")
    postgres_user = os.getenv("POSTGRES_USER", "")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "")

    # Check for direct DATABASE_URL override, but only if no explicit postgres vars are set
    # This allows make create-test-db to override DATABASE_URL with individual variables
    database_url = os.getenv("DATABASE_URL")

    # If DATABASE_URL exists but we have explicit postgres variables that differ from .env defaults,
    # prefer the explicit variables (this handles make create-test-db case)
    explicit_postgres_vars = (
        os.getenv("POSTGRES_HOST")
        or os.getenv("POSTGRES_PORT")
        or os.getenv("POSTGRES_DB")
        or os.getenv("POSTGRES_USER")
        or os.getenv("POSTGRES_PASSWORD")
    )

    if database_url and not explicit_postgres_vars:
        return database_url

    # Build URL from fresh environment variables
    return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"


# Set the SQLAlchemy URL in the alembic configuration
config.set_main_option("sqlalchemy.url", get_database_url())

# add your model's MetaData object here for 'autogenerate' support
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # Get configuration as a dict and override the URL
    configuration: Dict[str, Any] = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
