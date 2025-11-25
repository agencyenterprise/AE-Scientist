"""
Project-related Pydantic models.

This module contains all models related to Linear project management,
creation, and integration with conversations.
"""

from typing import Optional

from app.config import settings
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request model for creating a new project."""

    title: str = Field(
        ..., description="Project title", min_length=1, max_length=settings.MAX_PROJECT_TITLE_LENGTH
    )
    description: str = Field(..., description="Project description", min_length=1)


class Project(BaseModel):
    """Represents a Linear project."""

    id: int = Field(..., description="Database project ID")
    conversation_id: int = Field(..., description="Associated conversation ID")
    linear_project_id: str = Field(..., description="Linear project ID")
    title: str = Field(..., description="Project title")
    description: str = Field(..., description="Project description")
    linear_url: str = Field(..., description="Linear project URL")
    created_at: str = Field(..., description="ISO format creation timestamp")


class ProjectResponse(BaseModel):
    """Response model for project API endpoints."""

    success: bool = Field(..., description="Whether the operation was successful")
    project: Optional[Project] = Field(None, description="Project data")
    error: Optional[str] = Field(None, description="Error message if operation failed")
