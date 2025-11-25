"""
Idea API endpoints.

This module contains FastAPI routes for idea management and AI refinement.
"""

import logging
from typing import List, Optional, Union

from app.middleware.auth import get_current_user
from app.models import Idea, IdeaRefinementRequest, IdeaVersion
from app.services import get_database
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/conversations")
logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class IdeaGetResponse(BaseModel):
    """Get idea response."""

    idea: Idea = Field(..., description="Retrieved idea")


class IdeaUpdateResponse(BaseModel):
    """Update idea response."""

    idea: Idea = Field(..., description="Updated idea")


class IdeaVersionsResponse(BaseModel):
    """Get idea versions response."""

    versions: List[IdeaVersion] = Field(..., description="List of idea versions")


@router.get("/{conversation_id}/idea")
async def get_idea(
    conversation_id: int, response: Response
) -> Union[IdeaGetResponse, ErrorResponse]:
    """
    Get the idea for a conversation.
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

    # Get idea
    idea_data = db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    # Convert to Idea model
    active_version = IdeaVersion(
        version_id=idea_data.version_id,
        title=idea_data.title,
        short_hypothesis=idea_data.short_hypothesis,
        related_work=idea_data.related_work,
        abstract=idea_data.abstract,
        experiments=idea_data.experiments,
        expected_outcome=idea_data.expected_outcome,
        risk_factors_and_limitations=idea_data.risk_factors_and_limitations,
        is_manual_edit=idea_data.is_manual_edit,
        version_number=idea_data.version_number,
        created_at=idea_data.version_created_at.isoformat(),
    )

    idea = Idea(
        idea_id=idea_data.idea_id,
        conversation_id=idea_data.conversation_id,
        active_version=active_version,
        created_at=idea_data.created_at.isoformat(),
        updated_at=idea_data.updated_at.isoformat(),
    )

    return IdeaGetResponse(idea=idea)


@router.patch("/{conversation_id}/idea")
async def update_idea(
    conversation_id: int,
    idea_data: IdeaRefinementRequest,
    request: Request,
    response: Response,
) -> Union[IdeaUpdateResponse, ErrorResponse]:
    """
    Manually update an idea with all fields.
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

    # Check if idea exists
    existing_idea_data = db.get_idea_by_conversation_id(conversation_id)
    if not existing_idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Create new version with manual update
        user = get_current_user(request)
        db.create_idea_version(
            idea_id=existing_idea_data.idea_id,
            title=idea_data.title,
            short_hypothesis=idea_data.short_hypothesis,
            related_work=idea_data.related_work,
            abstract=idea_data.abstract,
            experiments=idea_data.experiments,
            expected_outcome=idea_data.expected_outcome,
            risk_factors_and_limitations=idea_data.risk_factors_and_limitations,
            is_manual_edit=True,
            created_by_user_id=user.id,
        )

        # Get updated idea
        updated_idea_data = db.get_idea_by_conversation_id(conversation_id)
        if not updated_idea_data:
            response.status_code = 500
            return ErrorResponse(error="Retrieval failed", detail="Failed to retrieve updated idea")

        # Convert to Idea model
        active_version = IdeaVersion(
            version_id=updated_idea_data.version_id,
            title=updated_idea_data.title,
            short_hypothesis=updated_idea_data.short_hypothesis,
            related_work=updated_idea_data.related_work,
            abstract=updated_idea_data.abstract,
            experiments=updated_idea_data.experiments,
            expected_outcome=updated_idea_data.expected_outcome,
            risk_factors_and_limitations=updated_idea_data.risk_factors_and_limitations,
            is_manual_edit=updated_idea_data.is_manual_edit,
            version_number=updated_idea_data.version_number,
            created_at=updated_idea_data.version_created_at.isoformat(),
        )

        idea = Idea(
            idea_id=updated_idea_data.idea_id,
            conversation_id=updated_idea_data.conversation_id,
            active_version=active_version,
            created_at=updated_idea_data.created_at.isoformat(),
            updated_at=updated_idea_data.updated_at.isoformat(),
        )

        return IdeaUpdateResponse(idea=idea)

    except Exception as e:
        logger.exception(f"Error updating idea: {e}")
        response.status_code = 500
        return ErrorResponse(error="Update failed", detail=f"Failed to update idea: {str(e)}")


@router.get("/{conversation_id}/idea/versions")
async def get_idea_versions(
    conversation_id: int, response: Response
) -> Union[IdeaVersionsResponse, ErrorResponse]:
    """
    Get all versions of an idea for a conversation.
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

    # Check if idea exists
    idea_data = db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Get all versions
        versions_data = db.get_idea_versions(idea_data.idea_id)

        # Convert to IdeaVersion models
        versions = [
            IdeaVersion(
                version_id=version.version_id,
                title=version.title,
                short_hypothesis=version.short_hypothesis,
                related_work=version.related_work,
                abstract=version.abstract,
                experiments=version.experiments,
                expected_outcome=version.expected_outcome,
                risk_factors_and_limitations=version.risk_factors_and_limitations,
                is_manual_edit=version.is_manual_edit,
                version_number=version.version_number,
                created_at=version.created_at.isoformat(),
            )
            for version in versions_data
        ]

        return IdeaVersionsResponse(versions=versions)

    except Exception as e:
        logger.exception(f"Error getting idea versions: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Versions failed", detail=f"Failed to get idea versions: {str(e)}"
        )


@router.post("/{conversation_id}/idea/versions/{version_id}/activate")
async def activate_idea_version(
    conversation_id: int, version_id: int, request: Request, response: Response
) -> Union[IdeaUpdateResponse, ErrorResponse]:
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

    # Check if idea exists
    idea_data = db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Create a new version by copying the specified version (recovery)
        user = get_current_user(request)
        new_version_id = db.recover_idea_version(
            idea_data.idea_id, version_id, created_by_user_id=user.id
        )

        if not new_version_id:
            response.status_code = 404
            return ErrorResponse(
                error="Recovery failed", detail="Source version not found or recovery failed"
            )

        # Get updated idea
        updated_idea_data = db.get_idea_by_conversation_id(conversation_id)
        if not updated_idea_data:
            response.status_code = 500
            return ErrorResponse(error="Retrieval failed", detail="Failed to retrieve updated idea")

        # Convert to Idea model
        active_version = IdeaVersion(
            version_id=updated_idea_data.version_id,
            title=updated_idea_data.title,
            short_hypothesis=updated_idea_data.short_hypothesis,
            related_work=updated_idea_data.related_work,
            abstract=updated_idea_data.abstract,
            experiments=updated_idea_data.experiments,
            expected_outcome=updated_idea_data.expected_outcome,
            risk_factors_and_limitations=updated_idea_data.risk_factors_and_limitations,
            is_manual_edit=updated_idea_data.is_manual_edit,
            version_number=updated_idea_data.version_number,
            created_at=updated_idea_data.version_created_at.isoformat(),
        )

        idea = Idea(
            idea_id=updated_idea_data.idea_id,
            conversation_id=updated_idea_data.conversation_id,
            active_version=active_version,
            created_at=updated_idea_data.created_at.isoformat(),
            updated_at=updated_idea_data.updated_at.isoformat(),
        )

        return IdeaUpdateResponse(idea=idea)

    except Exception as e:
        logger.exception(f"Error activating idea version: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Activation failed", detail=f"Failed to activate idea version: {str(e)}"
        )
