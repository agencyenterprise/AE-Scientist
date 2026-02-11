"""Fake data generation methods for FakeRunner."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

# fmt: off
# isort: off
from research_pipeline.ai_scientist.api_types import (  # type: ignore[import-not-found]
    FigureReviewEvent,
    FigureReviewsEvent,
    ReviewCompletedEvent,
    TokenUsageEvent,
)
# isort: on
# fmt: on

if TYPE_CHECKING:
    from .core import FakeRunnerCore

logger = logging.getLogger(__name__)


def get_paper_generation_steps() -> list[tuple[str, list[str], dict[str, object]]]:
    """Return the fake paper generation steps with substeps and details.

    Returns a list of tuples: (step_name, substeps, step_details)
    """
    return [
        (
            "plot_aggregation",
            ["collecting_figures", "validating_plots", "generating_captions"],
            {"figures_collected": 8, "valid_plots": 7},
        ),
        (
            "citation_gathering",
            ["searching_literature", "filtering_relevant", "formatting_citations"],
            {"citations_found": 15, "relevant_citations": 12},
        ),
        (
            "paper_writeup",
            [
                "writing_abstract",
                "writing_introduction",
                "writing_methodology",
                "writing_results",
                "writing_discussion",
                "writing_conclusion",
            ],
            {"sections_completed": 6, "word_count": 4500},
        ),
        (
            "paper_review",
            ["review_1", "review_2", "review_3"],
            {
                "avg_score": 7.2,
                "review_scores": [7.0, 7.5, 7.1],
                "strengths": ["novel approach", "thorough experiments"],
                "weaknesses": ["limited comparison", "minor clarity issues"],
            },
        ),
    ]


def generate_seed_modification_task(seed_value: int) -> str:
    """Generate a fake seed modification task prompt for testing.

    This mirrors the format of the actual seed modification task template
    used by the research pipeline.
    """
    return f"""# Seed Modification Task

**Your ONLY job is to change the random seed value in the code and run it.**

## Target Seed Value
**NEW_SEED = {seed_value}**

## Instructions
1. Find ALL places in the code where random seeds are set:
   - `SEED = ...` or `seed = ...` variable assignments
   - `random.seed(...)`
   - `np.random.seed(...)`
   - `torch.manual_seed(...)`
   - `torch.cuda.manual_seed(...)` / `torch.cuda.manual_seed_all(...)`
2. Change ALL seed values to **{seed_value}**
3. Write the modified code to `run.py`
4. Run: `/workspace/.venv/bin/python run.py`

## Do NOT change anything else
- Do not change any logic, algorithms, or model architecture
- Do not change where results are saved (must remain `./working/experiment_data.npy`)
- Do not change plot output locations (must remain `./working/*.png`)
- Do not modify hyperparameters (except seeds)

## Base Code
```python
import random
import numpy as np
import torch

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# ... experiment code ...
```
"""


def generate_seed_runfile_code(seed_value: int) -> str:
    """Generate fake generated Python code for a seed run.

    This simulates the code that Codex would generate after modifying
    the seed values in the original experiment code.
    """
    return f"""import os

working_dir = os.path.join(os.getcwd(), "working")
os.makedirs(working_dir, exist_ok=True)

import random
import numpy as np
import torch

# Seed modified by Codex to: {seed_value}
SEED = {seed_value}
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

# ... experiment code with seed {seed_value} ...

# Save results
np.save(os.path.join(working_dir, "experiment_data.npy"), {{"seed": SEED, "results": [0.85, 0.87, 0.86]}})
print(f"Experiment completed with seed {{SEED}}")
"""


class FakeDataMixin:
    """Mixin providing fake data generation methods for FakeRunner."""

    # Type hints for methods/attributes from FakeRunnerCore
    _run_id: str
    _webhook_client: Any
    _webhooks: "FakeRunnerCore._webhooks"  # type: ignore[name-defined]
    _persistence: "FakeRunnerCore._persistence"  # type: ignore[name-defined]

    def _emit_fake_token_usage(self) -> None:
        """Emit final token usage summary events at the end of the run.

        Note: Intermediate token usage events are now emitted during each
        stage iteration via _emit_iteration_token_usage and _emit_seed_token_usage
        in the EventsMixin. This method emits summary/final token usage for
        paper generation and review phases.
        """
        # Emit token usage for paper generation phase
        paper_gen_stages = [
            ("paper_writeup", 25000, 15000, 8000),
            ("citation_gathering", 8000, 5000, 2000),
            ("paper_review", 12000, 8000, 3000),
        ]
        for stage_name, input_tokens, cached_tokens, output_tokens in paper_gen_stages:
            payload = TokenUsageEvent(
                model="openai:gpt-5.2",
                input_tokens=input_tokens,
                cached_input_tokens=cached_tokens,
                output_tokens=output_tokens,
            )
            try:
                self._webhooks.publish_token_usage(payload)
            except Exception:
                logger.exception(
                    "[FakeRunner %s] Failed to publish token_usage for %s",
                    self._run_id[:8],
                    stage_name,
                )
        logger.info(
            "[FakeRunner %s] Posted final token_usage webhooks for %d paper generation stages",
            self._run_id[:8],
            len(paper_gen_stages),
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
