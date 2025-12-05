"""
LLM defaults database operations.

Handles CRUD operations for default_llm_parameters table.
"""

import logging
from datetime import datetime
from typing import NamedTuple

import psycopg2
import psycopg2.extras

from app.prompt_types import PromptTypes

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class DefaultLLMParametersData(NamedTuple):
    """Default LLM parameters data."""

    llm_model: str
    llm_provider: str


class LLMDefaultsMixin(ConnectionProvider):
    """Database operations for LLM default parameters."""

    def get_default_llm_parameters(self, prompt_type: PromptTypes) -> DefaultLLMParametersData:
        """Get the default LLM parameters for a given prompt type."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT llm_model, llm_provider FROM default_llm_parameters WHERE prompt_type = %s",
                    (prompt_type.value,),
                )
                result = cursor.fetchone()
                if result:
                    return DefaultLLMParametersData(**result)

        return DefaultLLMParametersData(
            llm_model="gpt-4o",
            llm_provider="openai",
        )

    def set_default_llm_parameters(
        self, prompt_type: str, llm_model: str, llm_provider: str, created_by_user_id: int
    ) -> bool:
        """Set the default LLM parameters for a given prompt type (upsert operation)."""
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO default_llm_parameters (prompt_type, llm_model, llm_provider, created_at, updated_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (prompt_type) DO UPDATE SET
                        llm_model = EXCLUDED.llm_model,
                        llm_provider = EXCLUDED.llm_provider,
                        updated_at = EXCLUDED.updated_at,
                        created_by_user_id = EXCLUDED.created_by_user_id
                    """,
                    (prompt_type, llm_model, llm_provider, now, now, created_by_user_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)
