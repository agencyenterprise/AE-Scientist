"""
Idea-related Pydantic models.

This module contains all models related to research idea management,
AI generation, refinement, and version control.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class IdeaVersion(BaseModel):
    """Represents a single version of a research idea."""

    version_id: int = Field(..., description="Version ID")
    title: str = Field(..., description="Title of the research idea")
    idea_markdown: str = Field(..., description="Research idea in markdown format")
    is_manual_edit: bool = Field(
        ..., description="Whether this version was manually edited by user"
    )
    version_number: int = Field(..., description="Version number for ordering")
    created_at: str = Field(..., description="ISO format creation timestamp")


class Idea(BaseModel):
    """Represents a research idea with its active version."""

    idea_id: int = Field(..., description="Idea ID")
    conversation_id: int = Field(..., description="Associated conversation ID")
    active_version: Optional[IdeaVersion] = Field(None, description="Currently active version")
    created_at: str = Field(..., description="ISO format creation timestamp")
    updated_at: str = Field(..., description="ISO format last update timestamp")


class IdeaCreateRequest(BaseModel):
    """Request model for manually creating/updating an idea."""

    idea_markdown: str = Field(..., description="Research idea in markdown format", min_length=1)
    user_prompt: Optional[str] = Field(
        None, description="User prompt that generated this refinement"
    )


class IdeaRefinementRequest(BaseModel):
    """Request model for manually updating an idea with all fields."""

    title: str = Field(..., description="Title of the research idea")
    idea_markdown: str = Field(..., description="Research idea in markdown format")


class IdeaResponse(BaseModel):
    """Response model for idea API endpoints."""

    success: bool = Field(..., description="Whether the operation was successful")
    idea: Optional[Idea] = Field(None, description="Idea data")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class IdeaVersionsResponse(BaseModel):
    """Response model for idea versions."""

    success: bool = Field(..., description="Whether the operation was successful")
    versions: List[IdeaVersion] = Field(default_factory=list, description="List of idea versions")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class IdeaRefinementResponse(BaseModel):
    """Response model for idea refinement."""

    success: bool = Field(..., description="Whether the operation was successful")
    suggestion: Optional[str] = Field(None, description="LLM-generated markdown suggestion")
    error: Optional[str] = Field(None, description="Error message if operation failed")
