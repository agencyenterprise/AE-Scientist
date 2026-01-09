"""
Conversation database operations.

Handles CRUD operations for conversations table.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider

logger = logging.getLogger(__name__)

CONVERSATION_STATUSES = ("draft", "with_research")


class ImportedChatMessage(NamedTuple):
    """Represents a single message in a conversation."""

    role: str
    content: str


class Conversation(NamedTuple):
    """Represents extracted conversation data from ChatGPT."""

    url: str
    title: str
    import_date: str
    imported_chat: List[ImportedChatMessage]


class FullConversation(NamedTuple):
    """Detailed conversation response including all messages."""

    id: int
    url: str
    title: str
    import_date: str
    created_at: datetime
    updated_at: datetime
    has_images: Optional[bool]
    has_pdfs: Optional[bool]
    user_id: int
    user_name: str
    user_email: str
    imported_chat: Optional[List[ImportedChatMessage]]
    manual_title: Optional[str]
    manual_hypothesis: Optional[str]
    status: str  # Conversation status: 'draft' or 'with_research'


class DashboardConversation(NamedTuple):
    """Conversation fields for dashboard list view (from DB view)."""

    id: int
    url: str
    title: str
    import_date: str
    created_at: datetime
    updated_at: datetime
    user_id: int
    user_name: str
    user_email: str
    idea_title: Optional[str]
    idea_abstract: Optional[str]
    last_user_message_content: Optional[str]
    last_assistant_message_content: Optional[str]
    manual_title: Optional[str]
    manual_hypothesis: Optional[str]
    status: str  # Conversation status: 'draft' or 'with_research'


class UrlConversationBrief(NamedTuple):
    id: int
    title: str
    updated_at: datetime
    url: str


class ConversationsMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Database operations for conversations."""

    async def create_conversation(
        self, conversation: Conversation, imported_by_user_id: int
    ) -> int:
        """Create a new conversation in the database."""
        now = datetime.now()
        content_data = [msg._asdict() for msg in conversation.imported_chat]

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO conversations
                    (url, title, import_date, imported_chat, created_at, updated_at, imported_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        conversation.url,
                        conversation.title,
                        conversation.import_date,
                        Jsonb(content_data),
                        now,
                        now,
                        imported_by_user_id,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create conversation: no ID returned")

                return int(result["id"])

    async def get_conversation_by_id(self, conversation_id: int) -> Optional[FullConversation]:
        """Get a conversation by its ID, including full content and file attachment flags."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT c.id, c.url, c.title, c.import_date, c.imported_chat,
                           c.created_at, c.updated_at, c.status,
                           u.id as user_id, u.name as user_name, u.email as user_email,
                           EXISTS(
                               SELECT 1 FROM file_attachments fa
                               WHERE fa.conversation_id = c.id
                               AND fa.file_type LIKE 'image/%%'
                           ) as has_images,
                           EXISTS(
                               SELECT 1 FROM file_attachments fa
                               WHERE fa.conversation_id = c.id
                               AND fa.file_type = 'application/pdf'
                           ) as has_pdfs,
                           c.manual_title,
                           c.manual_hypothesis
                    FROM conversations c
                    JOIN users u ON c.imported_by_user_id = u.id
                    WHERE c.id = %s
                """,
                    (conversation_id,),
                )
                row = await cursor.fetchone()

        if not row:
            return None

        content_data = row["imported_chat"]
        if isinstance(content_data, str):
            content_data = json.loads(content_data)
        content = [
            ImportedChatMessage(
                role=msg.get("role", ""),
                content=msg.get("content", ""),
            )
            for msg in content_data
        ]

        return FullConversation(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            import_date=row["import_date"].isoformat(),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            has_images=row["has_images"],
            has_pdfs=row["has_pdfs"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            user_email=row["user_email"],
            imported_chat=content,
            manual_title=row.get("manual_title"),
            manual_hypothesis=row.get("manual_hypothesis"),
            status=row["status"],
        )

    async def get_conversation_id_by_url(self, url: str) -> Optional[int]:
        """Get a conversation by its URL (without full content)."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT id
                    FROM conversations
                    WHERE url = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """,
                    (url,),
                )
                row = await cursor.fetchone()

        if not row:
            return None

        return int(row["id"])

    async def list_conversations_by_url(self, url: str) -> List[UrlConversationBrief]:
        """List conversations with the same URL, newest first, for conflict resolution UI."""

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT id, title, updated_at, url
                    FROM conversations
                    WHERE url = %s
                    ORDER BY updated_at DESC
                """,
                    (url,),
                )
                rows = await cursor.fetchall() or []

        return [
            UrlConversationBrief(
                id=row["id"], title=row["title"], updated_at=row["updated_at"], url=row["url"]
            )
            for row in rows
        ]

    async def list_conversations_by_title_substring(
        self, title_query: str
    ) -> List[UrlConversationBrief]:
        """List conversations where the title contains the given query (case-insensitive).

        Orders prefix matches first, then by most recently updated.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                substring_pattern = f"%{title_query}%"
                prefix_pattern = f"{title_query}%"
                await cursor.execute(
                    """
                    SELECT id, title, updated_at, url
                    FROM conversations
                    WHERE title ILIKE %s
                    ORDER BY (title ILIKE %s) DESC, updated_at DESC
                """,
                    (substring_pattern, prefix_pattern),
                )
                rows = await cursor.fetchall() or []

        return [
            UrlConversationBrief(
                id=row["id"], title=row["title"], updated_at=row["updated_at"], url=row["url"]
            )
            for row in rows
        ]

    async def list_conversations(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
        conversation_status: str | None = None,
        run_status: str | None = None,
    ) -> List[DashboardConversation]:
        """List conversations for dashboard with optional filtering and pagination.

        Args:
            limit: Max results (default 100, max 1000)
            offset: Pagination offset (default 0)
            user_id: Filter by user (required for API endpoint)
            conversation_status: Filter by "draft" or "with_research" (optional)
            run_status: Filter by run status (optional)

        Returns:
            List of DashboardConversation objects

        Note: Filters are ANDed together. When run_status is provided,
        only conversations with at least one matching run are returned.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                query = """
                    SELECT
                        c.id,
                        c.url,
                        c.title,
                        c.import_date,
                        c.created_at,
                        c.updated_at,
                        c.imported_by_user_id AS user_id,
                        u.name AS user_name,
                        u.email AS user_email,
                        iv.title AS idea_title,
                        iv.abstract AS idea_abstract,
                        (
                            SELECT cm.content
                            FROM chat_messages cm
                            WHERE cm.idea_id = i.id AND cm.role = 'user'
                            ORDER BY cm.sequence_number DESC
                            LIMIT 1
                        ) AS last_user_message_content,
                        (
                            SELECT cm.content
                            FROM chat_messages cm
                            WHERE cm.idea_id = i.id AND cm.role = 'assistant'
                            ORDER BY cm.sequence_number DESC
                            LIMIT 1
                        ) AS last_assistant_message_content,
                        c.manual_title,
                        c.manual_hypothesis,
                        c.status
                    FROM conversations c
                    LEFT JOIN users u ON c.imported_by_user_id = u.id
                    LEFT JOIN ideas i ON i.conversation_id = c.id
                    LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
                """

                params: list = []
                where_conditions: list = []

                # Add user filter (required for API)
                if user_id is not None:
                    where_conditions.append("c.imported_by_user_id = %s")
                    params.append(user_id)

                # Add conversation status filter
                if conversation_status is not None:
                    where_conditions.append("c.status = %s")
                    params.append(conversation_status)

                # Add research run status filter using EXISTS subquery
                # (avoids JOIN + DISTINCT which conflicts with ORDER BY in subqueries)
                if run_status is not None:
                    where_conditions.append(
                        "EXISTS (SELECT 1 FROM research_pipeline_runs rpr "
                        "WHERE rpr.idea_id = i.id AND rpr.status = %s)"
                    )
                    params.append(run_status)

                # Build complete WHERE clause
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)

                # Add ordering and pagination
                query += " ORDER BY c.updated_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                await cursor.execute(query, params)
                rows = await cursor.fetchall()

        return [
            DashboardConversation(
                id=row["id"],
                url=row["url"],
                title=row["title"],
                import_date=row["import_date"].isoformat(),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                user_email=row["user_email"],
                idea_title=row.get("idea_title"),
                idea_abstract=row.get("idea_abstract"),
                last_user_message_content=row.get("last_user_message_content"),
                last_assistant_message_content=row.get("last_assistant_message_content"),
                manual_title=row.get("manual_title"),
                manual_hypothesis=row.get("manual_hypothesis"),
                status=row["status"],
            )
            for row in rows
        ]

    async def create_manual_conversation(
        self,
        *,
        manual_title: str,
        manual_hypothesis: str,
        imported_by_user_id: int,
    ) -> int:
        """Create a conversation originating from manual seed data."""
        now = datetime.now()
        manual_url = f"manual://{uuid.uuid4()}"
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO conversations
                        (url, title, import_date, imported_chat, created_at, updated_at,
                         imported_by_user_id, manual_title, manual_hypothesis)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        manual_url,
                        manual_title,
                        now,
                        Jsonb([]),
                        now,
                        now,
                        imported_by_user_id,
                        manual_title,
                        manual_hypothesis,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create manual conversation: no ID returned")
                return int(result["id"])

    async def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation by its ID. Returns True if deleted, False if not found."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
                return bool(cursor.rowcount > 0)

    async def update_conversation_title(self, conversation_id: int, new_title: str) -> bool:
        """Update a conversation's title. Returns True if updated, False if not found."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
                    (new_title, now, conversation_id),
                )
                return bool(cursor.rowcount > 0)

    async def update_conversation_messages(
        self, conversation_id: int, messages: List[ImportedChatMessage]
    ) -> bool:
        """Update an existing conversation's messages with new data. Returns updated conversation."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE conversations
                    SET imported_chat = %s, updated_at = %s
                    WHERE id = %s
                """,
                    (
                        Jsonb([msg._asdict() for msg in messages]),
                        now,
                        conversation_id,
                    ),
                )
        return True

    async def update_conversation_status(self, conversation_id: int, status: str) -> bool:
        """
        Update conversation status to 'with_research' after research run created.

        Args:
            conversation_id: ID of conversation to update
            status: New status value (validated against CONVERSATION_STATUSES)

        Returns:
            True if updated, False if not found

        Raises:
            ValueError: If status not in CONVERSATION_STATUSES
        """
        if status not in CONVERSATION_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(CONVERSATION_STATUSES)}"
            )

        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE conversations
                    SET status = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (status, now, conversation_id),
                )
                return bool(cursor.rowcount > 0)
