"""
Conversation memories database operations.

Stores and retrieves memories blocks associated with conversations.
"""

import json
import logging
from typing import Any, Dict, List, NamedTuple

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class ConversationMemories(NamedTuple):
    """Represents stored memories block for a conversation and source."""

    id: int
    conversation_id: int
    memory_source: str
    memories: List[Dict[str, Any]]


class ConversationMemoriesMixin:
    """Database operations for conversation memories blocks."""

    def store_memories_block(
        self, conversation_id: int, source: str, memories_block: List[Dict[str, Any]]
    ) -> int:
        """Insert or replace memories block for a conversation and source. Returns row id."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversation_memories (conversation_id, memory_source, memories)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (conversation_id, memory_source)
                    DO UPDATE SET memories = EXCLUDED.memories
                    RETURNING id
                    """,
                    (conversation_id, source, json.dumps(memories_block)),
                )
                row = cursor.fetchone()
                conn.commit()
                if not row:
                    raise ValueError("Failed to upsert conversation_memories: no id returned")
                return int(row["id"])

    def get_memories_block(self, conversation_id: int, source: str) -> ConversationMemories:
        """Retrieve memories block for a conversation and source. Raises if not found."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, conversation_id, memory_source, memories
                    FROM conversation_memories
                    WHERE conversation_id = %s AND memory_source = %s
                    """,
                    (conversation_id, source),
                )
                row = cursor.fetchone()

        if not row:
            raise ValueError(
                f"Memories not found for conversation_id={conversation_id} source={source}"
            )

        memories_data = row["memories"]
        if isinstance(memories_data, str):
            memories_data = json.loads(memories_data)

        return ConversationMemories(
            id=row["id"],
            conversation_id=row["conversation_id"],
            memory_source=row["memory_source"],
            memories=memories_data,
        )
