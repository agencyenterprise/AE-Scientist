"""
File attachments database operations.

Handles CRUD operations for file_attachments table.
"""

import logging
from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class FileAttachmentData(NamedTuple):
    """File attachment data."""

    id: int
    chat_message_id: Optional[int]
    conversation_id: int
    filename: str
    file_size: int
    file_type: str
    s3_key: str
    created_at: datetime
    uploaded_by_user_id: int
    extracted_text: Optional[str]
    summary_text: Optional[str]


class AttachmentTexts(NamedTuple):
    """Attachment extracted and summary text container (never optional)."""

    extracted_text: str
    summary_text: str


class FileAttachmentsMixin(ConnectionProvider):
    """Database operations for file attachments."""

    def create_file_attachment_upload(
        self,
        conversation_id: int,
        filename: str,
        file_size: int,
        file_type: str,
        s3_key: str,
        uploaded_by_user_id: int,
    ) -> int:
        """
        Create a new file attachment record for an upload (not yet linked to a message).

        Args:
            conversation_id: ID of the conversation this file belongs to
            filename: Original filename
            file_size: File size in bytes
            file_type: MIME type of the file
            s3_key: S3 storage key
            uploaded_by_user_id: ID of the user who uploaded the file

        Returns:
            ID of the created file attachment

        Raises:
            Exception: If database operation fails
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO file_attachments (conversation_id, filename, file_size, file_type, s3_key, uploaded_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (conversation_id, filename, file_size, file_type, s3_key, uploaded_by_user_id),
                )
                result = cursor.fetchone()
                attachment_id = int(result[0]) if result else 0
                conn.commit()
                return attachment_id

    def update_file_attachment_message_id(self, attachment_id: int, chat_message_id: int) -> bool:
        """
        Update an existing file attachment to link it to a chat message.

        Args:
            attachment_id: ID of the file attachment to update
            chat_message_id: ID of the chat message to link to

        Returns:
            True if attachment was updated, False if not found

        Raises:
            Exception: If database operation fails
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE file_attachments
                    SET chat_message_id = %s
                    WHERE id = %s AND chat_message_id IS NULL
                    """,
                    (chat_message_id, attachment_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def get_file_attachments_by_message_ids(
        self, chat_message_ids: List[int]
    ) -> List[FileAttachmentData]:
        """
        Get all file attachments for multiple chat messages.

        Args:
            chat_message_ids: List of chat message IDs

        Returns:
            List of FileAttachmentData objects

        Raises:
            Exception: If database operation fails
        """
        if not chat_message_ids:
            return []

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, chat_message_id, conversation_id, filename, file_size, file_type, s3_key, created_at, uploaded_by_user_id, extracted_text, summary_text
                    FROM file_attachments
                    WHERE chat_message_id = ANY(%s)
                    ORDER BY created_at ASC
                    """,
                    (chat_message_ids,),
                )
                rows = cursor.fetchall()
                return [FileAttachmentData(**row) for row in rows]

    def get_file_attachments_by_ids(self, attachment_ids: List[int]) -> List[FileAttachmentData]:
        """
        Get multiple file attachments by their IDs.

        Args:
            attachment_ids: List of file attachment IDs

        Returns:
            List of FileAttachmentData objects

        Raises:
            Exception: If database operation fails
        """
        if not attachment_ids:
            return []

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Use tuple for IN clause
                placeholders = ",".join(["%s"] * len(attachment_ids))
                cursor.execute(
                    f"""
                    SELECT id, chat_message_id, conversation_id, filename, file_size, file_type, s3_key, created_at, uploaded_by_user_id, extracted_text, summary_text
                    FROM file_attachments
                    WHERE id IN ({placeholders})
                    ORDER BY created_at ASC
                    """,
                    attachment_ids,
                )
                rows = cursor.fetchall()
                return [FileAttachmentData(**row) for row in rows]

    def get_conversation_file_attachments(self, conversation_id: int) -> List[FileAttachmentData]:
        """
        Get all file attachments for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of FileAttachmentData objects

        Raises:
            Exception: If database operation fails
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, chat_message_id, conversation_id, filename, file_size, file_type, s3_key, created_at, uploaded_by_user_id
                    FROM file_attachments
                    WHERE conversation_id = %s
                    ORDER BY created_at ASC
                    """,
                    (conversation_id,),
                )
                rows = cursor.fetchall()
                return [FileAttachmentData(**row) for row in rows]

    def update_attachment_texts(
        self, attachment_id: int, extracted_text: str, summary_text: str
    ) -> bool:
        """
        Update extracted_text and summary_text for a file attachment.

        Args:
            attachment_id: File attachment ID
            extracted_text: Full extracted text content
            summary_text: Summary text content

        Returns:
            True if the record was updated, False otherwise
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE file_attachments
                    SET extracted_text = %s, summary_text = %s
                    WHERE id = %s
                    """,
                    (extracted_text, summary_text, attachment_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)
