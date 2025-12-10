"""
Database helpers for research pipeline LLM reviews.
"""

from datetime import datetime
from typing import Any, Dict, NamedTuple, Optional

import psycopg2
import psycopg2.extras

from .base import ConnectionProvider


class LlmReview(NamedTuple):
    id: int
    run_id: str
    summary: str
    strengths: list
    weaknesses: list
    originality: float
    quality: float
    clarity: float
    significance: float
    questions: list
    limitations: list
    ethical_concerns: bool
    soundness: float
    presentation: float
    contribution: float
    overall: float
    confidence: float
    decision: str
    source_path: Optional[str]
    created_at: datetime


class ResearchPipelineLlmReviewsMixin(ConnectionProvider):
    """Helpers to read LLM review data stored in rp_llm_reviews."""

    def get_review_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the LLM review for a specific research run.

        Args:
            run_id: The research pipeline run identifier

        Returns:
            Dictionary with all review fields, or None if no review exists for this run
        """
        query = """
            SELECT id, run_id, summary, strengths, weaknesses, originality, quality,
                   clarity, significance, questions, limitations, ethical_concerns,
                   soundness, presentation, contribution, overall, confidence, decision,
                   source_path, created_at
            FROM rp_llm_reviews
            WHERE run_id = %s
            LIMIT 1
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (run_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
