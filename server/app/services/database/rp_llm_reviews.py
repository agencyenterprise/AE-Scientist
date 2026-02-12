"""
Database helpers for research pipeline LLM reviews.
"""

from datetime import datetime
from typing import NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class LlmReview(NamedTuple):
    id: int
    run_id: str
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
    ethical_concerns_explanation: str
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str
    source_path: Optional[str]
    created_at: datetime


class ResearchPipelineLlmReviewsMixin(ConnectionProvider):
    """Helpers to read and write LLM review data stored in rp_llm_reviews."""

    async def insert_llm_review(
        self,
        *,
        run_id: str,
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
        ethical_concerns_explanation: str,
        soundness: int,
        presentation: int,
        contribution: int,
        overall: int,
        confidence: int,
        decision: str,
        source_path: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Insert an LLM review and return its ID."""
        if created_at is None:
            created_at = datetime.now()

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO rp_llm_reviews
                        (run_id, summary, strengths, weaknesses, originality, quality, clarity,
                         significance, questions, limitations, ethical_concerns,
                         ethical_concerns_explanation, soundness,
                         presentation, contribution, overall, confidence, decision, source_path, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        run_id,
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
                        source_path,
                        created_at,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert LLM review")
                return int(result["id"])

    async def get_review_by_run_id(self, run_id: str) -> Optional[LlmReview]:
        """Fetch the LLM review for a specific research run.

        Args:
            run_id: The research pipeline run identifier

        Returns:
            LlmReview with all review fields, or None if no review exists for this run
        """
        query = """
            SELECT id, run_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   ethical_concerns_explanation, soundness, presentation, contribution,
                   overall, confidence, decision, source_path, created_at
            FROM rp_llm_reviews
            WHERE run_id = %s
            LIMIT 1
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()
        if not row:
            return None
        return LlmReview(**row)
