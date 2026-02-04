"""
Paper review API endpoints.

Provides endpoints for submitting papers for review and retrieving results.
Reviews are processed asynchronously in the background.
"""

import logging
from typing import List, Optional, Union

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
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


class PaperReviewStartedResponse(BaseModel):
    """Response when a paper review is started."""

    review_id: int = Field(..., description="Unique review ID")
    status: str = Field(..., description="Review status (pending)")


class PaperReviewSummary(BaseModel):
    """Summary of a paper review for list views."""

    id: int = Field(..., description="Review ID")
    status: str = Field(..., description="Review status")
    summary: Optional[str] = Field(None, description="Paper summary (null if pending)")
    overall: Optional[int] = Field(None, description="Overall score (null if pending)")
    decision: Optional[str] = Field(None, description="Review decision (null if pending)")
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
    status: str = Field(..., description="Review status: pending, processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is failed")
    summary: Optional[str] = Field(None, description="Paper summary (null if not completed)")
    strengths: Optional[List[str]] = Field(
        None, description="List of strengths (null if not completed)"
    )
    weaknesses: Optional[List[str]] = Field(
        None, description="List of weaknesses (null if not completed)"
    )
    originality: Optional[int] = None
    quality: Optional[int] = None
    clarity: Optional[int] = None
    significance: Optional[int] = None
    questions: Optional[List[str]] = None
    limitations: Optional[List[str]] = None
    ethical_concerns: Optional[bool] = None
    soundness: Optional[int] = None
    presentation: Optional[int] = None
    contribution: Optional[int] = None
    overall: Optional[int] = None
    confidence: Optional[int] = None
    decision: Optional[str] = None
    original_filename: str
    model: str
    created_at: str
    token_usage: Optional[TokenUsageResponse] = Field(
        None, description="Token usage (null if not completed)"
    )
    cost_cents: int = Field(0, description="Cost charged in cents for this review")


class PaperDownloadResponse(BaseModel):
    """Response with a temporary download URL for the paper PDF."""

    download_url: str = Field(..., description="Temporary signed URL to download the PDF")
    filename: str = Field(..., description="Original filename of the PDF")


class PendingReviewSummary(BaseModel):
    """Summary of a pending/processing review."""

    id: int = Field(..., description="Review ID")
    status: str = Field(..., description="Review status")
    original_filename: str = Field(..., description="Original PDF filename")
    model: str = Field(..., description="Model used for review")
    created_at: str = Field(..., description="ISO timestamp of review creation")


class PendingReviewsResponse(BaseModel):
    """Response for listing pending reviews."""

    reviews: List[PendingReviewSummary] = Field(..., description="List of pending reviews")
    count: int = Field(..., description="Number of pending reviews")


@router.post("", response_model=None)
async def create_paper_review(
    request: Request,
    response: Response,
    file: UploadFile = File(..., description="PDF file to review"),
    model: str = Form(..., description="LLM model to use for review (provider:model format)"),
    num_reviews_ensemble: int = Form(
        ..., ge=1, le=5, description="Number of ensemble reviews (1-5)"
    ),
    num_reflections: int = Form(..., ge=1, le=3, description="Number of reflection rounds (1-3)"),
) -> Union[PaperReviewStartedResponse, ErrorResponse]:
    """
    Submit a paper for review.

    Upload a PDF file to start an asynchronous review process. The endpoint
    returns immediately with a review ID that can be used to poll for results.

    Requires authentication. Costs will be charged when the review completes.
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

    # Start review (returns immediately)
    try:
        service = get_paper_review_service()
        review_id, status = await service.start_review(
            user_id=current_user.id,
            pdf_content=pdf_content,
            original_filename=file.filename,
            model=model,
            num_reviews_ensemble=num_reviews_ensemble,
            num_reflections=num_reflections,
        )

        response.status_code = 202  # Accepted
        return PaperReviewStartedResponse(
            review_id=review_id,
            status=status,
        )

    except Exception as e:
        logger.exception("Failed to start paper review")
        # Check if it's a payment required error
        status_code = getattr(e, "status_code", None)
        if status_code == 402:
            response.status_code = 402
            return ErrorResponse(
                error="Insufficient balance",
                detail="You don't have enough balance to perform this review",
            )
        response.status_code = 500
        return ErrorResponse(error="Failed to start review", detail=str(e))


@router.get("/pending", response_model=None)
async def get_pending_reviews(
    request: Request,
    response: Response,
) -> Union[PendingReviewsResponse, ErrorResponse]:
    """
    Get all pending or processing reviews for the authenticated user.

    Use this endpoint to check if there are any reviews in progress.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()
        reviews = await service.get_pending_reviews(user_id=current_user.id)

        return PendingReviewsResponse(
            reviews=[PendingReviewSummary(**r) for r in reviews],
            count=len(reviews),
        )

    except Exception as e:
        logger.exception("Failed to get pending reviews")
        response.status_code = 500
        return ErrorResponse(error="Failed to get pending reviews", detail=str(e))


@router.get("", response_model=None)
async def list_paper_reviews(
    request: Request,
    response: Response,
    limit: int = 20,
    offset: int = 0,
) -> Union[PaperReviewListResponse, ErrorResponse]:
    """
    List paper reviews for the authenticated user.

    Returns a paginated list of review summaries including status.
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


@router.get("/{review_id}", response_model=PaperReviewDetailResponse)
async def get_paper_review(
    review_id: int,
    request: Request,
) -> PaperReviewDetailResponse:
    """
    Get a specific paper review by ID.

    Only returns reviews owned by the authenticated user.
    Poll this endpoint to check if a review has completed.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()
        review = await service.get_review(
            review_id=review_id,
            user_id=current_user.id,
        )

        if not review:
            raise HTTPException(
                status_code=404,
                detail="The requested review does not exist or you don't have access to it",
            )

        # Build token usage if available
        token_usage = None
        if review.get("token_usage") and review["token_usage"].get("input_tokens"):
            token_usage = TokenUsageResponse(**review["token_usage"])

        return PaperReviewDetailResponse(
            id=review["id"],
            status=review["status"],
            error_message=review.get("error_message"),
            summary=review.get("summary") or None,
            strengths=review.get("strengths"),
            weaknesses=review.get("weaknesses"),
            originality=review.get("originality"),
            quality=review.get("quality"),
            clarity=review.get("clarity"),
            significance=review.get("significance"),
            questions=review.get("questions"),
            limitations=review.get("limitations"),
            ethical_concerns=review.get("ethical_concerns"),
            soundness=review.get("soundness"),
            presentation=review.get("presentation"),
            contribution=review.get("contribution"),
            overall=review.get("overall"),
            confidence=review.get("confidence"),
            decision=review.get("decision"),
            original_filename=review["original_filename"],
            model=review["model"],
            created_at=review["created_at"],
            token_usage=token_usage,
            cost_cents=review.get("cost_cents", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get paper review")
        raise HTTPException(status_code=500, detail="Failed to get review") from e


@router.get("/{review_id}/download", response_model=None)
async def get_paper_download_url(
    review_id: int,
    request: Request,
    response: Response,
) -> Union[PaperDownloadResponse, ErrorResponse]:
    """
    Get a temporary download URL for the reviewed paper PDF.

    Returns a signed URL that expires after 1 hour. Only returns URLs
    for papers owned by the authenticated user.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()
        result = await service.get_paper_download_url(
            review_id=review_id,
            user_id=current_user.id,
        )

        if not result:
            response.status_code = 404
            return ErrorResponse(
                error="Paper not found",
                detail="The requested paper does not exist or you don't have access to it",
            )

        download_url, filename = result
        return PaperDownloadResponse(
            download_url=download_url,
            filename=filename,
        )

    except Exception as e:
        logger.exception("Failed to get paper download URL")
        response.status_code = 500
        return ErrorResponse(error="Failed to get download URL", detail=str(e))
