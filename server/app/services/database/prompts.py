"""
LLM prompts database operations.

Handles CRUD operations for llm_prompts table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class ActivePromptData(NamedTuple):
    """Active prompt data."""

    id: int
    created_at: datetime
    prompt_type: str
    system_prompt: str
    is_active: bool


class PromptsMixin:
    """Database operations for LLM prompts."""

    def get_active_prompt(self, prompt_type: str) -> Optional[ActivePromptData]:
        """Get the currently active prompt for a given type."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT id, created_at, prompt_type, system_prompt, is_active FROM llm_prompts WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )
                result = cursor.fetchone()
                return ActivePromptData(**result) if result else None

    def create_prompt(self, prompt_type: str, system_prompt: str, created_by_user_id: int) -> int:
        """Create a new prompt and set it as active, deactivating any existing active prompt."""
        now = datetime.now()

        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                # First deactivate any existing active prompt of this type
                cursor.execute(
                    "UPDATE llm_prompts SET is_active = FALSE WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )

                # Create the new prompt as active
                cursor.execute(
                    "INSERT INTO llm_prompts (created_at, prompt_type, system_prompt, is_active, created_by_user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (now, prompt_type, system_prompt, True, created_by_user_id),
                )
                new_prompt_id: int = cursor.fetchone()[0]

                conn.commit()
                return new_prompt_id

    def deactivate_prompt(self, prompt_type: str) -> bool:
        """Deactivate ALL active prompts for a given type."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                # Set ALL prompts of this type to inactive (not just the currently active one)
                cursor.execute(
                    "UPDATE llm_prompts SET is_active = FALSE WHERE prompt_type = %s AND is_active = TRUE",
                    (prompt_type,),
                )
                rows_affected = cursor.rowcount
                logger.info(f"Deactivated {rows_affected} prompt(s) for type '{prompt_type}'")
                conn.commit()
                return bool(
                    rows_affected >= 0
                )  # Return True even if no rows affected (already deactivated)
