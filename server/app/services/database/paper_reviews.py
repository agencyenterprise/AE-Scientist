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
    """Represents a standalone paper review."""

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
    original_filename: Optional[str]
    s3_key: Optional[str]
    model: str
    status: str
    error_message: Optional[str]
    created_at: datetime


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
                        (user_id, summary, original_filename, s3_key, model, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        "",  # Empty summary for pending review
                        original_filename,
                        s3_key,
                        model,
                        PaperReviewStatus.PENDING.value,
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
                   original_filename, s3_key, model, status, error_message, created_at
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
                         decision, original_filename, s3_key, model, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                   original_filename, s3_key, model, status, error_message, created_at
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
                   original_filename, s3_key, model, status, error_message, created_at
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
