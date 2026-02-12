"""
Paper review response models.

These are the Pydantic models used for API responses and service layer returns.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.services.database.paper_reviews import PaperReview


class TokenUsage(BaseModel):
    """Token usage summary for a paper review."""

    input_tokens: int = Field(..., description="Total input tokens used")
    cached_input_tokens: int = Field(..., description="Cached input tokens")
    output_tokens: int = Field(..., description="Total output tokens used")


class PaperReviewDetail(BaseModel):
    """Paper review with computed fields for API responses.

    This is used both as the service return type and the API response model.
    """

    # Always visible fields
    id: int
    status: str = Field(..., description="Review status: pending, processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is failed")
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
    access_restricted_reason: Optional[str] = Field(
        None,
        description="Message explaining why access is restricted",
    )

    # Fields that may be None when access is restricted
    summary: Optional[str] = Field(
        None, description="Paper summary (null if not completed or restricted)"
    )
    strengths: Optional[List[str]] = Field(
        None, description="List of strengths (null if not completed or restricted)"
    )
    weaknesses: Optional[List[str]] = Field(
        None, description="List of weaknesses (null if not completed or restricted)"
    )
    originality: Optional[int] = None
    quality: Optional[int] = None
    clarity: Optional[int] = None
    significance: Optional[int] = None
    questions: Optional[List[str]] = None
    limitations: Optional[List[str]] = None
    ethical_concerns: Optional[bool] = None
    ethical_concerns_explanation: Optional[str] = None
    soundness: Optional[int] = None
    presentation: Optional[int] = None
    contribution: Optional[int] = None
    overall: Optional[int] = None
    confidence: Optional[int] = None
    decision: Optional[str] = None
    token_usage: Optional[TokenUsage] = Field(
        None, description="Token usage (null if not completed or restricted)"
    )
    cost_cents: Optional[int] = Field(
        None, description="Cost charged in cents (null if restricted)"
    )

    # Progress fields (0.0-1.0 for in-progress, 1.0 for completed/failed)
    progress: float = Field(
        ...,
        description="Review progress (0.0-1.0)",
    )
    progress_step: str = Field(
        ...,
        description="Current step description (empty string when completed)",
    )

    @classmethod
    def from_review(
        cls,
        review: PaperReview,
        token_usage: TokenUsage | None,
        cost_cents: int,
    ) -> "PaperReviewDetail":
        """Create a PaperReviewDetail from a PaperReview with computed fields.

        Automatically handles access restriction logic based on has_enough_credits.

        Args:
            review: The PaperReview database record
            token_usage: Token usage summary (if available)
            cost_cents: Cost charged in cents
        """
        access_restricted = review.has_enough_credits is False
        access_restricted_reason = (
            "Your balance is negative. Add credits to view full review details."
            if access_restricted
            else None
        )

        if access_restricted:
            return cls(
                id=review.id,
                status=review.status,
                error_message=review.error_message,
                original_filename=review.original_filename,
                model=review.model,
                created_at=review.created_at.isoformat(),
                has_enough_credits=review.has_enough_credits,
                access_restricted=True,
                access_restricted_reason=access_restricted_reason,
                # Restricted fields explicitly set to None
                summary=None,
                strengths=None,
                weaknesses=None,
                token_usage=None,
                cost_cents=None,
                progress=review.progress,
                progress_step=review.progress_step,
            )

        return cls(
            id=review.id,
            status=review.status,
            error_message=review.error_message,
            original_filename=review.original_filename,
            model=review.model,
            created_at=review.created_at.isoformat(),
            has_enough_credits=review.has_enough_credits,
            access_restricted=False,
            access_restricted_reason=None,
            summary=review.summary,
            strengths=review.strengths,
            weaknesses=review.weaknesses,
            originality=review.originality,
            quality=review.quality,
            clarity=review.clarity,
            significance=review.significance,
            questions=review.questions,
            limitations=review.limitations,
            ethical_concerns=review.ethical_concerns,
            ethical_concerns_explanation=review.ethical_concerns_explanation,
            soundness=review.soundness,
            presentation=review.presentation,
            contribution=review.contribution,
            overall=review.overall,
            confidence=review.confidence,
            decision=review.decision,
            token_usage=token_usage,
            cost_cents=cost_cents,
            progress=review.progress,
            progress_step=review.progress_step,
        )
