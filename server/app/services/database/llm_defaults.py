"""
LLM defaults database operations.

Handles CRUD operations for default_llm_parameters table.
"""

import logging
from datetime import datetime
from typing import NamedTuple

from psycopg.rows import dict_row

from app.prompt_types import PromptTypes

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class DefaultLLMParametersData(NamedTuple):
    """Default LLM parameters data."""

    llm_model: str
    llm_provider: str


class LLMDefaultsMixin(ConnectionProvider):
    """Database operations for LLM default parameters."""

    async def get_default_llm_parameters(
        self, prompt_type: PromptTypes
    ) -> DefaultLLMParametersData:
        """Get the default LLM parameters for a given prompt type."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT llm_model, llm_provider FROM default_llm_parameters WHERE prompt_type = %s",
                    (prompt_type.value,),
                )
                result = await cursor.fetchone()
                if result:
                    return DefaultLLMParametersData(**result)

        return DefaultLLMParametersData(
            llm_model="gpt-5.2",
            llm_provider="openai",
        )

    async def set_default_llm_parameters(
        self, prompt_type: str, llm_model: str, llm_provider: str, created_by_user_id: int
    ) -> bool:
        """Set the default LLM parameters for a given prompt type (upsert operation)."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
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
                await conn.commit()
                return bool(cursor.rowcount > 0)
