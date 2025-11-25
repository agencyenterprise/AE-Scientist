"""
Project API endpoints.

This module contains FastAPI routes for Linear project creation and management.
"""

import logging
from typing import Optional, Union

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import Project, ProjectCreate
from app.services import LinearService, get_database
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/conversations")

# Initialize Linear service
linear_service = LinearService()
logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class ProjectCreateResponse(BaseModel):
    """Create project response."""

    project: Project = Field(..., description="Created project")


class ProjectGetResponse(BaseModel):
    """Get project response."""

    project: Project = Field(..., description="Retrieved project")


@router.post("/{conversation_id}/project")
async def create_project(
    conversation_id: int, project_data: ProjectCreate, request: Request, response: Response
) -> Union[ProjectCreateResponse, ErrorResponse]:
    """
    Create a new Linear project for a conversation.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    # Validate title length for Linear compatibility
    if len(project_data.title) > settings.MAX_PROJECT_TITLE_LENGTH:
        response.status_code = 400
        return ErrorResponse(
            error="Title too long",
            detail=f"Project title cannot exceed {settings.MAX_PROJECT_TITLE_LENGTH} characters for Linear compatibility. Current length: {len(project_data.title)}",
        )

    db = get_database()

    try:
        # Check if conversation exists
        existing_conversation = db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            response.status_code = 404
            return ErrorResponse(
                error="Conversation not found",
                detail=f"No conversation found with ID {conversation_id}",
            )

        # Check if conversation is already locked
        if db.conversation_is_locked(conversation_id):
            response.status_code = 409
            return ErrorResponse(
                error="Conversation locked",
                detail="Conversation is locked - project already exists",
            )

        # Check if project already exists
        existing_project = db.get_project_by_conversation_id(conversation_id)
        if existing_project:
            response.status_code = 409
            return ErrorResponse(
                error="Project exists", detail="Project already exists for this conversation"
            )

        logger.info(f"Creating Linear project for conversation {conversation_id}")
        logger.debug(f"  - Title: {project_data.title}")
        logger.debug(f"  - Description: {project_data.description[:100]}...")

        # Create project in Linear
        linear_project = await linear_service.create_project(
            title=project_data.title, description=project_data.description
        )

        # Save project to database (this also locks the conversation)
        user = get_current_user(request)
        project_id = db.create_project(
            conversation_id=conversation_id,
            linear_project_id=linear_project.id,
            title=linear_project.name,
            description=linear_project.content,  # Store Linear's response as our description
            linear_url=linear_project.url,
            created_by_user_id=user.id,
        )

        logger.info("Project created successfully")
        logger.info(f"  - Database ID: {project_id}")
        logger.info(f"  - Linear ID: {linear_project.id}")
        logger.info(f"  - Linear URL: {linear_project.url}")
        logger.info("  - Conversation locked: True")

        # Get the complete project data
        project_data_result = db.get_project_by_conversation_id(conversation_id)
        if not project_data_result:
            response.status_code = 500
            return ErrorResponse(
                error="Failed to retrieve project", detail="Failed to retrieve created project"
            )

        # Convert to Project model
        project = Project(
            id=project_data_result.id,
            conversation_id=project_data_result.conversation_id,
            linear_project_id=project_data_result.linear_project_id,
            title=project_data_result.title,
            description=project_data_result.description,
            linear_url=project_data_result.linear_url,
            created_at=project_data_result.created_at.isoformat(),
        )

        return ProjectCreateResponse(project=project)

    except Exception as e:
        logger.exception(f"Error creating project: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Project creation failed", detail=f"Failed to create project: {str(e)}"
        )


@router.get("/{conversation_id}/project")
async def get_project(
    conversation_id: int, response: Response
) -> Union[ProjectGetResponse, ErrorResponse]:
    """
    Get the Linear project for a conversation.
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
            return ErrorResponse(
                error="Conversation not found",
                detail=f"No conversation found with ID {conversation_id}",
            )

        # Get project
        project_data_result = db.get_project_by_conversation_id(conversation_id)
        if not project_data_result:
            response.status_code = 404
            return ErrorResponse(
                error="Project not found", detail="No project found for this conversation"
            )

        # Convert to Project model
        project = Project(
            id=project_data_result.id,
            conversation_id=project_data_result.conversation_id,
            linear_project_id=project_data_result.linear_project_id,
            title=project_data_result.title,
            description=project_data_result.description,
            linear_url=project_data_result.linear_url,
            created_at=project_data_result.created_at.isoformat(),
        )

        return ProjectGetResponse(project=project)

    except Exception as e:
        logger.exception(f"Error getting project: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Failed to get project", detail=f"Failed to get project: {str(e)}"
        )
