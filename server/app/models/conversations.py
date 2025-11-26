"""
Conversation-related Pydantic models.

This module contains all models related to conversation management,
parsing, importing, and summarization.
"""

from datetime import datetime
from typing import Annotated, List, Literal, NamedTuple, Optional, Union

from pydantic import BaseModel, Field


class ImportedChatMessage(BaseModel):
    """Represents a single message in a conversation."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content as Markdown")


class ImportedChat(BaseModel):
    """Represents extracted conversation data from a shared URL."""

    url: str = Field(..., description="Original conversation share URL")
    title: str = Field(..., description="Conversation title")
    import_date: str = Field(..., description="ISO format import timestamp")
    content: List[ImportedChatMessage] = Field(..., description="List of conversation messages")


class ImportChatBase(BaseModel):
    """Common fields for conversation import from shared URL."""

    url: str = Field(..., description="Share URL to import (ChatGPT or BranchPrompt)")
    llm_model: str = Field(..., description="LLM model to use", min_length=1)
    llm_provider: str = Field(..., description="LLM provider to use", min_length=1)
    accept_summarization: bool = Field(
        ...,  # required (no defaults)
        description=(
            "Whether to proceed by summarizing when the imported chat exceeds the selected model's context window"
        ),
    )


class ImportChatPrompt(ImportChatBase):
    duplicate_resolution: Literal["prompt"]


class ImportChatCreateNew(ImportChatBase):
    duplicate_resolution: Literal["create_new"]


class ImportChatUpdateExisting(ImportChatBase):
    duplicate_resolution: Literal["update_existing"]
    target_conversation_id: int = Field(
        ..., description="Conversation ID to update when duplicate_resolution is update_existing"
    )


ImportChatGPTConversation = Annotated[
    Union[ImportChatPrompt, ImportChatCreateNew, ImportChatUpdateExisting],
    Field(discriminator="duplicate_resolution"),
]


class ConversationUpdate(BaseModel):
    """Data required to update a conversation."""

    title: str = Field(..., description="New title for the conversation", min_length=1)


class ConversationResponse(BaseModel):
    """Response model for conversation API endpoints."""

    id: int = Field(..., description="Database ID of the conversation")
    url: str = Field(..., description="Original conversation share URL")
    title: str = Field(..., description="Conversation title")
    import_date: str = Field(..., description="ISO format import timestamp")
    created_at: str = Field(..., description="ISO format creation timestamp")
    updated_at: str = Field(..., description="ISO format last update timestamp")
    has_images: Optional[bool] = Field(None, description="Whether conversation contains images")
    has_pdfs: Optional[bool] = Field(None, description="Whether conversation contains PDFs")
    user_id: int = Field(..., description="ID of the user who imported the conversation")
    user_name: str = Field(..., description="Name of the user who imported the conversation")
    user_email: str = Field(..., description="Email of the user who imported the conversation")
    imported_chat: Optional[List[ImportedChatMessage]] = Field(
        None, description="Conversation messages (optional)"
    )


class ParseSuccessResult(BaseModel):
    """Successful parsing result."""

    success: bool = Field(True, description="Always true for success results")
    data: ImportedChat = Field(..., description="Parsed conversation data")


class ParseErrorResult(BaseModel):
    """Failed parsing result."""

    success: bool = Field(False, description="Always false for error results")
    error: str = Field(..., description="Error message describing what went wrong")


ParseResult = Union[ParseSuccessResult, ParseErrorResult]


class ChatMessageData(NamedTuple):
    """Chat message data."""

    id: int
    idea_id: int
    role: str
    content: str
    sequence_number: int
    created_at: datetime
