"""
LLM prompts database operations.

Handles CRUD operations for llm_prompts table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class ActivePromptData(NamedTuple):
    """Active prompt data."""

    id: int
    created_at: datetime
    prompt_type: str
    system_prompt: str
    is_active: bool


class PromptsMixin(ConnectionProvider):
    """Database operations for LLM prompts."""

    async def get_active_prompt(self, prompt_type: str) -> Optional[ActivePromptData]:
        """Get the currently active prompt for a given type."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT id, created_at, prompt_type, system_prompt, is_active FROM llm_prompts WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )
                result = await cursor.fetchone()
                return ActivePromptData(**result) if result else None

    async def create_prompt(
        self, prompt_type: str, system_prompt: str, created_by_user_id: int
    ) -> int:
        """Create a new prompt and set it as active, deactivating any existing active prompt."""
        now = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE llm_prompts SET is_active = FALSE WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )

                await cursor.execute(
                    "INSERT INTO llm_prompts (created_at, prompt_type, system_prompt, is_active, created_by_user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (now, prompt_type, system_prompt, True, created_by_user_id),
                )
                new_prompt_row = await cursor.fetchone()
                if not new_prompt_row:
                    raise ValueError("Failed to create prompt (missing id).")
                new_prompt_id: int = int(new_prompt_row[0])

                await conn.commit()
                return new_prompt_id

    async def deactivate_prompt(self, prompt_type: str) -> bool:
        """Deactivate ALL active prompts for a given type."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE llm_prompts SET is_active = FALSE WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )
                rows_affected = cursor.rowcount
                logger.info(f"Deactivated {rows_affected} prompt(s) for type '{prompt_type}'")
                await conn.commit()
                return bool(rows_affected >= 0)
