"""Fake data generation methods for FakeRunner."""

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

# fmt: off
# isort: off
from research_pipeline.ai_scientist.api_types import (  # type: ignore[import-not-found]
    BestNodeSelectionEvent,
    FigureReviewEvent,
    FigureReviewsEvent,
    ReviewCompletedEvent,
    TokenUsageEvent,
)
# isort: on
# fmt: on
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    PersistableEvent,
)

if TYPE_CHECKING:
    from .core import FakeRunnerCore

logger = logging.getLogger(__name__)


class FakeDataMixin:
    """Mixin providing fake data generation methods for FakeRunner."""

    # Type hints for methods/attributes from FakeRunnerCore
    _run_id: str
    _webhook_client: Any
    _webhooks: "FakeRunnerCore._webhooks"  # type: ignore[name-defined]
    _persistence: "FakeRunnerCore._persistence"  # type: ignore[name-defined]

    def _emit_fake_token_usage(self) -> None:
        """Emit fake token usage events to exercise the token_usage webhook."""
        stages = ["1_initial_implementation", "2_baseline_tuning", "3_creative_research"]
        for stage in stages:
            payload = TokenUsageEvent(
                provider="openai",
                model="gpt-4o",
                input_tokens=15000 + hash(stage) % 5000,
                output_tokens=3000 + hash(stage) % 1000,
                cached_input_tokens=8000 + hash(stage) % 2000,
            )
            try:
                self._webhooks.publish_token_usage(payload)
            except Exception:
                logger.exception(
                    "[FakeRunner %s] Failed to publish token_usage for stage %s",
                    self._run_id[:8],
                    stage,
                )
        logger.info(
            "[FakeRunner %s] Posted token_usage webhooks for %d stages",
            self._run_id[:8],
            len(stages),
        )

    def _emit_fake_hw_stats(self) -> None:
        """Emit fake hardware stats to exercise the hw-stats webhook."""
        partitions = [
            {"partition": "/", "total_bytes": 500_000_000_000, "used_bytes": 150_000_000_000},
            {
                "partition": "/workspace",
                "total_bytes": 200_000_000_000,
                "used_bytes": 50_000_000_000,
            },
        ]
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_hw_stats(partitions=partitions)
                logger.info("[FakeRunner %s] Posted hw-stats webhook", self._run_id[:8])
        except Exception:
            logger.exception("[FakeRunner %s] Failed to publish hw-stats", self._run_id[:8])

    def _emit_fake_figure_reviews(self) -> None:
        """Emit fake VLM figure reviews to exercise the figure_reviews webhook."""
        fake_reviews: list[dict[str, str | None]] = [
            {
                "figure_name": "Figure 1",
                "img_description": "A line plot showing training loss curves over 100 epochs. The blue line represents the baseline model while the orange line shows our improved method.",
                "img_review": "The figure clearly demonstrates the convergence behavior of both methods. The improved method shows faster convergence and lower final loss.",
                "caption_review": "Caption accurately describes the plot contents and provides context for interpretation.",
                "figrefs_review": "Figure is appropriately referenced in Section 3.2 when discussing training dynamics.",
                "source_path": "plots/loss_curves.png",
            },
            {
                "figure_name": "Figure 2",
                "img_description": "A bar chart comparing accuracy metrics across three datasets: MNIST, CIFAR-10, and ImageNet.",
                "img_review": "Clear visualization of comparative performance. Error bars would improve the figure by showing statistical significance.",
                "caption_review": "Caption is informative but could benefit from including exact numerical values.",
                "figrefs_review": "Referenced correctly in the results section.",
                "source_path": "plots/accuracy_comparison.png",
            },
            {
                "figure_name": "Figure 3",
                "img_description": "Architecture diagram showing the neural network structure with attention mechanisms.",
                "img_review": "Well-designed diagram that clearly illustrates the model architecture. The attention module connections are easy to follow.",
                "caption_review": "Comprehensive caption explaining each component of the architecture.",
                "figrefs_review": "Properly referenced in Section 2 (Methodology) and Section 4 (Discussion).",
                "source_path": None,
            },
        ]

        try:
            review_events = [
                FigureReviewEvent(
                    figure_name=r["figure_name"],
                    img_description=r["img_description"],
                    img_review=r["img_review"],
                    caption_review=r["caption_review"],
                    figrefs_review=r["figrefs_review"],
                    source_path=r["source_path"],
                )
                for r in fake_reviews
            ]
            self._webhooks.publish_figure_reviews(FigureReviewsEvent(reviews=review_events))
            logger.info(
                "[FakeRunner %s] Posted figure_reviews webhook with %d reviews",
                self._run_id[:8],
                len(fake_reviews),
            )
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to post figure_reviews webhook", self._run_id[:8]
            )

    def _emit_fake_review(self) -> None:
        """Emit a fake LLM review by storing it in the database and publishing a webhook."""
        summary = "This paper presents a novel approach to the problem with solid experimental validation. The methodology is sound and the results demonstrate clear improvements over baseline approaches."
        strengths = [
            "Novel approach with clear motivation",
            "Comprehensive experimental evaluation",
            "Well-written and easy to follow",
            "Strong empirical results across multiple benchmarks",
        ]
        weaknesses = [
            "Limited comparison with recent state-of-the-art methods",
            "Some experimental details could be clarified",
            "Scalability concerns not fully addressed",
        ]
        questions = [
            "How does the approach scale to larger datasets?",
            "What is the computational overhead compared to baselines?",
        ]
        limitations = [
            "Limited to specific domain",
            "Requires significant computational resources",
        ]
        originality = 3
        quality = 3
        clarity = 4
        significance = 3
        soundness = 3
        presentation = 4
        contribution = 3
        overall = 7
        confidence = 4
        decision = "Accept"
        ethical_concerns = False
        source_path = None
        created_at = datetime.now(timezone.utc)

        # Publish the webhook (server will generate the ID and persist to database)
        webhook_payload = ReviewCompletedEvent(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            originality=originality,
            quality=quality,
            clarity=clarity,
            significance=significance,
            questions=questions,
            limitations=limitations,
            ethical_concerns=ethical_concerns,
            soundness=soundness,
            presentation=presentation,
            contribution=contribution,
            overall=overall,
            confidence=confidence,
            decision=decision,
            source_path=source_path,
            created_at=created_at.isoformat(),
        )

        try:
            self._webhooks.publish_review_completed(webhook_payload)
            logger.info("[FakeRunner %s] Posted review completed webhook", self._run_id[:8])
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to post review completed webhook", self._run_id[:8]
            )

    def _emit_fake_best_node(self, *, stage_name: str, stage_index: int) -> None:
        """Emit a fake best node selection event."""
        node_id = f"{stage_name}-best-{uuid.uuid4().hex[:8]}"
        reasoning = (
            f"Selected synthetic best node for {stage_name} after stage index {stage_index + 1}."
        )
        try:
            self._persistence.queue.put(
                PersistableEvent(
                    kind="best_node_selection",
                    data=BestNodeSelectionEvent(
                        stage=stage_name,
                        node_id=node_id,
                        reasoning=reasoning,
                    ),
                )
            )
        except Exception:
            logger.exception("Failed to enqueue fake best node event for stage %s", stage_name)
