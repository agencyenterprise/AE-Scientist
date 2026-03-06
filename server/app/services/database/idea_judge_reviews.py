"""
Database helpers for idea judge reviews.

Each review stores the per-criterion results as JSONB alongside the
aggregate score and recommendation, keyed by idea_id + idea_version_id.
"""

import logging
from datetime import datetime
from typing import Any, Dict, NamedTuple, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class IdeaJudgeReviewData(NamedTuple):
    """Row returned from idea_judge_reviews."""

    id: int
    idea_id: int
    idea_version_id: Optional[int]
    relevance: Dict[str, Any]
    feasibility: Dict[str, Any]
    novelty: Dict[str, Any]
    impact: Dict[str, Any]
    revision: Optional[Dict[str, Any]]
    overall_score: float
    recommendation: str
    summary: str
    llm_model: Optional[str]
    created_at: datetime


class IdeaJudgeReviewsMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Database operations for idea judge reviews."""

    async def create_idea_judge_review(
        self,
        *,
        idea_id: int,
        idea_version_id: Optional[int],
        relevance: Dict[str, Any],
        feasibility: Dict[str, Any],
        novelty: Dict[str, Any],
        impact: Dict[str, Any],
        revision: Dict[str, Any],
        overall_score: float,
        recommendation: str,
        summary: str,
        llm_model: Optional[str] = None,
    ) -> int:
        """Persist a judge review. Returns the new row id."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO idea_judge_reviews (
                        idea_id, idea_version_id,
                        relevance, feasibility, novelty, impact, revision,
                        overall_score, recommendation, summary,
                        llm_model, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        idea_id,
                        idea_version_id,
                        Jsonb(relevance),
                        Jsonb(feasibility),
                        Jsonb(novelty),
                        Jsonb(impact),
                        Jsonb(revision),
                        overall_score,
                        recommendation,
                        summary,
                        llm_model,
                        now,
                    ),
                )
                row = await cursor.fetchone()
                if not row:
                    raise ValueError("Failed to create idea_judge_review (missing id).")
                return int(row[0])

    async def get_idea_judge_review_by_idea_id(
        self, idea_id: int
    ) -> Optional[IdeaJudgeReviewData]:
        """Return the most recent judge review for a given idea, or None."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        id, idea_id, idea_version_id,
                        relevance, feasibility, novelty, impact, revision,
                        overall_score, recommendation, summary,
                        llm_model, created_at
                    FROM idea_judge_reviews
                    WHERE idea_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (idea_id,),
                )
                row = await cursor.fetchone()
        if not row:
            return None
        return IdeaJudgeReviewData(
            id=row["id"],
            idea_id=row["idea_id"],
            idea_version_id=row["idea_version_id"],
            relevance=row["relevance"],
            feasibility=row["feasibility"],
            novelty=row["novelty"],
            impact=row["impact"],
            revision=row.get("revision"),
            overall_score=row["overall_score"],
            recommendation=row["recommendation"],
            summary=row["summary"],
            llm_model=row["llm_model"],
            created_at=row["created_at"],
        )

    async def get_idea_judge_reviews_by_idea_id(
        self, idea_id: int
    ) -> list[IdeaJudgeReviewData]:
        """Return all judge reviews for a given idea, newest first."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        id, idea_id, idea_version_id,
                        relevance, feasibility, novelty, impact, revision,
                        overall_score, recommendation, summary,
                        llm_model, created_at
                    FROM idea_judge_reviews
                    WHERE idea_id = %s
                    ORDER BY created_at DESC
                    """,
                    (idea_id,),
                )
                rows = await cursor.fetchall()
        return [
            IdeaJudgeReviewData(
                id=row["id"],
                idea_id=row["idea_id"],
                idea_version_id=row["idea_version_id"],
                relevance=row["relevance"],
                feasibility=row["feasibility"],
                novelty=row["novelty"],
                impact=row["impact"],
                revision=row.get("revision"),
                overall_score=row["overall_score"],
                recommendation=row["recommendation"],
                summary=row["summary"],
                llm_model=row["llm_model"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
