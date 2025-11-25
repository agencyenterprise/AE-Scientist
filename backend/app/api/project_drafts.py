"""
Project Draft API endpoints.

This module contains FastAPI routes for project draft management and AI refinement.
"""

import logging
from typing import List, Optional, Union

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import ProjectDraft, ProjectDraftCreateRequest, ProjectDraftVersion
from app.services import ChunkingService, EmbeddingsService, SearchIndexer, get_database
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/conversations")
logger = logging.getLogger(__name__)
embeddings_service = EmbeddingsService()
chunking_service = ChunkingService()
search_indexer = SearchIndexer(embeddings_service, chunking_service)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class ProjectDraftGetResponse(BaseModel):
    """Get project draft response."""

    project_draft: ProjectDraft = Field(..., description="Retrieved project draft")


class ProjectDraftUpdateResponse(BaseModel):
    """Update project draft response."""

    project_draft: ProjectDraft = Field(..., description="Updated project draft")


class ProjectDraftVersionsResponse(BaseModel):
    """Get project draft versions response."""

    versions: List[ProjectDraftVersion] = Field(..., description="List of project draft versions")


@router.get("/{conversation_id}/project-draft")
async def get_project_draft(
    conversation_id: int, response: Response
) -> Union[ProjectDraftGetResponse, ErrorResponse]:
    """
    Get the project draft for a conversation.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    # Check if conversation exists
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Get project draft
    project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
    if not project_draft_data:
        response.status_code = 404
        return ErrorResponse(
            error="Project draft not found", detail="No project draft found for this conversation"
        )

    # Convert to ProjectDraft model
    active_version = ProjectDraftVersion(
        version_id=project_draft_data.version_id,
        title=project_draft_data.title,
        description=project_draft_data.description,
        is_manual_edit=project_draft_data.is_manual_edit,
        version_number=project_draft_data.version_number,
        created_at=project_draft_data.version_created_at.isoformat(),
    )

    project_draft = ProjectDraft(
        project_draft_id=project_draft_data.project_draft_id,
        conversation_id=project_draft_data.conversation_id,
        active_version=active_version,
        created_at=project_draft_data.created_at.isoformat(),
        updated_at=project_draft_data.updated_at.isoformat(),
    )

    return ProjectDraftGetResponse(project_draft=project_draft)


@router.patch("/{conversation_id}/project-draft")
async def update_project_draft(
    conversation_id: int,
    draft_data: ProjectDraftCreateRequest,
    request: Request,
    response: Response,
) -> Union[ProjectDraftUpdateResponse, ErrorResponse]:
    """
    Manually update a project draft's title and description.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    # Validate title length for Linear compatibility
    if len(draft_data.title) > settings.MAX_PROJECT_TITLE_LENGTH:
        response.status_code = 400
        return ErrorResponse(
            error="Title too long",
            detail=f"Project title cannot exceed {settings.MAX_PROJECT_TITLE_LENGTH} characters for Linear compatibility. Current length: {len(draft_data.title)}",
        )

    db = get_database()

    # Check if conversation exists
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if project draft exists
    project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
    if not project_draft_data:
        response.status_code = 404
        return ErrorResponse(
            error="Project draft not found", detail="No project draft found for this conversation"
        )

    try:
        # Create new version with manual update
        user = get_current_user(request)
        db.create_project_draft_version(
            project_draft_id=project_draft_data.project_draft_id,
            title=draft_data.title,
            description=draft_data.description,
            is_manual_edit=True,
            created_by_user_id=user.id,
        )

        # Get updated project draft
        updated_project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
        if not updated_project_draft_data:
            response.status_code = 500
            return ErrorResponse(
                error="Retrieval failed", detail="Failed to retrieve updated project draft"
            )

        # Convert to ProjectDraft model
        active_version = ProjectDraftVersion(
            version_id=updated_project_draft_data.version_id,
            title=updated_project_draft_data.title,
            description=updated_project_draft_data.description,
            is_manual_edit=updated_project_draft_data.is_manual_edit,
            version_number=updated_project_draft_data.version_number,
            created_at=updated_project_draft_data.version_created_at.isoformat(),
        )

        project_draft = ProjectDraft(
            project_draft_id=updated_project_draft_data.project_draft_id,
            conversation_id=updated_project_draft_data.conversation_id,
            active_version=active_version,
            created_at=updated_project_draft_data.created_at.isoformat(),
            updated_at=updated_project_draft_data.updated_at.isoformat(),
        )

        # Re-index the active project draft
        search_indexer.index_active_project_draft(
            project_draft_id=updated_project_draft_data.project_draft_id
        )

        return ProjectDraftUpdateResponse(project_draft=project_draft)

    except Exception as e:
        logger.exception(f"Error updating project draft: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Update failed", detail=f"Failed to update project draft: {str(e)}"
        )


@router.get("/{conversation_id}/project-draft/versions")
async def get_project_draft_versions(
    conversation_id: int, response: Response
) -> Union[ProjectDraftVersionsResponse, ErrorResponse]:
    """
    Get all versions of a project draft for a conversation.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    # Check if conversation exists
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if project draft exists
    project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
    if not project_draft_data:
        response.status_code = 404
        return ErrorResponse(
            error="Project draft not found", detail="No project draft found for this conversation"
        )

    try:
        # Get all versions
        versions_data = db.get_project_draft_versions(project_draft_data.project_draft_id)

        # Convert to ProjectDraftVersion models
        versions = [
            ProjectDraftVersion(
                version_id=version.version_id,
                title=version.title,
                description=version.description,
                is_manual_edit=version.is_manual_edit,
                version_number=version.version_number,
                created_at=version.created_at.isoformat(),
            )
            for version in versions_data
        ]

        return ProjectDraftVersionsResponse(versions=versions)

    except Exception as e:
        logger.exception(f"Error getting project draft versions: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Versions failed", detail=f"Failed to get project draft versions: {str(e)}"
        )


@router.post("/{conversation_id}/project-draft/versions/{version_id}/activate")
async def activate_project_draft_version(
    conversation_id: int, version_id: int, request: Request, response: Response
) -> Union[ProjectDraftUpdateResponse, ErrorResponse]:
    """
    Recover a previous version by creating a new version with the same content.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    if version_id <= 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid version ID", detail="Version ID must be positive")

    db = get_database()

    # Check if conversation exists
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if project draft exists
    project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
    if not project_draft_data:
        response.status_code = 404
        return ErrorResponse(
            error="Project draft not found", detail="No project draft found for this conversation"
        )

    try:
        # Create a new version by copying the specified version (recovery)
        user = get_current_user(request)
        new_version_id = db.recover_project_draft_version(
            project_draft_data.project_draft_id, version_id, created_by_user_id=user.id
        )

        if not new_version_id:
            response.status_code = 404
            return ErrorResponse(
                error="Recovery failed", detail="Source version not found or recovery failed"
            )

        # Get updated project draft
        updated_project_draft_data = db.get_project_draft_by_conversation_id(conversation_id)
        if not updated_project_draft_data:
            response.status_code = 500
            return ErrorResponse(
                error="Retrieval failed", detail="Failed to retrieve updated project draft"
            )

        # Convert to ProjectDraft model
        active_version = ProjectDraftVersion(
            version_id=updated_project_draft_data.version_id,
            title=updated_project_draft_data.title,
            description=updated_project_draft_data.description,
            is_manual_edit=updated_project_draft_data.is_manual_edit,
            version_number=updated_project_draft_data.version_number,
            created_at=updated_project_draft_data.version_created_at.isoformat(),
        )

        project_draft = ProjectDraft(
            project_draft_id=updated_project_draft_data.project_draft_id,
            conversation_id=updated_project_draft_data.conversation_id,
            active_version=active_version,
            created_at=updated_project_draft_data.created_at.isoformat(),
            updated_at=updated_project_draft_data.updated_at.isoformat(),
        )

        # Re-index after activation
        search_indexer.index_active_project_draft(
            project_draft_id=updated_project_draft_data.project_draft_id
        )

        return ProjectDraftUpdateResponse(project_draft=project_draft)

    except Exception as e:
        logger.exception(f"Error activating project draft version: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Activation failed", detail=f"Failed to activate project draft version: {str(e)}"
        )
