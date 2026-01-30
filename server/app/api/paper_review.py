"""
Paper review API endpoints.

Provides endpoints for submitting papers for review and retrieving results.
"""

import logging
from typing import List, Optional, Union

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.services.paper_review_service import get_paper_review_service

router = APIRouter(prefix="/paper-reviews", tags=["paper-reviews"])

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class TokenUsageResponse(BaseModel):
    """Token usage summary."""

    input_tokens: int = Field(..., description="Total input tokens used")
    cached_input_tokens: int = Field(..., description="Cached input tokens")
    output_tokens: int = Field(..., description="Total output tokens used")


class ReviewContent(BaseModel):
    """Full review content."""

    summary: str = Field(..., description="Paper summary")
    strengths: List[str] = Field(..., description="List of paper strengths")
    weaknesses: List[str] = Field(..., description="List of paper weaknesses")
    originality: int
    quality: int
    clarity: int
    significance: int
    questions: List[str] = Field(..., description="Questions for authors")
    limitations: List[str] = Field(..., description="Identified limitations")
    ethical_concerns: bool = Field(..., description="Whether ethical concerns were identified")
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str = Field(..., description="Review decision (Accept/Reject/etc.)")


class PaperReviewResponse(BaseModel):
    """Response for a completed paper review."""

    review_id: int = Field(..., description="Unique review ID")
    review: ReviewContent = Field(..., description="Full review content")
    token_usage: TokenUsageResponse = Field(..., description="Token usage summary")
    credits_charged: int = Field(..., description="Credits charged for this review")


class PaperReviewSummary(BaseModel):
    """Summary of a paper review for list views."""

    id: int = Field(..., description="Review ID")
    summary: str = Field(..., description="Truncated summary")
    overall: int = Field(..., description="Overall score")
    decision: str = Field(..., description="Review decision")
    original_filename: str = Field(..., description="Original PDF filename")
    model: str = Field(..., description="Model used for review")
    created_at: str = Field(..., description="ISO timestamp of review creation")


class PaperReviewListResponse(BaseModel):
    """Response for listing paper reviews."""

    reviews: List[PaperReviewSummary] = Field(..., description="List of review summaries")
    count: int = Field(..., description="Number of reviews returned")


class PaperReviewDetailResponse(BaseModel):
    """Detailed response for a single paper review."""

    id: int
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    originality: int
    quality: int
    clarity: int
    significance: int
    questions: List[str]
    limitations: List[str]
    ethical_concerns: bool
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str
    original_filename: str
    model: str
    created_at: str
    token_usage: TokenUsageResponse


@router.post("", response_model=None)
async def create_paper_review(
    request: Request,
    response: Response,
    file: UploadFile = File(..., description="PDF file to review"),
    model: str = Form(
        default="anthropic/claude-sonnet-4-20250514",
        description="LLM model to use for review",
    ),
    num_reviews_ensemble: int = Form(
        default=3,
        ge=1,
        le=5,
        description="Number of ensemble reviews (1-5)",
    ),
    num_reflections: int = Form(
        default=2,
        ge=1,
        le=3,
        description="Number of reflection rounds (1-3)",
    ),
) -> Union[PaperReviewResponse, ErrorResponse]:
    """
    Submit a paper for review.

    Upload a PDF file and receive a comprehensive academic review including
    scores for originality, quality, clarity, significance, and more.

    Requires authentication. Credits will be charged based on token usage.
    """
    # Get authenticated user
    current_user = get_current_user(request)

    # Validate file is a PDF
    if not file.filename:
        response.status_code = 400
        return ErrorResponse(error="No file provided", detail="Please upload a PDF file")

    if not file.filename.lower().endswith(".pdf"):
        response.status_code = 400
        return ErrorResponse(
            error="Invalid file type",
            detail="Only PDF files are supported",
        )

    # Read file content
    try:
        pdf_content = await file.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file")
        response.status_code = 400
        return ErrorResponse(error="Failed to read file", detail=str(e))

    if not pdf_content:
        response.status_code = 400
        return ErrorResponse(error="Empty file", detail="The uploaded file is empty")

    # Perform review
    try:
        service = get_paper_review_service()
        result = await service.review_paper(
            user_id=current_user.id,
            pdf_content=pdf_content,
            original_filename=file.filename,
            model=model,
            num_reviews_ensemble=num_reviews_ensemble,
            num_reflections=num_reflections,
        )

        return PaperReviewResponse(
            review_id=result["review_id"],
            review=ReviewContent(**result["review"]),
            token_usage=TokenUsageResponse(**result["token_usage"]),
            credits_charged=result["credits_charged"],
        )

    except Exception as e:
        logger.exception("Paper review failed")
        # Check if it's a payment required error
        status_code = getattr(e, "status_code", None)
        if status_code == 402:
            response.status_code = 402
            return ErrorResponse(
                error="Insufficient credits",
                detail="You don't have enough credits to perform this review",
            )
        response.status_code = 500
        return ErrorResponse(error="Review failed", detail=str(e))


@router.get("", response_model=None)
async def list_paper_reviews(
    request: Request,
    response: Response,
    limit: int = 20,
    offset: int = 0,
) -> Union[PaperReviewListResponse, ErrorResponse]:
    """
    List paper reviews for the authenticated user.

    Returns a paginated list of review summaries.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()
        reviews = await service.list_reviews(
            user_id=current_user.id,
            limit=min(limit, 100),  # Cap at 100
            offset=offset,
        )

        return PaperReviewListResponse(
            reviews=[PaperReviewSummary(**r) for r in reviews],
            count=len(reviews),
        )

    except Exception as e:
        logger.exception("Failed to list paper reviews")
        response.status_code = 500
        return ErrorResponse(error="Failed to list reviews", detail=str(e))


@router.get("/{review_id}", response_model=None)
async def get_paper_review(
    review_id: int,
    request: Request,
    response: Response,
) -> Union[PaperReviewDetailResponse, ErrorResponse]:
    """
    Get a specific paper review by ID.

    Only returns reviews owned by the authenticated user.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()
        review = await service.get_review(
            review_id=review_id,
            user_id=current_user.id,
        )

        if not review:
            response.status_code = 404
            return ErrorResponse(
                error="Review not found",
                detail="The requested review does not exist or you don't have access to it",
            )

        return PaperReviewDetailResponse(
            id=review["id"],
            summary=review["summary"],
            strengths=review["strengths"],
            weaknesses=review["weaknesses"],
            originality=review["originality"],
            quality=review["quality"],
            clarity=review["clarity"],
            significance=review["significance"],
            questions=review["questions"],
            limitations=review["limitations"],
            ethical_concerns=review["ethical_concerns"],
            soundness=review["soundness"],
            presentation=review["presentation"],
            contribution=review["contribution"],
            overall=review["overall"],
            confidence=review["confidence"],
            decision=review["decision"],
            original_filename=review["original_filename"],
            model=review["model"],
            created_at=review["created_at"],
            token_usage=TokenUsageResponse(**review["token_usage"]),
        )

    except Exception as e:
        logger.exception("Failed to get paper review")
        response.status_code = 500
        return ErrorResponse(error="Failed to get review", detail=str(e))
