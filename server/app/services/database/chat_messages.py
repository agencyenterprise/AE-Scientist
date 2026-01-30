"""
Chat messages database operations.

Handles CRUD operations for chat_messages table.
"""

import logging
from datetime import datetime
from typing import Any, List, NamedTuple

from psycopg import AsyncCursor
from psycopg.rows import dict_row

from .base import ConnectionProvider

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


class ChatMessagesMixin(ConnectionProvider):
    """Database operations for chat messages."""

    async def get_chat_messages(self, idea_id: int) -> List[ChatMessageData]:
        """Get all chat messages for an idea, ordered by sequence number."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
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
                rows = await cursor.fetchall()
                return [ChatMessageData(**row) for row in rows]

    async def create_chat_message(
        self, idea_id: int, role: str, content: str, sent_by_user_id: int
    ) -> int:
        """Create a new chat message with the next sequence number."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                sequence_number = await self._get_next_sequence_number(cursor, idea_id)

                await cursor.execute(
                    "INSERT INTO chat_messages (idea_id, role, content, sequence_number, sent_by_user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (idea_id, role, content, sequence_number, sent_by_user_id),
                )
                result = await cursor.fetchone()
                message_id = int(result[0]) if result else 0
                await conn.commit()
                return message_id

    async def _get_next_sequence_number(self, cursor: AsyncCursor[Any], idea_id: int) -> int:
        """Get the next sequence number for an idea."""
        await cursor.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM chat_messages WHERE idea_id = %s",
            (idea_id,),
        )
        result = await cursor.fetchone()
        return int(result[0]) if result else 1

    async def get_chat_messages_for_ids(self, message_ids: List[int]) -> List[ChatMessageData]:
        """Get chat messages by a list of ids."""
        if not message_ids:
            return []
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
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
                rows = await cursor.fetchall()
                return [ChatMessageData(**row) for row in rows]

    async def update_chat_message_content(self, message_id: int, content: str) -> bool:
        """Update the content of an existing chat message."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE chat_messages SET content = %s WHERE id = %s",
                    (content, message_id),
                )
                await conn.commit()
                return bool(cursor.rowcount > 0)

    async def delete_chat_message(self, message_id: int) -> bool:
        """Delete a chat message."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM chat_messages WHERE id = %s",
                    (message_id,),
                )
                await conn.commit()
                return bool(cursor.rowcount > 0)
