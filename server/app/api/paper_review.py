"""
Paper review API endpoints.

Provides endpoints for submitting papers for review and retrieving results.
Reviews are processed asynchronously in the background.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.models.billing import InsufficientBalanceError
from app.models.paper_review import PaperReviewDetail
from app.services.paper_review_service import get_paper_review_service

router = APIRouter(prefix="/paper-reviews", tags=["paper-reviews"])

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class PaperReviewStartedResponse(BaseModel):
    """Response when a paper review is started."""

    review_id: int = Field(..., description="Unique review ID")
    status: str = Field(..., description="Review status (pending)")


class PaperReviewSummary(BaseModel):
    """Summary of a paper review for list views."""

    id: int = Field(..., description="Review ID")
    status: str = Field(..., description="Review status")
    summary: Optional[str] = Field(
        None, description="Paper summary (null if pending or restricted)"
    )
    overall: Optional[int] = Field(
        None, description="Overall score (null if pending or restricted)"
    )
    decision: Optional[str] = Field(
        None, description="Review decision (null if pending or restricted)"
    )
    original_filename: str = Field(..., description="Original PDF filename")
    model: str = Field(..., description="Model used for review")
    created_at: str = Field(..., description="ISO timestamp of review creation")
    has_enough_credits: Optional[bool] = Field(
        None,
        description="Whether user had positive balance when review completed. NULL if still running.",
    )
    access_restricted: bool = Field(
        False,
        description="True if user cannot view full review details due to insufficient credits",
    )
    progress: float = Field(..., description="Review progress (0.0-1.0)")
    progress_step: str = Field(
        ..., description="Current step description (empty string when completed)"
    )


class PaperReviewListResponse(BaseModel):
    """Response for listing paper reviews."""

    reviews: List[PaperReviewSummary] = Field(..., description="List of review summaries")
    count: int = Field(..., description="Number of reviews returned")


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


@router.post(
    "",
    response_model=PaperReviewStartedResponse,
    status_code=202,
    responses={
        402: {
            "model": InsufficientBalanceError,
            "description": "Insufficient balance to start paper review",
        },
    },
)
async def create_paper_review(
    request: Request,
    file: UploadFile = File(..., description="PDF file to review"),
    model: str = Form(..., description="LLM model to use for review (provider:model format)"),
    num_reviews_ensemble: int = Form(
        ..., ge=1, le=5, description="Number of ensemble reviews (1-5)"
    ),
    num_reflections: int = Form(..., ge=1, le=3, description="Number of reflection rounds (1-3)"),
) -> PaperReviewStartedResponse:
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
        raise HTTPException(status_code=400, detail="No file provided. Please upload a PDF file.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF files are supported."
        )

    # Read file content
    try:
        pdf_content = await file.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e

    if not pdf_content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

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

        return PaperReviewStartedResponse(
            review_id=review_id,
            status=status,
        )

    except HTTPException:
        # Let HTTPException (including 402 from enforce_minimum_balance) propagate
        raise
    except Exception as e:
        logger.exception("Failed to start paper review")
        raise HTTPException(status_code=500, detail="Failed to start review") from e


@router.get("/pending", response_model=PendingReviewsResponse)
async def get_pending_reviews(
    request: Request,
) -> PendingReviewsResponse:
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
        raise HTTPException(status_code=500, detail="Failed to get pending reviews") from e


@router.get("", response_model=PaperReviewListResponse)
async def list_paper_reviews(
    request: Request,
    limit: int = 20,
    offset: int = 0,
) -> PaperReviewListResponse:
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
        raise HTTPException(status_code=500, detail="Failed to list reviews") from e


@router.get("/{review_id}", response_model=PaperReviewDetail)
async def get_paper_review(
    review_id: int,
    request: Request,
) -> PaperReviewDetail:
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

        return review

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get paper review")
        raise HTTPException(status_code=500, detail="Failed to get review") from e


@router.get("/{review_id}/download", response_model=PaperDownloadResponse)
async def get_paper_download_url(
    review_id: int,
    request: Request,
) -> PaperDownloadResponse:
    """
    Get a temporary download URL for the reviewed paper PDF.

    Returns a signed URL that expires after 1 hour. Only returns URLs
    for papers owned by the authenticated user.

    Returns 402 Payment Required if the user's balance was negative when
    the review completed.
    """
    current_user = get_current_user(request)

    try:
        service = get_paper_review_service()

        # First check if the review exists and if access is restricted
        review = await service.get_review(
            review_id=review_id,
            user_id=current_user.id,
        )

        if not review:
            raise HTTPException(
                status_code=404,
                detail="The requested paper does not exist or you don't have access to it",
            )

        if review.access_restricted:
            raise HTTPException(
                status_code=402,
                detail="Insufficient credits. Add funds to download this paper.",
            )

        result = await service.get_paper_download_url(
            review_id=review_id,
            user_id=current_user.id,
            check_credits=False,  # Already checked above
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="The requested paper does not exist or you don't have access to it",
            )

        download_url, filename = result
        return PaperDownloadResponse(
            download_url=download_url,
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get paper download URL")
        raise HTTPException(status_code=500, detail="Failed to get download URL") from e
