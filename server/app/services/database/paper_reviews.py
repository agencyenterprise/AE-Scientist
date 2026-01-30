"""
Database helpers for standalone paper reviews.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class PaperReview(NamedTuple):
    """Represents a standalone paper review."""

    id: int
    user_id: int
    summary: str
    strengths: list
    weaknesses: list
    originality: int
    quality: int
    clarity: int
    significance: int
    questions: list
    limitations: list
    ethical_concerns: bool
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str
    original_filename: Optional[str]
    s3_key: Optional[str]
    model: str
    created_at: datetime


class PaperReviewsMixin(ConnectionProvider):
    """Database operations for standalone paper reviews."""

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
        """Insert a paper review and return its ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_reviews
                        (user_id, summary, strengths, weaknesses, originality, quality,
                         clarity, significance, questions, limitations, ethical_concerns,
                         soundness, presentation, contribution, overall, confidence,
                         decision, original_filename, s3_key, model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                   original_filename, s3_key, model, created_at
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
                   original_filename, s3_key, model, created_at
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
