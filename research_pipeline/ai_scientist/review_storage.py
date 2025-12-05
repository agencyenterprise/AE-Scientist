from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from ai_scientist.perform_llm_review import ReviewResponseModel
from ai_scientist.perform_vlm_review import FigureImageCaptionRefReview
from ai_scientist.telemetry.event_persistence import _parse_database_url

logger = logging.getLogger(__name__)


@dataclass
class ReviewResponseRecorder:
    """Persists structured LLM review outputs to Postgres."""

    _pg_config: dict[str, Any]
    _run_id: str

    @classmethod
    def from_database_url(cls, *, database_url: str, run_id: str) -> "ReviewResponseRecorder":
        return cls(_parse_database_url(database_url), run_id)

    def insert_review(
        self, *, review: ReviewResponseModel, source_path: Path | None = None
    ) -> None:
        payload = review.model_dump()
        strengths = psycopg2.extras.Json(payload.get("Strengths", []))
        weaknesses = psycopg2.extras.Json(payload.get("Weaknesses", []))
        questions = psycopg2.extras.Json(payload.get("Questions", []))
        limitations = psycopg2.extras.Json(payload.get("Limitations", []))
        source_value = str(source_path) if source_path is not None else None

        try:
            with psycopg2.connect(**self._pg_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO rp_llm_reviews (
                            run_id,
                            summary,
                            strengths,
                            weaknesses,
                            originality,
                            quality,
                            clarity,
                            significance,
                            questions,
                            limitations,
                            ethical_concerns,
                            soundness,
                            presentation,
                            contribution,
                            overall,
                            confidence,
                            decision,
                            source_path
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            self._run_id,
                            review.Summary,
                            strengths,
                            weaknesses,
                            review.Originality,
                            review.Quality,
                            review.Clarity,
                            review.Significance,
                            questions,
                            limitations,
                            review.Ethical_Concerns,
                            review.Soundness,
                            review.Presentation,
                            review.Contribution,
                            review.Overall,
                            review.Confidence,
                            review.Decision,
                            source_value,
                        ),
                    )
        except psycopg2.Error:
            logger.exception("Failed to persist LLM review response for run_id=%s", self._run_id)


@dataclass
class FigureReviewRecorder:
    """Persists structured VLM figure reviews to Postgres."""

    _pg_config: dict[str, Any]
    _run_id: str

    @classmethod
    def from_database_url(cls, *, database_url: str, run_id: str) -> "FigureReviewRecorder":
        return cls(_parse_database_url(database_url), run_id)

    def insert_reviews(
        self, *, reviews: list[FigureImageCaptionRefReview], source_path: Path | None = None
    ) -> None:
        if not reviews:
            return
        source_value = str(source_path) if source_path is not None else None
        rows = [
            (
                self._run_id,
                review.figure_name,
                review.review.Img_description,
                review.review.Img_review,
                review.review.Caption_review,
                review.review.Figrefs_review,
                source_value,
            )
            for review in reviews
        ]
        try:
            with psycopg2.connect(**self._pg_config) as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO rp_vlm_figure_reviews (
                            run_id,
                            figure_name,
                            img_description,
                            img_review,
                            caption_review,
                            figrefs_review,
                            source_path
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        rows,
                    )
        except psycopg2.Error:
            logger.exception("Failed to persist VLM figure reviews for run_id=%s", self._run_id)
