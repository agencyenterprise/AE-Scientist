import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_scientist.api_types import (
    FigureReviewEvent,
    FigureReviewsEvent,
    ReviewCompletedEvent,
)
from ai_scientist.perform_llm_review import ReviewResponseModel
from ai_scientist.perform_vlm_review import FigureImageCaptionRefReview
from ai_scientist.telemetry.event_persistence import WebhookClient

logger = logging.getLogger(__name__)


@dataclass
class ReviewResponseRecorder:
    """Publishes structured LLM review outputs via webhooks."""

    _run_id: str
    _webhook_client: WebhookClient | None = None

    @classmethod
    def from_webhook_client(
        cls,
        *,
        run_id: str,
        webhook_client: WebhookClient | None = None,
    ) -> "ReviewResponseRecorder":
        return cls(run_id, webhook_client)

    def insert_review(
        self, *, review: ReviewResponseModel, source_path: Path | None = None
    ) -> None:
        """Publish review via webhook. Database persistence handled by server."""
        payload = review.model_dump()
        source_value = str(source_path) if source_path is not None else None
        created_at = datetime.now(timezone.utc).isoformat()

        # Emit SSE event via webhook
        if self._webhook_client is not None:
            try:
                self._webhook_client.publish(
                    kind="review_completed",
                    payload=ReviewCompletedEvent(
                        summary=review.Summary,
                        strengths=payload.get("Strengths", []),
                        weaknesses=payload.get("Weaknesses", []),
                        originality=float(review.Originality),
                        quality=float(review.Quality),
                        clarity=float(review.Clarity),
                        significance=float(review.Significance),
                        questions=payload.get("Questions", []),
                        limitations=payload.get("Limitations", []),
                        ethical_concerns=review.Ethical_Concerns,
                        soundness=float(review.Soundness),
                        presentation=float(review.Presentation),
                        contribution=float(review.Contribution),
                        overall=float(review.Overall),
                        confidence=float(review.Confidence),
                        decision=review.Decision,
                        source_path=source_value,
                        created_at=created_at,
                    ),
                )
                logger.info("Emitted review SSE event for run_id=%s", self._run_id)
            except Exception:
                logger.exception("Failed to emit review SSE event")
                raise
        else:
            logger.warning("webhook_client is None, skipping review SSE event emission")


@dataclass
class FigureReviewRecorder:
    """Publishes structured VLM figure reviews via webhooks."""

    _run_id: str
    _webhook_client: WebhookClient | None = None

    @classmethod
    def from_webhook_client(
        cls, *, run_id: str, webhook_client: WebhookClient | None = None
    ) -> "FigureReviewRecorder":
        return cls(run_id, webhook_client)

    def insert_reviews(
        self, *, reviews: list[FigureImageCaptionRefReview], source_path: Path | None = None
    ) -> None:
        """Publish reviews via webhook. Database persistence handled by server."""
        if not reviews:
            return
        source_value = str(source_path) if source_path is not None else None

        # Emit webhook event
        if self._webhook_client is not None:
            try:
                review_events = [
                    FigureReviewEvent(
                        figure_name=review.figure_name,
                        img_description=review.review.Img_description,
                        img_review=review.review.Img_review,
                        caption_review=review.review.Caption_review,
                        figrefs_review=review.review.Figrefs_review,
                        source_path=source_value,
                    )
                    for review in reviews
                ]
                self._webhook_client.publish(
                    kind="figure_reviews",
                    payload=FigureReviewsEvent(reviews=review_events),
                )
                logger.info("Emitted figure reviews webhook for run_id=%s", self._run_id)
            except Exception:
                logger.exception("Failed to emit figure reviews webhook")
                raise
        else:
            logger.warning("webhook_client is None, skipping figure reviews webhook emission")
