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
    title: str = Field(..., description="Research idea title")
    short_hypothesis: str = Field(..., description="Short hypothesis statement")
    related_work: str = Field(..., description="Related work and background")
    abstract: str = Field(..., description="Detailed abstract of the idea")
    experiments: List[str] = Field(..., description="List of proposed experiments")
    expected_outcome: str = Field(..., description="Expected outcome of the research")
    risk_factors_and_limitations: List[str] = Field(..., description="Risk factors and limitations")
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

    title: str = Field(..., description="Research idea title", min_length=1)
    short_hypothesis: str = Field(..., description="Short hypothesis statement", min_length=1)
    related_work: str = Field(..., description="Related work and background", min_length=1)
    abstract: str = Field(..., description="Detailed abstract of the idea", min_length=1)
    experiments: List[str] = Field(..., description="List of proposed experiments", min_length=1)
    expected_outcome: str = Field(..., description="Expected outcome of the research", min_length=1)
    risk_factors_and_limitations: List[str] = Field(
        ..., description="Risk factors and limitations", min_length=1
    )
    user_prompt: Optional[str] = Field(
        None, description="User prompt that generated this refinement"
    )


class IdeaRefinementRequest(BaseModel):
    """Request model for manually updating an idea with all fields."""

    title: str = Field(..., description="Idea title")
    short_hypothesis: str = Field(..., description="Short hypothesis of the idea")
    related_work: str = Field(..., description="Related work or background")
    abstract: str = Field(..., description="Abstract of the idea")
    experiments: List[str] = Field(..., description="List of experiments")
    expected_outcome: str = Field(..., description="Expected outcome of the experiments")
    risk_factors_and_limitations: List[str] = Field(..., description="Risk factors and limitations")


class IdeaRefinementSuggestion(BaseModel):
    """LLM suggestion for idea refinement."""

    title: str = Field(..., description="Suggested idea title")
    short_hypothesis: str = Field(..., description="Suggested short hypothesis")
    related_work: str = Field(..., description="Suggested related work")
    abstract: str = Field(..., description="Suggested abstract")
    experiments: List[str] = Field(..., description="Suggested experiments list")
    expected_outcome: str = Field(..., description="Suggested expected outcome")
    risk_factors_and_limitations: List[str] = Field(
        ..., description="Suggested risk factors and limitations"
    )
    explanation: str = Field(..., description="Explanation of changes made")


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
    suggestion: Optional[IdeaRefinementSuggestion] = Field(
        None, description="LLM refinement suggestion"
    )
    error: Optional[str] = Field(None, description="Error message if operation failed")
