"""
Paper review response models.

Pydantic models used for API responses and service layer returns.
Simplified version for AE Paper Review (no billing/access restriction).
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
    """Paper review with computed fields for API responses."""

    id: int
    status: str = Field(..., description="Review status: pending, processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is failed")
    original_filename: str = Field(..., description="Original PDF filename")
    model: str = Field(..., description="Model used for review")
    created_at: str = Field(..., description="ISO timestamp of review creation")

    # Review content fields
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
    ethical_concerns_explanation: str = ""
    soundness: Optional[int] = None
    presentation: Optional[int] = None
    contribution: Optional[int] = None
    overall: Optional[int] = None
    confidence: Optional[int] = None
    decision: Optional[str] = None
    token_usage: Optional[TokenUsage] = Field(
        None, description="Token usage (null if not completed)"
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
        token_usage: Optional[TokenUsage],
    ) -> "PaperReviewDetail":
        """Create a PaperReviewDetail from a PaperReview with computed fields.

        Args:
            review: The PaperReview database record
            token_usage: Token usage summary (if available)
        """
        return cls(
            id=review.id,
            status=review.status,
            error_message=review.error_message,
            original_filename=review.original_filename,
            model=review.model,
            created_at=review.created_at.isoformat(),
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
            progress=review.progress,
            progress_step=review.progress_step,
        )


class PaperReviewSummary(BaseModel):
    """Summary of a paper review for list views."""

    id: int
    status: str
    summary: Optional[str] = None
    overall: Optional[int] = None
    decision: Optional[str] = None
    original_filename: str
    model: str
    created_at: str
    progress: float
    progress_step: str
