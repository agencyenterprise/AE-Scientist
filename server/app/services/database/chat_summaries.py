"""
Chat summaries database operations.

Handles CRUD operations for chat_summaries table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class ChatSummary(NamedTuple):
    """Represents a single chat summary."""

    id: int
    conversation_id: int
    summary: str
    latest_message_id: int
    created_at: datetime
    updated_at: datetime


class ChatSummariesMixin(ConnectionProvider):
    """Database operations for chat summaries."""

    async def create_chat_summary(
        self, conversation_id: int, summary: str, latest_message_id: int
    ) -> int:
        """Create a new chat summary in the database."""
        now = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO chat_summaries
                    (conversation_id, summary, latest_message_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation_id,
                        summary,
                        latest_message_id,
                        now,
                        now,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create chat summary: no ID returned")

                chat_summary_id = int(result["id"])
                await conn.commit()
                return chat_summary_id

    async def update_chat_summary(
        self, conversation_id: int, new_summary: str, latest_message_id: int | None = None
    ) -> bool:
        """Update a conversation's summary. Returns True if updated, False if not found."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                if latest_message_id is not None:
                    await cursor.execute(
                        "UPDATE chat_summaries SET summary = %s, latest_message_id = %s, updated_at = %s WHERE conversation_id = %s",
                        (new_summary, latest_message_id, now, conversation_id),
                    )
                else:
                    await cursor.execute(
                        "UPDATE chat_summaries SET summary = %s, updated_at = %s WHERE conversation_id = %s",
                        (new_summary, now, conversation_id),
                    )
                await conn.commit()
                return bool(cursor.rowcount > 0)

    async def get_chat_summary_by_conversation_id(
        self, conversation_id: int
    ) -> Optional[ChatSummary]:
        """Get a conversation's summary by conversation ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT id, conversation_id, summary, latest_message_id, created_at, updated_at FROM chat_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = await cursor.fetchone()
                return ChatSummary(**row) if row else None
