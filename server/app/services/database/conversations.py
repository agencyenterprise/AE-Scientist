"""
Conversation database operations.

Handles CRUD operations for conversations table.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


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


class UrlConversationBrief(NamedTuple):
    id: int
    title: str
    updated_at: datetime
    url: str


class ConversationsMixin:
    """Database operations for conversations."""

    def create_conversation(self, conversation: Conversation, imported_by_user_id: int) -> int:
        """Create a new conversation in the database."""
        now = datetime.now()
        content_data = [msg._asdict() for msg in conversation.imported_chat]

        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
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
                        json.dumps(content_data),
                        now,
                        now,
                        imported_by_user_id,
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create conversation: no ID returned")

                conversation_id = int(result["id"])
                conn.commit()

        return conversation_id

    def get_conversation_by_id(self, conversation_id: int) -> Optional[FullConversation]:
        """Get a conversation by its ID, including full content and file attachment flags."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT c.id, c.url, c.title, c.import_date, c.imported_chat,
                           c.created_at, c.updated_at,
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
                           ) as has_pdfs
                           , c.manual_title, c.manual_hypothesis
                    FROM conversations c
                    JOIN users u ON c.imported_by_user_id = u.id
                    WHERE c.id = %s
                """,
                    (conversation_id,),
                )
                row = cursor.fetchone()

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
        )

    def get_conversation_id_by_url(self, url: str) -> Optional[int]:
        """Get a conversation by its URL (without full content)."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM conversations
                    WHERE url = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """,
                    (url,),
                )
                row = cursor.fetchone()

        if not row:
            return None

        return int(row["id"])

    def list_conversations_by_url(self, url: str) -> List[UrlConversationBrief]:
        """List conversations with the same URL, newest first, for conflict resolution UI."""

        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, title, updated_at, url
                    FROM conversations
                    WHERE url = %s
                    ORDER BY updated_at DESC
                """,
                    (url,),
                )
                rows = cursor.fetchall() or []

        return [
            UrlConversationBrief(
                id=row["id"], title=row["title"], updated_at=row["updated_at"], url=row["url"]
            )
            for row in rows
        ]

    def list_conversations_by_title_substring(self, title_query: str) -> List[UrlConversationBrief]:
        """List conversations where the title contains the given query (case-insensitive).

        Orders prefix matches first, then by most recently updated.
        """
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                substring_pattern = f"%{title_query}%"
                prefix_pattern = f"{title_query}%"
                cursor.execute(
                    """
                    SELECT id, title, updated_at, url
                    FROM conversations
                    WHERE title ILIKE %s
                    ORDER BY (title ILIKE %s) DESC, updated_at DESC
                """,
                    (substring_pattern, prefix_pattern),
                )
                rows = cursor.fetchall() or []

        return [
            UrlConversationBrief(
                id=row["id"], title=row["title"], updated_at=row["updated_at"], url=row["url"]
            )
            for row in rows
        ]

    def list_conversations(
        self, limit: int = 100, offset: int = 0, user_id: int | None = None
    ) -> List[DashboardConversation]:
        """List conversations for dashboard (from view), with pagination."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                query = """
                    SELECT id, url, title, import_date, created_at, updated_at,
                           user_id, user_name, user_email,
                           idea_title, idea_abstract,
                           last_user_message_content, last_assistant_message_content,
                           manual_title, manual_hypothesis
                    FROM conversation_dashboard_view
                """
                params: list = []
                if user_id is not None:
                    query += " WHERE user_id = %s"
                    params.append(user_id)
                query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()

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
            )
            for row in rows
        ]

    def create_manual_conversation(
        self,
        *,
        manual_title: str,
        manual_hypothesis: str,
        imported_by_user_id: int,
    ) -> int:
        """Create a conversation originating from manual seed data."""
        now = datetime.now()
        manual_url = f"manual://{uuid.uuid4()}"
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
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
                        json.dumps([]),
                        now,
                        now,
                        imported_by_user_id,
                        manual_title,
                        manual_hypothesis,
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create manual conversation: no ID returned")
                conversation_id = int(result["id"])
                conn.commit()
        return conversation_id

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation by its ID. Returns True if deleted, False if not found."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
                conn.commit()
                return bool(cursor.rowcount > 0)

    def update_conversation_title(self, conversation_id: int, new_title: str) -> bool:
        """Update a conversation's title. Returns True if updated, False if not found."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
                    (new_title, now, conversation_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def update_conversation_messages(
        self, conversation_id: int, messages: List[ImportedChatMessage]
    ) -> bool:
        """Update an existing conversation's messages with new data. Returns updated conversation."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE conversations
                    SET imported_chat = %s, updated_at = %s
                    WHERE id = %s
                """,
                    (
                        json.dumps([msg._asdict() for msg in messages]),
                        now,
                        conversation_id,
                    ),
                )
                conn.commit()

        return True

    def conversation_is_locked(self, _conversation_id: int) -> bool:
        """Check if a conversation is locked (deprecated - always returns False)."""
        # Conversations are no longer locked since Linear integration was removed
        return False
