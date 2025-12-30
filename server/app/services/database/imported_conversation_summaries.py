"""
Imported conversation summaries database operations.

Handles CRUD operations for imported_conversation_summaries table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class ImportedConversationSummary(NamedTuple):
    """Represents a single imported conversation summary."""

    id: int
    conversation_id: int
    summary: str
    created_at: datetime
    updated_at: datetime


class ImportedConversationSummariesMixin(ConnectionProvider):
    """Database operations for imported conversation summaries."""

    async def create_imported_conversation_summary(self, conversation_id: int, summary: str) -> int:
        """Create a new imported conversation summary in the database."""
        now = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO imported_conversation_summaries
                    (conversation_id, summary, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation_id,
                        summary,
                        now,
                        now,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError(
                        "Failed to create imported conversation summary: no ID returned"
                    )

                imported_conversation_summary_id = int(result["id"])
                await conn.commit()
                return imported_conversation_summary_id

    async def update_imported_conversation_summary(
        self, conversation_id: int, new_summary: str
    ) -> bool:
        """Update a conversation's summary. Returns True if updated, False if not found."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE imported_conversation_summaries SET summary = %s, updated_at = %s WHERE conversation_id = %s",
                    (new_summary, now, conversation_id),
                )
                await conn.commit()
                return bool(cursor.rowcount > 0)

    async def get_imported_conversation_summary_by_conversation_id(
        self, conversation_id: int
    ) -> Optional[ImportedConversationSummary]:
        """Get a conversation's summary by conversation ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT id, conversation_id, summary, created_at, updated_at FROM imported_conversation_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = await cursor.fetchone()
                return ImportedConversationSummary(**row) if row else None

    async def delete_imported_conversation_summary(self, conversation_id: int) -> bool:
        """Delete a conversation's summary by conversation ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM imported_conversation_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                await conn.commit()
                return bool(cursor.rowcount > 0)
