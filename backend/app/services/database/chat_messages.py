"""
Chat messages database operations.

Handles CRUD operations for chat_messages table.
"""

import logging
from datetime import datetime
from typing import List, NamedTuple

import psycopg2
import psycopg2.extras
from psycopg2.extensions import cursor

logger = logging.getLogger(__name__)


class ChatMessageData(NamedTuple):
    """Chat message data."""

    id: int
    idea_id: int
    role: str
    content: str
    sequence_number: int
    created_at: datetime
    sent_by_user_id: int
    sent_by_user_name: str
    sent_by_user_email: str


class ChatMessagesMixin:
    """Database operations for chat messages."""

    def get_chat_messages(self, idea_id: int) -> List[ChatMessageData]:
        """Get all chat messages for an idea, ordered by sequence number."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT cm.id, cm.idea_id, cm.role, cm.content,
                           cm.sequence_number, cm.created_at, cm.sent_by_user_id,
                           u.name as sent_by_user_name, u.email as sent_by_user_email
                    FROM chat_messages cm
                    JOIN users u ON cm.sent_by_user_id = u.id
                    WHERE cm.idea_id = %s
                    ORDER BY cm.sequence_number ASC
                    """,
                    (idea_id,),
                )
                return [ChatMessageData(**row) for row in cursor.fetchall()]

    def create_chat_message(
        self, idea_id: int, role: str, content: str, sent_by_user_id: int
    ) -> int:
        """Create a new chat message with the next sequence number."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                # Get the next sequence number
                sequence_number = self._get_next_sequence_number(cursor, idea_id)

                cursor.execute(
                    "INSERT INTO chat_messages (idea_id, role, content, sequence_number, sent_by_user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (idea_id, role, content, sequence_number, sent_by_user_id),
                )
                result = cursor.fetchone()
                message_id = int(result[0]) if result else 0
                conn.commit()
                return message_id

    def _get_next_sequence_number(self, cursor: cursor, idea_id: int) -> int:
        """Get the next sequence number for an idea."""
        cursor.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM chat_messages WHERE idea_id = %s",
            (idea_id,),
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 1

    def get_chat_messages_for_ids(self, message_ids: List[int]) -> List[ChatMessageData]:
        """Get chat messages by a list of ids."""
        if not message_ids:
            return []
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT cm.id, cm.idea_id, cm.role, cm.content,
                           cm.sequence_number, cm.created_at, cm.sent_by_user_id,
                           u.name as sent_by_user_name, u.email as sent_by_user_email
                    FROM chat_messages cm
                    JOIN users u ON cm.sent_by_user_id = u.id
                    WHERE cm.id = ANY(%s)
                    ORDER BY cm.id ASC
                    """,
                    (message_ids,),
                )
                return [ChatMessageData(**row) for row in cursor.fetchall()]
