"""
LLM token usage database operations.

Handles operations for llm_token_usages table.
"""

import logging
from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class BaseLlmTokenUsage(NamedTuple):
    """Represents a base data model of LLM token usage. Mostly used when aggregating data."""

    conversation_id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    run_id: Optional[str] = None


class LlmTokenUsage(BaseLlmTokenUsage):
    """Represents a record of LLM token usage."""

    id: int
    created_at: datetime
    updated_at: datetime


class LlmTokenUsagesMixin(ConnectionProvider):
    """Database operations for LLM token usages."""

    def create_llm_token_usage(
        self,
        conversation_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        run_id: Optional[str] = None,
    ) -> int:
        """Create a new LLM token usage record in the database."""
        now = datetime.now()

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO llm_token_usages
                    (conversation_id, run_id, provider, model, input_tokens, output_tokens, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation_id,
                        run_id,
                        provider,
                        model,
                        input_tokens,
                        output_tokens,
                        now,
                        now,
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create LLM token usage record: no ID returned")

                token_usage_id = int(result["id"])
                conn.commit()

        return token_usage_id

    def get_llm_token_usages_by_conversation_aggregated_by_model(
        self, conversation_id: int
    ) -> List[BaseLlmTokenUsage]:
        """
        Get all LLM token usages for a conversation aggregated by model.
        This DOES NOT include the items with run_id.

        Args:
            conversation_id: The ID of the conversation

        Returns:
            List of LlmTokenUsage objects
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT conversation_id, provider, model, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                    FROM llm_token_usages
                    WHERE conversation_id = %s
                    AND run_id IS NULL
                    GROUP BY conversation_id, provider, model
                    ORDER BY provider, model
                """,
                    (conversation_id,),
                )
                rows = cursor.fetchall()
        return [BaseLlmTokenUsage(**row) for row in rows]

    def get_llm_token_usages_by_conversation_aggregated_by_run_and_model(
        self, conversation_id: int
    ) -> List[BaseLlmTokenUsage]:
        """Get all LLM token usages for a conversation aggregated by run_id and model."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT conversation_id, run_id, provider, model, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                    FROM llm_token_usages
                    WHERE conversation_id = %s
                    AND run_id IS NOT NULL
                    GROUP BY conversation_id, run_id, provider, model
                    ORDER BY provider, model
                """,
                    (conversation_id,),
                )
                rows = cursor.fetchall()
        return [BaseLlmTokenUsage(**row) for row in rows]

    def get_llm_token_usages_by_run_aggregated_by_model(
        self, run_id: str
    ) -> List[BaseLlmTokenUsage]:
        """Get all LLM token usages for a run aggregated by model."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT conversation_id, run_id, provider, model, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                    FROM llm_token_usages
                    WHERE run_id = %s
                    GROUP BY conversation_id, run_id, provider, model
                    ORDER BY provider, model
                """,
                    (run_id,),
                )
                rows = cursor.fetchall()
        return [BaseLlmTokenUsage(**row) for row in rows]
