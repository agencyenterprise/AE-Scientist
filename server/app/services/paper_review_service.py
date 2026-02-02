"""
Paper review service for standalone PDF reviews.

This service orchestrates paper review using the ae-paper-review package,
handling token tracking, database persistence, and credit charging.

Reviews are processed asynchronously in the background to avoid blocking
the main event loop.
"""

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ae_paper_review import ReviewResult, load_paper, perform_review

from app.services.billing_guard import charge_user_credits, enforce_minimum_credits
from app.services.database import PaperReviewStatus, get_database
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)


# Minimum credits required to start a paper review
MINIMUM_CREDITS_FOR_REVIEW = 100

# Cost per 1M input tokens (in credits)
INPUT_TOKEN_COST_PER_MILLION = 30

# Cost per 1M output tokens (in credits)
OUTPUT_TOKEN_COST_PER_MILLION = 150


def calculate_review_cost(input_tokens: int, output_tokens: int) -> int:
    """Calculate the credit cost for a review based on token usage.

    Args:
        input_tokens: Total input tokens used
        output_tokens: Total output tokens used

    Returns:
        Credit cost (rounded up to nearest integer)
    """
    input_cost = (input_tokens / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
    total_cost = input_cost + output_cost
    return max(1, int(total_cost + 0.5))  # Round to nearest, minimum 1 credit


def _run_review_sync(
    paper_text: str,
    model: str,
    num_reviews_ensemble: int,
    num_reflections: int,
) -> ReviewResult:
    """Run the paper review synchronously (called in thread pool).

    This function is designed to be called via asyncio.to_thread() to avoid
    blocking the main event loop.

    Args:
        paper_text: The extracted text from the paper PDF
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        num_reviews_ensemble: Number of ensemble reviews
        num_reflections: Number of reflection rounds
    """
    return perform_review(
        text=paper_text,
        model=model,
        temperature=1,
        num_reviews_ensemble=num_reviews_ensemble,
        num_reflections=num_reflections,
    )


class PaperReviewService:
    """Service for performing standalone paper reviews."""

    def __init__(self) -> None:
        self._s3_service = S3Service()

    def _upload_paper_pdf(
        self,
        *,
        user_id: int,
        pdf_content: bytes,
        original_filename: str,
    ) -> str:
        """Upload a paper PDF to S3 for storage.

        Args:
            user_id: ID of the user
            pdf_content: Raw PDF file content
            original_filename: Original filename

        Returns:
            S3 key for the uploaded file
        """
        # Generate unique S3 key for paper reviews
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = quote(original_filename, safe="")
        s3_key = f"paper-reviews/{user_id}/{unique_id}/{safe_filename}"

        # Upload to S3
        self._s3_service.s3_client.put_object(
            Bucket=self._s3_service.bucket_name,
            Key=s3_key,
            Body=pdf_content,
            ContentType="application/pdf",
            Metadata={
                "original_filename": original_filename[:255],  # S3 metadata limit
                "user_id": str(user_id),
            },
        )

        logger.debug("Uploaded paper PDF to S3: %s", s3_key)
        return s3_key

    async def _process_review_background(
        self,
        *,
        review_id: int,
        user_id: int,
        pdf_content: bytes,
        original_filename: str,
        model: str,
        num_reviews_ensemble: int,
        num_reflections: int,
    ) -> None:
        """Process a paper review in the background.

        This method runs the blocking LLM call in a thread pool and updates
        the database with the results.
        """
        db = get_database()
        tmp_path: Path | None = None

        try:
            # Update status to processing
            await db.update_paper_review_status(review_id, PaperReviewStatus.PROCESSING)

            # Save PDF to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_path = Path(tmp_file.name)

            # Load paper text from PDF (relatively fast, ok to do here)
            paper_text = load_paper(str(tmp_path))

            # Run the LLM review in a thread pool to avoid blocking
            result = await asyncio.to_thread(
                _run_review_sync,
                paper_text,
                model,
                num_reviews_ensemble,
                num_reflections,
            )

            # Get token usage from result
            token_usages = result.token_usage_detailed
            total_usage = result.token_usage

            # Calculate cost
            cost = calculate_review_cost(
                input_tokens=total_usage["input_tokens"],
                output_tokens=total_usage["output_tokens"],
            )

            # Store the review results
            review = result.review
            await db.complete_paper_review(
                review_id=review_id,
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
                soundness=review.soundness,
                presentation=review.presentation,
                contribution=review.contribution,
                overall=review.overall,
                confidence=review.confidence,
                decision=review.decision,
            )

            # Store token usages
            if token_usages:
                await db.insert_paper_review_token_usages_batch(
                    paper_review_id=review_id,
                    usages=token_usages,
                )

            # Charge user credits
            await charge_user_credits(
                user_id=user_id,
                cost=cost,
                action="paper_review",
                description=f"Paper review: {original_filename}",
                metadata={
                    "paper_review_id": review_id,
                    "model": model,
                    "input_tokens": total_usage["input_tokens"],
                    "output_tokens": total_usage["output_tokens"],
                },
            )

            logger.info(
                "Paper review completed: review_id=%d, user_id=%d, cost=%d credits",
                review_id,
                user_id,
                cost,
            )

        except Exception as e:
            # Mark review as failed
            error_message = str(e)
            logger.exception(
                "Paper review failed: review_id=%d, error=%s", review_id, error_message
            )
            await db.update_paper_review_status(
                review_id,
                PaperReviewStatus.FAILED,
                error_message=error_message[:1000],  # Limit error message length
            )

        finally:
            # Clean up temporary file
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    async def start_review(
        self,
        *,
        user_id: int,
        pdf_content: bytes,
        original_filename: str,
        model: str,
        num_reviews_ensemble: int,
        num_reflections: int,
    ) -> dict[str, Any]:
        """Start a paper review asynchronously.

        Creates a pending review record, uploads the PDF, and starts
        background processing. Returns immediately with the review ID.

        Args:
            user_id: ID of the user requesting the review
            pdf_content: Raw PDF file content
            original_filename: Original filename of the uploaded PDF
            model: LLM model to use for review
            num_reviews_ensemble: Number of ensemble reviews
            num_reflections: Number of reflection rounds

        Returns:
            Dict containing review_id and status

        Raises:
            HTTPException: If user has insufficient credits
        """
        db = get_database()

        # Check user has minimum credits
        await enforce_minimum_credits(
            user_id=user_id,
            required=MINIMUM_CREDITS_FOR_REVIEW,
            action="paper_review",
        )

        # Upload PDF to S3 first
        s3_key = self._upload_paper_pdf(
            user_id=user_id,
            pdf_content=pdf_content,
            original_filename=original_filename,
        )

        # Create pending review record
        review_id = await db.create_pending_paper_review(
            user_id=user_id,
            original_filename=original_filename,
            s3_key=s3_key,
            model=model,
        )

        logger.info(
            "Paper review started: review_id=%d, user_id=%d, model=%s",
            review_id,
            user_id,
            model,
        )

        # Start background processing (fire and forget)
        asyncio.create_task(
            self._process_review_background(
                review_id=review_id,
                user_id=user_id,
                pdf_content=pdf_content,
                original_filename=original_filename,
                model=model,
                num_reviews_ensemble=num_reviews_ensemble,
                num_reflections=num_reflections,
            )
        )

        return {
            "review_id": review_id,
            "status": PaperReviewStatus.PENDING.value,
        }

    async def get_review(self, *, review_id: int, user_id: int) -> dict[str, Any] | None:
        """Get a paper review by ID.

        Args:
            review_id: ID of the review
            user_id: ID of the user (for authorization)

        Returns:
            Review dict if found and owned by user, None otherwise
        """
        db = get_database()
        review = await db.get_paper_review_by_id(review_id)

        if not review or review.user_id != user_id:
            return None

        token_usage = await db.get_total_token_usage_by_review_id(review_id)

        # Calculate credits charged from token usage
        credits_charged = 0
        if token_usage.get("input_tokens") and token_usage.get("output_tokens"):
            credits_charged = calculate_review_cost(
                input_tokens=token_usage["input_tokens"],
                output_tokens=token_usage["output_tokens"],
            )

        return {
            "id": review.id,
            "status": review.status,
            "error_message": review.error_message,
            "summary": review.summary,
            "strengths": review.strengths,
            "weaknesses": review.weaknesses,
            "originality": review.originality,
            "quality": review.quality,
            "clarity": review.clarity,
            "significance": review.significance,
            "questions": review.questions,
            "limitations": review.limitations,
            "ethical_concerns": review.ethical_concerns,
            "soundness": review.soundness,
            "presentation": review.presentation,
            "contribution": review.contribution,
            "overall": review.overall,
            "confidence": review.confidence,
            "decision": review.decision,
            "original_filename": review.original_filename,
            "model": review.model,
            "created_at": review.created_at.isoformat(),
            "token_usage": token_usage,
            "credits_charged": credits_charged,
        }

    async def get_pending_reviews(self, *, user_id: int) -> list[dict[str, Any]]:
        """Get all pending or processing reviews for a user.

        Args:
            user_id: ID of the user

        Returns:
            List of pending/processing review dicts
        """
        db = get_database()
        reviews = await db.get_pending_reviews_by_user(user_id)

        return [
            {
                "id": review.id,
                "status": review.status,
                "original_filename": review.original_filename,
                "model": review.model,
                "created_at": review.created_at.isoformat(),
            }
            for review in reviews
        ]

    async def list_reviews(
        self,
        *,
        user_id: int,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """List paper reviews for a user.

        Args:
            user_id: ID of the user
            limit: Maximum number of reviews to return
            offset: Number of reviews to skip

        Returns:
            List of review summary dicts
        """
        db = get_database()
        reviews = await db.list_paper_reviews_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        return [
            {
                "id": review.id,
                "status": review.status,
                "summary": review.summary,
                "overall": review.overall,
                "decision": review.decision,
                "original_filename": review.original_filename,
                "model": review.model,
                "created_at": review.created_at.isoformat(),
            }
            for review in reviews
        ]


# Global service instance
_paper_review_service: PaperReviewService | None = None


def get_paper_review_service() -> PaperReviewService:
    """Get the global paper review service instance."""
    global _paper_review_service
    if _paper_review_service is None:
        _paper_review_service = PaperReviewService()
    return _paper_review_service
