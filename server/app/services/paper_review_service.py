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
from typing import Any, cast
from urllib.parse import quote

from ae_paper_review import ReviewProgressEvent, ReviewResult, load_paper, perform_review
from psycopg import AsyncConnection

from app.config import settings
from app.models.paper_review import PaperReviewDetail, TokenUsage
from app.services.billing_guard import charge_cents, enforce_minimum_balance
from app.services.database import PaperReviewStatus, get_database
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

# Advisory lock keys for paper review recovery (unique pair)
_PAPER_REVIEW_RECOVERY_LOCK_KEY_1 = 184467
_PAPER_REVIEW_RECOVERY_LOCK_KEY_2 = 991801

# How long a review can be in pending/processing before it's considered stale
_STALE_REVIEW_THRESHOLD_MINUTES = 15


def calculate_review_cost_cents(
    *,
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> int:
    """Calculate the cost for a review in cents based on token usage and model pricing.

    Uses the actual model pricing from JSON_MODEL_PRICE_PER_MILLION_IN_CENTS config.

    Args:
        model: Model in "provider:model" format (e.g., "openai:gpt-5.2")
        input_tokens: Total input tokens used (non-cached)
        cached_input_tokens: Number of cached input tokens
        output_tokens: Total output tokens used

    Returns:
        Cost in cents (rounded to nearest integer, minimum 1 cent)
    """
    # Get prices in cents per 1M tokens
    input_price_cents = settings.llm_pricing.get_input_price(model)
    cached_input_price_cents = settings.llm_pricing.get_cached_input_price(model)
    output_price_cents = settings.llm_pricing.get_output_price(model)

    # Calculate non-cached input tokens
    non_cached_input_tokens = input_tokens - cached_input_tokens

    # Calculate cost in cents
    input_cost_cents = (non_cached_input_tokens / 1_000_000) * input_price_cents
    cached_cost_cents = (cached_input_tokens / 1_000_000) * cached_input_price_cents
    output_cost_cents = (output_tokens / 1_000_000) * output_price_cents
    total_cost_cents = input_cost_cents + cached_cost_cents + output_cost_cents

    return max(1, int(total_cost_cents + 0.5))  # Round to nearest, minimum 1 cent


def _run_review_sync(
    paper_text: str,
    model: str,
    num_reviews_ensemble: int,
    num_reflections: int,
    review_id: int,
) -> ReviewResult:
    """Run the paper review synchronously (called in thread pool).

    This function is designed to be called via asyncio.to_thread() to avoid
    blocking the main event loop.

    Args:
        paper_text: The extracted text from the paper PDF
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        num_reviews_ensemble: Number of ensemble reviews
        num_reflections: Number of reflection rounds
        review_id: The paper review ID for progress tracking
    """
    db = get_database()

    def on_progress(event: ReviewProgressEvent) -> None:
        db.update_paper_review_progress_sync(
            review_id=review_id,
            progress=event.progress,
            progress_step=event.substep,
        )

    return perform_review(
        text=paper_text,
        model=model,
        temperature=1,
        num_reviews_ensemble=num_reviews_ensemble,
        num_reflections=num_reflections,
        event_callback=on_progress,
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
                review_id,
            )

            # Get token usage from result
            token_usages = result.token_usage_detailed
            total_usage = result.token_usage

            # Calculate cost based on actual model pricing
            cost_cents = calculate_review_cost_cents(
                model=model,
                input_tokens=total_usage.input_tokens,
                cached_input_tokens=total_usage.cached_input_tokens,
                output_tokens=total_usage.output_tokens,
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

            # Charge user for the review
            await charge_cents(
                user_id=user_id,
                amount_cents=cost_cents,
                action="paper_review",
                description=f"Paper review: {original_filename}",
                metadata={
                    "paper_review_id": review_id,
                    "model": model,
                    "input_tokens": total_usage.input_tokens,
                    "output_tokens": total_usage.output_tokens,
                },
            )

            # Set has_enough_credits based on user's balance after charging
            balance = await db.get_user_wallet_balance(user_id)
            has_enough_credits = balance > 0
            await db.set_paper_review_has_enough_credits(review_id, has_enough_credits)

            logger.info(
                "Paper review completed: review_id=%d, user_id=%d, cost=%d cents, has_enough_credits=%s",
                review_id,
                user_id,
                cost_cents,
                has_enough_credits,
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
            # Set has_enough_credits=True for failed reviews so users can see error details
            await db.set_paper_review_has_enough_credits(review_id, True)

        finally:
            # Clear progress (set to 1.0 for completed/failed)
            await db.clear_paper_review_progress(review_id)

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
    ) -> tuple[int, str]:
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
            Tuple of (review_id, status)

        Raises:
            HTTPException: If user has insufficient balance
        """
        db = get_database()

        # Check user has minimum balance
        await enforce_minimum_balance(
            user_id=user_id,
            required_cents=settings.billing_limits.min_balance_cents_for_paper_review,
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

        return (review_id, PaperReviewStatus.PENDING.value)

    async def get_review(self, *, review_id: int, user_id: int) -> PaperReviewDetail | None:
        """Get a paper review by ID.

        Args:
            review_id: ID of the review
            user_id: ID of the user (for authorization)

        Returns:
            PaperReviewDetail if found and owned by user, None otherwise
        """
        db = get_database()
        review = await db.get_paper_review_by_id(review_id)

        if not review or review.user_id != user_id:
            return None

        token_usage_dict = await db.get_total_token_usage_by_review_id(review_id)

        # Build TokenUsage if we have data
        token_usage: TokenUsage | None = None
        cost_cents = 0
        input_tokens = token_usage_dict.get("input_tokens", 0)
        output_tokens = token_usage_dict.get("output_tokens", 0)
        if input_tokens or output_tokens:
            cached_input_tokens = token_usage_dict.get("cached_input_tokens", 0)
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
            )
            cost_cents = calculate_review_cost_cents(
                model=review.model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
            )

        # Progress is now stored in the database, so it comes from review directly
        return PaperReviewDetail.from_review(
            review=review,
            token_usage=token_usage,
            cost_cents=cost_cents,
        )

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

        result = []
        for review in reviews:
            access_restricted = review.has_enough_credits is False
            result.append(
                {
                    "id": review.id,
                    "status": review.status,
                    "summary": review.summary if not access_restricted else None,
                    "overall": review.overall if not access_restricted else None,
                    "decision": review.decision if not access_restricted else None,
                    "original_filename": review.original_filename,
                    "model": review.model,
                    "created_at": review.created_at.isoformat(),
                    "has_enough_credits": review.has_enough_credits,
                    "access_restricted": access_restricted,
                    "progress": review.progress,
                    "progress_step": review.progress_step,
                }
            )
        return result

    async def get_paper_download_url(
        self, *, review_id: int, user_id: int, check_credits: bool = True
    ) -> tuple[str, str] | None:
        """Get a temporary download URL for the reviewed paper PDF.

        Args:
            review_id: ID of the review
            user_id: ID of the user (for authorization)
            check_credits: If True, blocks download when has_enough_credits is False

        Returns:
            Tuple of (download_url, filename) if found and owned by user, None otherwise
        """
        db = get_database()
        review = await db.get_paper_review_by_id(review_id)

        if not review or review.user_id != user_id:
            return None

        # Block download if access is restricted
        if check_credits and review.has_enough_credits is False:
            return None

        if not review.s3_key:
            return None

        # Generate a temporary download URL (valid for 1 hour)
        download_url = self._s3_service.generate_download_url(
            s3_key=review.s3_key,
            expires_in=3600,
        )

        return (download_url, review.original_filename or "paper.pdf")


# Global service instance
_paper_review_service: PaperReviewService | None = None


def get_paper_review_service() -> PaperReviewService:
    """Get the global paper review service instance."""
    global _paper_review_service
    if _paper_review_service is None:
        _paper_review_service = PaperReviewService()
    return _paper_review_service


async def _try_acquire_recovery_lock(conn: AsyncConnection[object]) -> bool:
    """Try to acquire the advisory lock for paper review recovery.

    Uses pg_try_advisory_lock which returns immediately (non-blocking).
    Only one server instance will succeed in acquiring the lock.
    """
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT pg_try_advisory_lock(%s, %s)",
                (_PAPER_REVIEW_RECOVERY_LOCK_KEY_1, _PAPER_REVIEW_RECOVERY_LOCK_KEY_2),
            )
            row = cast("tuple[object, ...] | None", await cursor.fetchone())
            if row is None:
                return False
            return bool(row[0])
    except Exception:
        logger.exception("Failed to acquire paper review recovery lock")
        return False


async def _release_recovery_lock(conn: AsyncConnection[object]) -> None:
    """Release the advisory lock for paper review recovery."""
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT pg_advisory_unlock(%s, %s)",
                (_PAPER_REVIEW_RECOVERY_LOCK_KEY_1, _PAPER_REVIEW_RECOVERY_LOCK_KEY_2),
            )
    except Exception:
        logger.exception("Failed to release paper review recovery lock")


async def recover_stale_paper_reviews() -> None:
    """Mark stale paper reviews as failed on server startup.

    This function uses a PostgreSQL advisory lock to ensure only one server
    instance performs the recovery, even when multiple instances start
    simultaneously.

    Reviews that have been in pending/processing status for longer than
    _STALE_REVIEW_THRESHOLD_MINUTES are marked as failed.
    """
    db = get_database()

    async with db.aget_connection() as conn:
        lock_acquired = await _try_acquire_recovery_lock(conn)
        if not lock_acquired:
            logger.debug("Another server instance is handling paper review recovery, skipping.")
            return

        try:
            count = await db.mark_stale_reviews_as_failed(
                stale_threshold_minutes=_STALE_REVIEW_THRESHOLD_MINUTES
            )
            if count > 0:
                logger.info(
                    "Marked %d stale paper review(s) as failed during startup recovery.",
                    count,
                )
            else:
                logger.debug("No stale paper reviews found during startup recovery.")
        finally:
            await _release_recovery_lock(conn)
