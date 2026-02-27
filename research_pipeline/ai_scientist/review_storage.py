import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ae_paper_review import (
    AEScientistReviewModel,
    ICLRReviewModel,
    NeurIPSReviewModel,
    ReviewModel,
)

from ai_scientist.api_types import (
    FigureReviewEvent,
    FigureReviewsEvent,
    ReviewCompletedEvent,
)
from ai_scientist.telemetry.event_persistence import WebhookClient
from ai_scientist.vlm import FigureImageCaptionRefReview

logger = logging.getLogger(__name__)


def _to_review_completed_event(
    *,
    review: ReviewModel,
    source_path: str | None,
    created_at: str,
) -> ReviewCompletedEvent:
    if isinstance(review, AEScientistReviewModel):
        return ReviewCompletedEvent(
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
            ethical_concerns_explanation=review.ethical_concerns_explanation,
            soundness=review.soundness,
            presentation=review.presentation,
            contribution=review.contribution,
            overall=review.overall,
            confidence=review.confidence,
            decision=review.decision,
            source_path=source_path,
            created_at=created_at,
        )
    if isinstance(review, NeurIPSReviewModel):
        return ReviewCompletedEvent(
            summary=review.summary,
            strengths=[review.strengths_and_weaknesses],
            weaknesses=[],
            originality=review.originality,
            quality=review.quality,
            clarity=review.clarity,
            significance=review.significance,
            questions=review.questions,
            limitations=[review.limitations],
            ethical_concerns=review.ethical_concerns,
            ethical_concerns_explanation=review.ethical_concerns_explanation,
            soundness=0,
            presentation=0,
            contribution=0,
            overall=review.overall,
            confidence=review.confidence,
            decision=review.decision,
            source_path=source_path,
            created_at=created_at,
        )
    if isinstance(review, ICLRReviewModel):
        return ReviewCompletedEvent(
            summary=review.summary,
            strengths=review.strengths,
            weaknesses=review.weaknesses,
            originality=0,
            quality=0,
            clarity=0,
            significance=0,
            questions=review.questions,
            limitations=[review.limitations],
            ethical_concerns=review.ethical_concerns,
            ethical_concerns_explanation=review.ethical_concerns_explanation,
            soundness=review.soundness,
            presentation=review.presentation,
            contribution=review.contribution,
            overall=review.overall,
            confidence=review.confidence,
            decision=review.decision,
            source_path=source_path,
            created_at=created_at,
        )
    # ICMLReviewModel
    return ReviewCompletedEvent(
        summary=review.summary,
        strengths=[review.claims_and_evidence],
        weaknesses=[review.other_aspects],
        originality=0,
        quality=0,
        clarity=0,
        significance=0,
        questions=review.questions,
        limitations=[],
        ethical_concerns=review.ethical_issues,
        ethical_concerns_explanation=review.ethical_issues_explanation,
        soundness=0,
        presentation=0,
        contribution=0,
        overall=review.overall,
        confidence=0,
        decision=review.decision,
        source_path=source_path,
        created_at=created_at,
    )


@dataclass
class ReviewResponseRecorder:
    """Publishes structured LLM review outputs via webhooks."""

    _run_id: str
    _webhook_client: WebhookClient | None

    @classmethod
    def from_webhook_client(
        cls,
        *,
        run_id: str,
        webhook_client: WebhookClient | None,
    ) -> "ReviewResponseRecorder":
        return cls(_run_id=run_id, _webhook_client=webhook_client)

    def insert_review(self, *, review: ReviewModel, source_path: Path | None) -> None:
        """Publish review via webhook. Database persistence handled by server."""
        source_value = str(source_path) if source_path is not None else None
        created_at = datetime.now(timezone.utc).isoformat()

        if self._webhook_client is not None:
            try:
                self._webhook_client.publish(
                    kind="review_completed",
                    payload=_to_review_completed_event(
                        review=review,
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
    _webhook_client: WebhookClient | None

    @classmethod
    def from_webhook_client(
        cls, *, run_id: str, webhook_client: WebhookClient | None
    ) -> "FigureReviewRecorder":
        return cls(_run_id=run_id, _webhook_client=webhook_client)

    def insert_reviews(
        self, *, reviews: list[FigureImageCaptionRefReview], source_path: Path | None
    ) -> None:
        """Publish reviews via webhook. Database persistence handled by server."""
        if not reviews:
            return
        source_value = str(source_path) if source_path is not None else None

        if self._webhook_client is not None:
            try:
                review_events = [
                    FigureReviewEvent(
                        figure_name=review.figure_name,
                        img_description=review.review.img_description,
                        img_review=review.review.img_review,
                        caption_review=review.review.caption_review,
                        figrefs_review=review.review.figrefs_review,
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
