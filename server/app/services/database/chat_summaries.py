"""
Chat summaries database operations.

Handles CRUD operations for chat_summaries table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class ChatSummary(NamedTuple):
    """Represents a single chat summary."""

    id: int
    conversation_id: int
    external_id: int
    summary: str
    latest_message_id: int
    created_at: datetime
    updated_at: datetime


class ChatSummariesMixin:
    """Database operations for chat summaries."""

    def create_chat_summary(
        self, conversation_id: int, external_id: int, summary: str, latest_message_id: int
    ) -> int:
        """Create a new chat summary in the database."""
        now = datetime.now()

        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_summaries
                    (conversation_id, external_id, summary, latest_message_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation_id,
                        external_id,
                        summary,
                        latest_message_id,
                        now,
                        now,
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create chat summary: no ID returned")

                chat_summary_id = int(result["id"])
                conn.commit()

        return chat_summary_id

    def update_chat_summary(
        self, conversation_id: int, new_summary: str, latest_message_id: int
    ) -> bool:
        """Update a conversation's summary. Returns True if updated, False if not found."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE chat_summaries SET summary = %s, latest_message_id = %s, updated_at = %s WHERE conversation_id = %s",
                    (new_summary, latest_message_id, now, conversation_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def get_chat_summary_by_conversation_id(self, conversation_id: int) -> Optional[ChatSummary]:
        """Get a conversation's summary by conversation ID."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT id, conversation_id, external_id, summary, latest_message_id, created_at, updated_at FROM chat_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                return ChatSummary(**row) if row else None
