"""
Imported conversation summaries database operations.

Handles CRUD operations for imported_conversation_summaries table.
"""

import logging
from datetime import datetime
from typing import NamedTuple, Optional

import psycopg2
import psycopg2.extras

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class ImportedConversationSummary(NamedTuple):
    """Represents a single imported conversation summary."""

    id: int
    conversation_id: int
    external_id: int
    summary: str
    created_at: datetime
    updated_at: datetime


class ImportedConversationSummariesMixin(ConnectionProvider):
    """Database operations for imported conversation summaries."""

    def create_imported_conversation_summary(
        self, conversation_id: int, external_id: int, summary: str
    ) -> int:
        """Create a new imported conversation summary in the database."""
        now = datetime.now()

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO imported_conversation_summaries
                    (conversation_id, external_id, summary, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation_id,
                        external_id,
                        summary,
                        now,
                        now,
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError(
                        "Failed to create imported conversation summary: no ID returned"
                    )

                imported_conversation_summary_id = int(result["id"])
                conn.commit()

        return imported_conversation_summary_id

    def update_imported_conversation_summary(self, conversation_id: int, new_summary: str) -> bool:
        """Update a conversation's summary. Returns True if updated, False if not found."""
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE imported_conversation_summaries SET summary = %s, updated_at = %s WHERE conversation_id = %s",
                    (new_summary, now, conversation_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def get_imported_conversation_summary_by_conversation_id(
        self, conversation_id: int
    ) -> Optional[ImportedConversationSummary]:
        """Get a conversation's summary by conversation ID."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT id, conversation_id, external_id, summary, created_at, updated_at FROM imported_conversation_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                return ImportedConversationSummary(**row) if row else None

    def delete_imported_conversation_summary(self, conversation_id: int) -> bool:
        """Delete a conversation's summary by conversation ID."""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM imported_conversation_summaries WHERE conversation_id = %s",
                    (conversation_id,),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)
