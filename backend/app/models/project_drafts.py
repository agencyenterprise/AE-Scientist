"""
Project Draft-related Pydantic models.

This module contains all models related to project draft management,
AI generation, refinement, and version control.
"""

from typing import List, Optional

from app.config import settings
from pydantic import BaseModel, Field


class ProjectDraftVersion(BaseModel):
    """Represents a single version of a project draft."""

    version_id: int = Field(..., description="Version ID")
    title: str = Field(..., description="Project title")
    description: str = Field(..., description="Project description")
    is_manual_edit: bool = Field(
        ..., description="Whether this version was manually edited by user"
    )
    version_number: int = Field(..., description="Version number for ordering")
    created_at: str = Field(..., description="ISO format creation timestamp")


class ProjectDraft(BaseModel):
    """Represents a project draft with its active version."""

    project_draft_id: int = Field(..., description="Project draft ID")
    conversation_id: int = Field(..., description="Associated conversation ID")
    active_version: Optional[ProjectDraftVersion] = Field(
        None, description="Currently active version"
    )
    created_at: str = Field(..., description="ISO format creation timestamp")
    updated_at: str = Field(..., description="ISO format last update timestamp")


class ProjectDraftCreateRequest(BaseModel):
    """Request model for manually creating/updating project draft."""

    title: str = Field(
        ..., description="Project title", min_length=1, max_length=settings.MAX_PROJECT_TITLE_LENGTH
    )
    description: str = Field(..., description="Project description", min_length=1)
    user_prompt: Optional[str] = Field(
        None, description="User prompt that generated this refinement"
    )


class ProjectDraftRefinementRequest(BaseModel):
    """Request model for LLM-based project refinement."""

    user_prompt: str = Field(..., description="User prompt for refinement", min_length=1)


class ProjectDraftRefinementSuggestion(BaseModel):
    """LLM suggestion for project refinement."""

    title: str = Field(..., description="Suggested project title")
    description: str = Field(..., description="Suggested project description")
    explanation: str = Field(..., description="Explanation of changes made")


class ProjectDraftResponse(BaseModel):
    """Response model for project draft API endpoints."""

    success: bool = Field(..., description="Whether the operation was successful")
    project_draft: Optional[ProjectDraft] = Field(None, description="Project draft data")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class ProjectDraftVersionsResponse(BaseModel):
    """Response model for project draft versions."""

    success: bool = Field(..., description="Whether the operation was successful")
    versions: List[ProjectDraftVersion] = Field(
        default_factory=list, description="List of project draft versions"
    )
    error: Optional[str] = Field(None, description="Error message if operation failed")


class ProjectDraftRefinementResponse(BaseModel):
    """Response model for project draft refinement."""

    success: bool = Field(..., description="Whether the operation was successful")
    suggestion: Optional[ProjectDraftRefinementSuggestion] = Field(
        None, description="LLM refinement suggestion"
    )
    error: Optional[str] = Field(None, description="Error message if operation failed")
