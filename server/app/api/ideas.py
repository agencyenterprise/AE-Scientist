"""
Idea API endpoints.

This module contains FastAPI routes for idea management and AI refinement.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.models import Idea, IdeaRefinementRequest, IdeaVersion
from app.services import get_database

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


class IdeaJudgeReviewResponse(BaseModel):
    """Response for an idea judge review."""

    id: int
    idea_id: int
    idea_version_id: Optional[int] = None
    relevance: Dict[str, Any]
    feasibility: Dict[str, Any]
    novelty: Dict[str, Any]
    impact: Dict[str, Any]
    revision: Optional[Dict[str, Any]] = None
    overall_score: float
    recommendation: str
    summary: str
    llm_model: Optional[str] = None
    created_at: str


class IdeaJudgeReviewsResponse(BaseModel):
    """Response containing all judge reviews for an idea."""

    reviews: List[IdeaJudgeReviewResponse]


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
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Get idea
    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    # Convert to Idea model
    active_version = IdeaVersion(
        version_id=idea_data.version_id,
        title=idea_data.title,
        idea_markdown=idea_data.idea_markdown,
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
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if idea exists
    existing_idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not existing_idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Create new version with manual update
        user = get_current_user(request)
        await db.create_idea_version(
            idea_id=existing_idea_data.idea_id,
            title=idea_data.title,
            idea_markdown=idea_data.idea_markdown,
            is_manual_edit=True,
            created_by_user_id=user.id,
        )

        # Get updated idea
        updated_idea_data = await db.get_idea_by_conversation_id(conversation_id)
        if not updated_idea_data:
            response.status_code = 500
            return ErrorResponse(error="Retrieval failed", detail="Failed to retrieve updated idea")

        # Convert to Idea model
        active_version = IdeaVersion(
            version_id=updated_idea_data.version_id,
            title=updated_idea_data.title,
            idea_markdown=updated_idea_data.idea_markdown,
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
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if idea exists
    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Get all versions
        versions_data = await db.get_idea_versions(idea_data.idea_id)

        # Convert to IdeaVersion models
        versions = [
            IdeaVersion(
                version_id=version.version_id,
                title=version.title,
                idea_markdown=version.idea_markdown,
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
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Check if idea exists
    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        # Create a new version by copying the specified version (recovery)
        user = get_current_user(request)
        new_version_id = await db.recover_idea_version(
            idea_data.idea_id, version_id, created_by_user_id=user.id
        )

        if not new_version_id:
            response.status_code = 404
            return ErrorResponse(
                error="Recovery failed", detail="Source version not found or recovery failed"
            )

        # Get updated idea
        updated_idea_data = await db.get_idea_by_conversation_id(conversation_id)
        if not updated_idea_data:
            response.status_code = 500
            return ErrorResponse(error="Retrieval failed", detail="Failed to retrieve updated idea")

        # Convert to Idea model
        active_version = IdeaVersion(
            version_id=updated_idea_data.version_id,
            title=updated_idea_data.title,
            idea_markdown=updated_idea_data.idea_markdown,
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


@router.get("/{conversation_id}/idea/judge-reviews")
async def get_idea_judge_reviews(
    conversation_id: int, response: Response
) -> Union[IdeaJudgeReviewsResponse, ErrorResponse]:
    """
    Get all judge reviews for a conversation's idea (newest first).
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    try:
        reviews_data = await db.get_idea_judge_reviews_by_idea_id(idea_data.idea_id)
        reviews = [
            IdeaJudgeReviewResponse(
                id=r.id,
                idea_id=r.idea_id,
                idea_version_id=r.idea_version_id,
                relevance=r.relevance,
                feasibility=r.feasibility,
                novelty=r.novelty,
                impact=r.impact,
                revision=r.revision,
                overall_score=r.overall_score,
                recommendation=r.recommendation,
                summary=r.summary,
                llm_model=r.llm_model,
                created_at=r.created_at.isoformat(),
            )
            for r in reviews_data
        ]
        return IdeaJudgeReviewsResponse(reviews=reviews)

    except Exception as e:
        logger.exception(f"Error getting judge reviews: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Reviews failed", detail=f"Failed to get judge reviews: {str(e)}"
        )


class JudgeRunResponse(BaseModel):
    """Response when a judge re-run is accepted."""

    status: str = Field(..., description="Status message")


def _format_prior_reviews(reviews: list) -> str:
    """Build a formatted string of prior judge reviews for prompt context.

    Reviews should be ordered newest-first (as returned from DB).
    We reverse to show them chronologically (oldest first).
    """
    if not reviews:
        return ""
    chronological = list(reversed(reviews))
    parts: list[str] = []
    for i, r in enumerate(chronological, 1):
        rel = r.relevance.get("score", "?") if isinstance(r.relevance, dict) else "?"
        feas = r.feasibility.get("score", "?") if isinstance(r.feasibility, dict) else "?"
        nov = r.novelty.get("score", "?") if isinstance(r.novelty, dict) else "?"
        imp = r.impact.get("score", "?") if isinstance(r.impact, dict) else "?"
        rev_assessment = ""
        if r.revision and isinstance(r.revision, dict):
            rev_assessment = r.revision.get("overall_assessment", "")
        parts.append(
            f"### Round {i} — Overall {r.overall_score:.1f}/5 ({r.recommendation})\n"
            f"Relevance {rel}/5 · Feasibility {feas}/5 · Novelty {nov}/5 · Impact {imp}/5\n"
            f"Summary: {r.summary}\n"
            + (f"Assessment: {rev_assessment}\n" if rev_assessment else "")
        )
    return "\n".join(parts)


def _format_refinement_history(
    original_version: Optional[Any],
    reviews: list,
) -> str:
    """Build full refinement history for the refiner prompt."""
    if not reviews:
        return ""
    parts: list[str] = []
    if original_version:
        parts.append(
            f"### Original Idea (v1)\n"
            f"**Title:** {original_version.title}\n\n"
            f"{original_version.idea_markdown}\n"
        )
    parts.append("### Judge Review History (chronological)\n")
    parts.append(_format_prior_reviews(reviews))
    return "\n---\n".join(parts)


async def _run_judge_background(conversation_id: int) -> None:
    """Background task: run the idea judge and persist the result."""
    from app.services.idea_judge_service import IdeaJudgeService, JUDGE_DEFAULT_MODEL
    from app.services.openai_service import OpenAIService

    db = get_database()
    try:
        idea = await db.get_idea_by_conversation_id(conversation_id)
        if not idea:
            logger.warning("judge re-run: no idea for conversation %d", conversation_id)
            return

        summary_row = await db.get_imported_conversation_summary_by_conversation_id(
            conversation_id
        )
        conversation_text = summary_row.summary if summary_row else ""

        prior_reviews_data = await db.get_idea_judge_reviews_by_idea_id(idea.idea_id)
        prior_reviews = _format_prior_reviews(prior_reviews_data) if prior_reviews_data else None

        judge = IdeaJudgeService(llm_service=OpenAIService())
        result = await judge.judge(
            llm_model=JUDGE_DEFAULT_MODEL,
            idea_title=idea.title,
            idea_markdown=idea.idea_markdown,
            conversation_text=conversation_text,
            prior_reviews=prior_reviews,
        )

        await db.create_idea_judge_review(
            idea_id=idea.idea_id,
            idea_version_id=idea.version_id,
            relevance=result.relevance.model_dump(),
            feasibility=result.feasibility.model_dump(),
            novelty=result.novelty.model_dump(),
            impact=result.impact.model_dump(),
            revision=result.revision.model_dump(),
            overall_score=result.overall_score,
            recommendation=result.recommendation,
            summary=result.summary,
            llm_model=JUDGE_DEFAULT_MODEL,
        )
        logger.info(
            "judge re-run: conversation=%d idea=%d overall=%.2f recommendation=%s",
            conversation_id,
            idea.idea_id,
            result.overall_score,
            result.recommendation,
        )
    except Exception:
        logger.exception("judge re-run failed for conversation %d", conversation_id)


@router.post("/{conversation_id}/idea/judge-reviews/run")
async def run_idea_judge(
    conversation_id: int, response: Response
) -> Union[JudgeRunResponse, ErrorResponse]:
    """
    Trigger a fresh idea judge evaluation (runs in background).
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    asyncio.create_task(_run_judge_background(conversation_id))
    return JudgeRunResponse(status="Judge review started")


async def _run_refine_background(conversation_id: int, user_id: int) -> None:
    """Background task: refine the idea using the latest judge review, save as new version."""
    from app.services.idea_judge_service import (
        IdeaJudgeResult,
        RelevanceCriterionResult,
        FeasibilityCriterionResult,
        NoveltyCriterionResult,
        ImpactCriterionResult,
        RevisionPlan,
    )
    from app.services.idea_refiner_service import IdeaRefinerService, REFINER_DEFAULT_MODEL
    from app.services.openai_service import OpenAIService

    db = get_database()
    try:
        idea = await db.get_idea_by_conversation_id(conversation_id)
        if not idea:
            logger.warning("refine: no idea for conversation %d", conversation_id)
            return

        review = await db.get_idea_judge_review_by_idea_id(idea.idea_id)
        if not review:
            logger.warning("refine: no judge review for idea %d", idea.idea_id)
            return

        judge_result = IdeaJudgeResult(
            relevance=RelevanceCriterionResult(**review.relevance),
            feasibility=FeasibilityCriterionResult(**review.feasibility),
            novelty=NoveltyCriterionResult(**review.novelty),
            impact=ImpactCriterionResult(**review.impact),
            revision=RevisionPlan(**review.revision) if review.revision else RevisionPlan(
                action_items=[], overall_assessment="No revision plan available."
            ),
        )

        summary_row = await db.get_imported_conversation_summary_by_conversation_id(
            conversation_id
        )
        conversation_text = summary_row.summary if summary_row else ""

        all_reviews = await db.get_idea_judge_reviews_by_idea_id(idea.idea_id)
        all_versions = await db.get_idea_versions(idea.idea_id)
        original_version = all_versions[-1] if all_versions else None
        refinement_history = _format_refinement_history(original_version, all_reviews)

        refiner = IdeaRefinerService(llm_service=OpenAIService())
        result = await refiner.refine(
            llm_model=REFINER_DEFAULT_MODEL,
            idea_title=idea.title,
            idea_markdown=idea.idea_markdown,
            judge_result=judge_result,
            conversation_text=conversation_text,
            refinement_history=refinement_history or None,
        )

        await db.create_idea_version(
            idea_id=idea.idea_id,
            title=result.refined_title,
            idea_markdown=result.refined_markdown,
            is_manual_edit=False,
            created_by_user_id=user_id,
        )

        logger.info(
            "refine: conversation=%d idea=%d changes=%d summary=%s",
            conversation_id,
            idea.idea_id,
            len(result.changes_made),
            result.refinement_summary[:120],
        )

        asyncio.create_task(_run_judge_background(conversation_id))
    except Exception:
        logger.exception("refine failed for conversation %d", conversation_id)


@router.post("/{conversation_id}/idea/refine")
async def refine_idea(
    conversation_id: int, request: Request, response: Response
) -> Union[JudgeRunResponse, ErrorResponse]:
    """
    Trigger idea refinement based on the latest judge review (runs in background).
    Creates a new idea version with improvements addressing judge concerns.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    if not idea_data:
        response.status_code = 404
        return ErrorResponse(error="Idea not found", detail="No idea found for this conversation")

    review = await db.get_idea_judge_review_by_idea_id(idea_data.idea_id)
    if not review:
        response.status_code = 404
        return ErrorResponse(
            error="No judge review",
            detail="Run the judge first before refining",
        )

    user = get_current_user(request)
    asyncio.create_task(_run_refine_background(conversation_id, user.id))
    return JudgeRunResponse(status="Refinement started")
