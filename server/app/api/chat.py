"""
Chat API endpoints for idea conversations.

This module contains FastAPI routes for retrieving chat history for a conversation's idea.
"""

import logging
from typing import List, Optional, Union

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.models.chat import ChatMessage, FileAttachment
from app.services import get_database

router = APIRouter(prefix="/conversations")

logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    chat_messages: List[ChatMessage] = Field(..., description="List of chat messages")


@router.get("/{conversation_id}/idea/chat")
async def get_chat_history(
    conversation_id: int, response: Response
) -> Union[ChatHistoryResponse, ErrorResponse]:
    """
    Get chat history for a conversation's idea.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    try:
        # Check if conversation exists
        existing_conversation = db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            response.status_code = 404
            return ErrorResponse(error="Conversation not found", detail="Conversation not found")

        # Check if idea exists
        idea_data = db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            # Return empty chat history if no idea exists yet
            return ChatHistoryResponse(chat_messages=[])

        # Get chat messages from database
        chat_messages_data = db.get_chat_messages(idea_data.idea_id)
        file_attachments = db.get_file_attachments_by_message_ids(
            [msg.id for msg in chat_messages_data]
        )

        # Convert to ChatMessage models with file attachments
        chat_messages = []
        for msg in chat_messages_data:
            # Get file attachments for this message

            # Convert to FileAttachment models
            attachments = [
                FileAttachment(
                    id=fa.id,
                    filename=fa.filename,
                    file_size=fa.file_size,
                    file_type=fa.file_type,
                    s3_key=fa.s3_key,
                    created_at=fa.created_at.isoformat(),
                )
                for fa in file_attachments
                if fa.chat_message_id == msg.id
            ]

            chat_message = ChatMessage(
                role=msg.role,
                content=msg.content,
                sequence_number=msg.sequence_number,
                created_at=msg.created_at.isoformat(),
                sent_by_user_id=msg.sent_by_user_id,
                sent_by_user_name=msg.sent_by_user_name,
                sent_by_user_email=msg.sent_by_user_email,
                attachments=attachments,
            )
            chat_messages.append(chat_message)

        return ChatHistoryResponse(chat_messages=chat_messages)

    except Exception as e:
        logger.exception(f"Error getting chat history: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Chat history failed", detail=f"Failed to get chat history: {str(e)}"
        )
