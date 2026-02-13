"""
Database helpers for standalone paper reviews.

Simplified version for AE Paper Review (no billing/credits).
"""

from datetime import datetime
from enum import Enum
from typing import NamedTuple

from ae_paper_review import TokenUsageDetail
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class PaperReviewStatus(str, Enum):
    """Status of a paper review."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TokenUsageTotal(NamedTuple):
    """Total token usage for a paper review."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class PaperReview(NamedTuple):
    """Represents a standalone paper review from the database."""

    id: int
    user_id: int
    summary: str
    strengths: list[str] | None
    weaknesses: list[str] | None
    originality: int | None
    quality: int | None
    clarity: int | None
    significance: int | None
    questions: list[str] | None
    limitations: list[str] | None
    ethical_concerns: bool | None
    ethical_concerns_explanation: str
    soundness: int | None
    presentation: int | None
    contribution: int | None
    overall: int | None
    confidence: int | None
    decision: str | None
    original_filename: str
    s3_key: str | None
    model: str
    status: str
    error_message: str | None
    created_at: datetime
    progress: float
    progress_step: str


class PaperReviewsDatabaseMixin(ConnectionProvider):
    """Database operations for standalone paper reviews."""

    async def create_pending_paper_review(
        self,
        *,
        user_id: int,
        original_filename: str,
        s3_key: str,
        model: str,
    ) -> int:
        """Create a pending paper review and return its ID."""
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
        error_message: str | None = None,
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
        strengths: list[str],
        weaknesses: list[str],
        originality: int,
        quality: int,
        clarity: int,
        significance: int,
        questions: list[str],
        limitations: list[str],
        ethical_concerns: bool,
        ethical_concerns_explanation: str,
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
                        ethical_concerns_explanation = %s,
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
                        ethical_concerns_explanation,
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

    async def get_pending_reviews_by_user(self, user_id: int) -> list[PaperReview]:
        """Get all pending or processing reviews for a user."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   ethical_concerns_explanation,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   progress, progress_step
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

    async def get_paper_review_by_id(self, review_id: int) -> PaperReview | None:
        """Fetch a paper review by its ID."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   ethical_concerns_explanation,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   progress, progress_step
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
    ) -> list[PaperReview]:
        """List paper reviews for a user, ordered by creation time (newest first)."""
        query = """
            SELECT id, user_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   ethical_concerns_explanation,
                   soundness, presentation, contribution, overall, confidence, decision,
                   original_filename, s3_key, model, status, error_message, created_at,
                   progress, progress_step
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
        """Mark paper reviews stuck in pending/processing as failed."""
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

    def update_paper_review_progress_sync(
        self,
        review_id: int,
        progress: float,
        progress_step: str,
    ) -> None:
        """Update the progress of a paper review (sync version for use from threads)."""
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
        """Clear progress for a completed/failed review."""
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

    async def insert_paper_review_token_usages_batch(
        self, *, paper_review_id: int, usages: list[TokenUsageDetail]
    ) -> None:
        """Insert token usages for a paper review.

        Args:
            paper_review_id: The paper review ID
            usages: List of TokenUsageDetail with model (in "provider:model" format),
                    input_tokens, cached_input_tokens, output_tokens
        """
        if not usages:
            return

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                for usage in usages:
                    # Parse provider:model format (e.g., "openai:gpt-5.2")
                    if ":" in usage.model:
                        provider, model = usage.model.split(":", 1)
                    else:
                        provider = "unknown"
                        model = usage.model

                    await cursor.execute(
                        """
                        INSERT INTO paper_review_token_usages
                            (paper_review_id, provider, model, input_tokens,
                             cached_input_tokens, output_tokens)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            paper_review_id,
                            provider,
                            model,
                            usage.input_tokens,
                            usage.cached_input_tokens,
                            usage.output_tokens,
                        ),
                    )

    async def get_total_token_usage_by_review_id(self, review_id: int) -> TokenUsageTotal:
        """Get total token usage for a review."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT COALESCE(SUM(input_tokens), 0) as input_tokens,
                           COALESCE(SUM(cached_input_tokens), 0) as cached_input_tokens,
                           COALESCE(SUM(output_tokens), 0) as output_tokens
                    FROM paper_review_token_usages
                    WHERE paper_review_id = %s
                    """,
                    (review_id,),
                )
                result = await cursor.fetchone()
                if result:
                    return TokenUsageTotal(
                        input_tokens=int(result["input_tokens"]),
                        cached_input_tokens=int(result["cached_input_tokens"]),
                        output_tokens=int(result["output_tokens"]),
                    )
                return TokenUsageTotal(input_tokens=0, cached_input_tokens=0, output_tokens=0)
