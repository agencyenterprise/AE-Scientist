"""
Database helpers for standalone paper reviews.
"""

from datetime import datetime
from enum import Enum
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class PaperReviewStatus(str, Enum):
    """Status of a paper review."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaperReview(NamedTuple):
    """Represents a standalone paper review from the database."""

    id: int
    user_id: int
    summary: str
    strengths: Optional[list]
    weaknesses: Optional[list]
    originality: Optional[int]
    quality: Optional[int]
    clarity: Optional[int]
    significance: Optional[int]
    questions: Optional[list]
    limitations: Optional[list]
    ethical_concerns: Optional[bool]
    soundness: Optional[int]
    presentation: Optional[int]
    contribution: Optional[int]
    overall: Optional[int]
    confidence: Optional[int]
    decision: Optional[str]
    original_filename: str
    s3_key: Optional[str]
    model: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    progress: float
    progress_step: str
    has_enough_credits: Optional[bool] = None


class PaperReviewsMixin(ConnectionProvider):
    """Database operations for standalone paper reviews."""

    async def create_pending_paper_review(
        self,
        *,
        user_id: int,
        original_filename: str,
        s3_key: str,
        model: str,
    ) -> int:
        """Create a pending paper review and return its ID.

        This creates a review record with status='pending' that can be
        updated later when the review completes.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_reviews
                        (user_id, summary, original_filename, s3_key, model, status,
                         progress, progress_step)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        "",  # Empty summary for pending review
                        original_filename,
                        s3_key,
                        model,
                        PaperReviewStatus.PENDING.value,
                        0.0,  # Initial progress
                        "",  # Empty progress step
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create pending paper review")
                return int(result["id"])

    async def update_paper_review_status(
        self,
        review_id: int,
        status: PaperReviewStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the status of a paper review."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET status = %s, error_message = %s
                    WHERE id = %s
                    """,
                    (status.value, error_message, review_id),
                )

    async def complete_paper_review(
        self,
        *,
        review_id: int,
        summary: str,
        strengths: list,
        weaknesses: list,
        originality: int,
        quality: int,
        clarity: int,
        significance: int,
        questions: list,
        limitations: list,
        ethical_concerns: bool,
        soundness: int,
        presentation: int,
        contribution: int,
        overall: int,
        confidence: int,
        decision: str,
    ) -> None:
        """Update a pending/processing review with completed results."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET summary = %s, strengths = %s, weaknesses = %s,
                        originality = %s, quality = %s, clarity = %s, significance = %s,
                        questions = %s, limitations = %s, ethical_concerns = %s,
                        soundness = %s, presentation = %s, contribution = %s,
                        overall = %s, confidence = %s, decision = %s,
                        status = %s
                    WHERE id = %s
                    """,
                    (
                        summary,
                        Jsonb(strengths),
                        Jsonb(weaknesses),
                        originality,
                        quality,
                        clarity,
                        significance,
                        Jsonb(questions),
                        Jsonb(limitations),
                        ethical_concerns,
                        soundness,
                        presentation,
                        contribution,
                        overall,
                        confidence,
                        decision,
                        PaperReviewStatus.COMPLETED.value,
                        review_id,
                    ),
                )

    async def get_pending_reviews_by_user(self, user_id: int) -> List[PaperReview]:
        """Get all pending or processing reviews for a user."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   has_enough_credits, progress, progress_step
            FROM paper_reviews
            WHERE user_id = %s AND status IN (%s, %s)
            ORDER BY created_at DESC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    query,
                    (user_id, PaperReviewStatus.PENDING.value, PaperReviewStatus.PROCESSING.value),
                )
                rows = await cursor.fetchall() or []
        return [PaperReview(**row) for row in rows]

    async def insert_paper_review(
        self,
        *,
        user_id: int,
        summary: str,
        strengths: list,
        weaknesses: list,
        originality: int,
        quality: int,
        clarity: int,
        significance: int,
        questions: list,
        limitations: list,
        ethical_concerns: bool,
        soundness: int,
        presentation: int,
        contribution: int,
        overall: int,
        confidence: int,
        decision: str,
        model: str,
        original_filename: Optional[str] = None,
        s3_key: Optional[str] = None,
    ) -> int:
        """Insert a completed paper review and return its ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_reviews
                        (user_id, summary, strengths, weaknesses, originality, quality,
                         clarity, significance, questions, limitations, ethical_concerns,
                         soundness, presentation, contribution, overall, confidence,
                         decision, original_filename, s3_key, model, status,
                         progress, progress_step)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        summary,
                        Jsonb(strengths),
                        Jsonb(weaknesses),
                        originality,
                        quality,
                        clarity,
                        significance,
                        Jsonb(questions),
                        Jsonb(limitations),
                        ethical_concerns,
                        soundness,
                        presentation,
                        contribution,
                        overall,
                        confidence,
                        decision,
                        original_filename,
                        s3_key,
                        model,
                        PaperReviewStatus.COMPLETED.value,
                        1.0,  # Completed review progress
                        "",  # Empty progress step for completed review
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert paper review")
                return int(result["id"])

    async def get_paper_review_by_id(self, review_id: int) -> Optional[PaperReview]:
        """Fetch a paper review by its ID."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   has_enough_credits, progress, progress_step
            FROM paper_reviews
            WHERE id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (review_id,))
                row = await cursor.fetchone()
        if not row:
            return None
        return PaperReview(**row)

    async def list_paper_reviews_by_user(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> List[PaperReview]:
        """List paper reviews for a user, ordered by creation time (newest first)."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   progress, progress_step, has_enough_credits
            FROM paper_reviews
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (user_id, limit, offset))
                rows = await cursor.fetchall() or []
        return [PaperReview(**row) for row in rows]

    async def mark_stale_reviews_as_failed(self, stale_threshold_minutes: int = 15) -> int:
        """Mark paper reviews stuck in pending/processing as failed.

        This is used on server startup to clean up reviews that were interrupted
        by a server restart.

        Args:
            stale_threshold_minutes: Reviews older than this many minutes in
                pending/processing status will be marked as failed.

        Returns:
            Number of reviews marked as failed.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET status = %s,
                        error_message = %s
                    WHERE status IN (%s, %s)
                      AND created_at < NOW() - INTERVAL '%s minutes'
                    """,
                    (
                        PaperReviewStatus.FAILED.value,
                        "Review interrupted by server restart. Please try again.",
                        PaperReviewStatus.PENDING.value,
                        PaperReviewStatus.PROCESSING.value,
                        stale_threshold_minutes,
                    ),
                )
                return cursor.rowcount or 0

    async def set_paper_review_has_enough_credits(
        self, review_id: int, has_enough_credits: bool
    ) -> None:
        """Set the has_enough_credits flag for a paper review.

        This is called when a review completes to record whether the user
        had positive balance at completion time.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = %s
                    WHERE id = %s
                    """,
                    (has_enough_credits, review_id),
                )

    async def unlock_paper_reviews_for_user(self, user_id: int) -> int:
        """Unlock paper reviews for a user by setting has_enough_credits to TRUE.

        This is called when a user adds credits and their balance becomes positive.

        Returns:
            Number of reviews unlocked.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = TRUE
                    WHERE user_id = %s
                      AND has_enough_credits = FALSE
                    """,
                    (user_id,),
                )
                return cursor.rowcount or 0

    async def lock_active_paper_reviews_for_user(self, user_id: int) -> int:
        """Lock active paper reviews for a user by setting has_enough_credits to FALSE.

        This is called when a user's balance goes negative from any charge.
        Only locks reviews that are still in progress (pending or processing).

        Returns:
            Number of reviews locked.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = FALSE
                    WHERE user_id = %s
                      AND status IN ('pending', 'processing')
                    """,
                    (user_id,),
                )
                return cursor.rowcount or 0

    def update_paper_review_progress_sync(
        self,
        review_id: int,
        progress: float,
        progress_step: str,
    ) -> None:
        """Update the progress of a paper review (sync version for use from threads).

        This is called from the sync thread running the LLM review to update
        progress in the database.

        Args:
            review_id: The paper review ID
            progress: Progress value (0.0 to 1.0)
            progress_step: Description of current step
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET progress = %s, progress_step = %s
                    WHERE id = %s
                    """,
                    (progress, progress_step, review_id),
                )

    async def clear_paper_review_progress(self, review_id: int) -> None:
        """Clear progress for a completed/failed review.

        Sets progress to 1.0 and clears progress_step.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET progress = 1.0, progress_step = ''
                    WHERE id = %s
                    """,
                    (review_id,),
                )
