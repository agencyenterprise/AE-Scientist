"""
Chat-related Pydantic models.

This module contains all models related to chat functionality,
including messages, requests, and responses for LLM conversations.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.ideas import Idea


class ChatMessage(BaseModel):
    """Represents a single chat message."""

    role: str = Field(..., description="Message role ('user' or 'assistant')")
    content: str = Field(..., description="Message content")
    sequence_number: int = Field(..., description="Sequence number for ordering")
    created_at: str = Field(..., description="ISO format creation timestamp")
    sent_by_user_id: int = Field(..., description="ID of the user who sent this message")
    sent_by_user_name: str = Field(..., description="Name of the user who sent this message")
    sent_by_user_email: str = Field(..., description="Email of the user who sent this message")
    attachments: List["FileAttachment"] = Field(
        default_factory=list, description="File attachments for this message"
    )


class ChatRequest(BaseModel):
    """Request model for sending a chat message."""

    message: str = Field(..., description="User message content", min_length=1)
    llm_provider: str = Field(..., description="LLM provider to use", min_length=1)
    llm_model: str = Field(..., description="LLM model to use", min_length=1)
    attachment_ids: List[int] = Field(
        default_factory=list, description="List of file attachment IDs to include with this message"
    )


class FileAttachment(BaseModel):
    """File attachment model for chat messages."""

    id: int = Field(..., description="Unique attachment ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type of the file")
    s3_key: str = Field(..., description="S3 storage key")
    created_at: str = Field(..., description="ISO format creation timestamp")


class ChatResponse(BaseModel):
    """Response model for chat API endpoints."""

    success: bool = Field(..., description="Whether the operation was successful")
    llm_response: str = Field(..., description="LLM's response message")
    idea_updated: bool = Field(..., description="Whether the idea was updated")
    new_idea: Optional[Idea] = Field(None, description="Updated idea if it was modified")
    chat_messages: List[ChatMessage] = Field(
        default_factory=list, description="Complete chat message history"
    )
    error: Optional[str] = Field(None, description="Error message if operation failed")
