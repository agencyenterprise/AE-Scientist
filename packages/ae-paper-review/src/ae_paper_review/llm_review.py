"""LLM-based paper review functionality."""

import importlib.resources
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, NamedTuple

from .llm.native_pdf import NativePDFProvider, get_provider
from .llm.token_tracking import (
    TokenUsage,
    TokenUsageDetail,
    TokenUsageSummary,
)
from .models import PaperContextExtraction, ReviewResponseModel
from .prompts import render_text
from .semantic_scholar import scan_for_related_papers

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of a paper review including the review and token usage."""

    review: ReviewResponseModel
    token_usage: TokenUsageSummary
    token_usage_detailed: list[TokenUsageDetail]


class AbstractExtractionResult(NamedTuple):
    """Result of abstract extraction from a PDF."""

    abstract: str
    token_usage: TokenUsage


class FewshotExample(NamedTuple):
    """A few-shot example with file_id and review text."""

    file_id: str
    review_text: str


# Pre-render static system prompt
_reviewer_system_prompt_balanced = render_text(
    template_name="llm_review/reviewer_system_prompt_balanced.txt.j2",
    context={},
)


class ReviewProgressEvent:
    """Simple progress event for review callbacks."""

    def __init__(
        self,
        *,
        step: str,
        substep: str,
        progress: float,
        step_progress: float,
    ) -> None:
        self.step = step
        self.substep = substep
        self.progress = progress
        self.step_progress = step_progress

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "substep": self.substep,
            "progress": self.progress,
            "step_progress": self.step_progress,
        }


# =============================================================================
# Orchestrator - unified flow for all providers
# =============================================================================


class ReviewOrchestrator:
    """Orchestrates the paper review process using any provider."""

    def __init__(
        self,
        provider: NativePDFProvider,
        model: str,
        temperature: float,
        event_callback: Callable[[ReviewProgressEvent], None],
        usage: TokenUsage,
    ) -> None:
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._event_callback = event_callback
        self._usage = usage
        self._uploaded_file_ids: list[str] = []

    def run(
        self,
        pdf_path: Path,
        num_reflections: int,
        num_fs_examples: int,
        num_reviews_ensemble: int,
    ) -> ReviewResult:
        """Run the full review process."""
        try:
            # Upload files
            self._emit_progress(
                step="upload",
                substep="Uploading files...",
                progress=0.0,
                step_progress=0.0,
            )

            paper_file_id = self._provider.upload_pdf(pdf_path=pdf_path, filename="paper.pdf")
            self._uploaded_file_ids.append(paper_file_id)

            fewshot_examples = self._upload_fewshot_examples(num_fs_examples=num_fs_examples)

            # Extract context
            self._emit_progress(
                step="context_extraction",
                substep="Extracting paper context...",
                progress=0.02,
                step_progress=0.0,
            )

            extraction = self._provider.structured_chat(
                file_ids=[paper_file_id],
                prompt=render_text(
                    template_name="context_extraction/extract_context.txt.j2",
                    context={},
                ),
                system_message=render_text(
                    template_name="context_extraction/system_prompt.txt.j2",
                    context={},
                ),
                temperature=0.1,
                schema_class=PaperContextExtraction,
                usage=self._usage,
            )

            s2_result = scan_for_related_papers(
                title=extraction.title,
                abstract=extraction.abstract,
                max_results=3,
            )
            context = _format_context(
                related_papers=s2_result.papers,
                s2_message=s2_result.message,
            )

            # Build base prompt
            fewshot_text = _build_fewshot_review_text(fewshot_examples=fewshot_examples)
            base_prompt = render_text(
                template_name="llm_review/review_prompt.txt.j2",
                context={
                    "context": context,
                    "fewshot_examples": fewshot_text,
                },
            )

            # Collect all file_ids for review calls
            all_file_ids = [ex.file_id for ex in fewshot_examples] + [paper_file_id]

            self._emit_progress(
                step="init",
                substep="Starting paper review...",
                progress=0.05,
                step_progress=0.0,
            )

            # Run ensemble reviews or single review
            review = self._run_reviews(
                base_prompt=base_prompt,
                all_file_ids=all_file_ids,
                num_reviews_ensemble=num_reviews_ensemble,
            )

            # Run reflections
            if num_reflections > 0:
                review = self._run_reflections(
                    review=review,
                    all_file_ids=all_file_ids,
                    num_reflections=num_reflections,
                )

            total_usage = self._usage.get_total()
            logger.info(
                "Review complete (decision=%s, overall=%s, input_tokens=%d, output_tokens=%d)",
                review.decision,
                review.overall,
                total_usage.input_tokens,
                total_usage.output_tokens,
            )

            return ReviewResult(
                review=review,
                token_usage=total_usage,
                token_usage_detailed=self._usage.get_detailed(),
            )

        finally:
            self._cleanup()

    def _emit_progress(
        self, step: str, substep: str, progress: float, step_progress: float
    ) -> None:
        """Emit a progress event."""
        self._event_callback(
            ReviewProgressEvent(
                step=step,
                substep=substep,
                progress=progress,
                step_progress=step_progress,
            )
        )

    def _upload_fewshot_examples(self, num_fs_examples: int) -> list[FewshotExample]:
        """Get or upload few-shot example PDFs.

        Uses get_or_upload_fewshot() to cache fewshot files across calls.
        Fewshot file_ids are NOT added to _uploaded_file_ids since they should
        persist and be reused across review sessions.
        """
        if num_fs_examples <= 0:
            return []

        fewshot_files = [
            ("132_automated_relational", "132_automated_relational"),
            ("attention", "attention"),
            ("2_carpe_diem", "2_carpe_diem"),
        ]

        files = importlib.resources.files("ae_paper_review.fewshot_examples")
        examples: list[FewshotExample] = []

        for paper_name, review_name in fewshot_files[:num_fs_examples]:
            pdf_file = files.joinpath(f"{paper_name}.pdf")
            json_file = files.joinpath(f"{review_name}.json")

            with importlib.resources.as_file(pdf_file) as pdf_path:
                file_id = self._provider.get_or_upload_fewshot(
                    pdf_path=pdf_path,
                    filename=f"{paper_name}.pdf",
                )
                # Note: NOT adding to _uploaded_file_ids - fewshot files are persistent

            review_data = json.loads(json_file.read_text())
            review_text = str(review_data["review"])
            examples.append(FewshotExample(file_id=file_id, review_text=review_text))

        logger.info("Loaded %d few-shot examples", len(examples))
        return examples

    def _run_reviews(
        self,
        base_prompt: str,
        all_file_ids: list[str],
        num_reviews_ensemble: int,
    ) -> ReviewResponseModel:
        """Run ensemble reviews or single review."""
        if num_reviews_ensemble > 1:
            review = self._run_ensemble_reviews(
                base_prompt=base_prompt,
                all_file_ids=all_file_ids,
                num_reviews_ensemble=num_reviews_ensemble,
            )
            if review is not None:
                return review

        # Fall back to single review
        logger.info("Running single review")
        return self._provider.structured_chat(
            file_ids=all_file_ids,
            prompt=base_prompt,
            system_message=_reviewer_system_prompt_balanced,
            temperature=self._temperature,
            schema_class=ReviewResponseModel,
            usage=self._usage,
        )

    def _run_ensemble_reviews(
        self,
        base_prompt: str,
        all_file_ids: list[str],
        num_reviews_ensemble: int,
    ) -> ReviewResponseModel | None:
        """Run ensemble reviews and aggregate."""
        logger.info("Running ensemble reviews (%d reviews)", num_reviews_ensemble)
        parsed_reviews: List[ReviewResponseModel] = []

        for idx in range(num_reviews_ensemble):
            try:
                step_progress = idx / num_reviews_ensemble
                self._emit_progress(
                    step="ensemble",
                    substep=f"Review {idx + 1} of {num_reviews_ensemble}",
                    progress=0.05 + 0.65 * step_progress,
                    step_progress=step_progress,
                )

                parsed = self._provider.structured_chat(
                    file_ids=all_file_ids,
                    prompt=base_prompt,
                    system_message=_reviewer_system_prompt_balanced,
                    temperature=self._temperature,
                    schema_class=ReviewResponseModel,
                    usage=self._usage,
                )
                parsed_reviews.append(parsed)
            except Exception as exc:
                logger.warning(
                    "Ensemble review %d/%d failed: %s",
                    idx + 1,
                    num_reviews_ensemble,
                    exc,
                )

        if not parsed_reviews:
            return None

        self._emit_progress(
            step="meta_review",
            substep="Generating meta-review...",
            progress=0.70,
            step_progress=0.0,
        )

        review = _get_meta_review(
            provider=self._provider,
            temperature=self._temperature,
            reviews=parsed_reviews,
            usage=self._usage,
        )
        if review is None:
            return parsed_reviews[0]

        _average_ensemble_scores(review=review, parsed_reviews=parsed_reviews)
        return review

    def _run_reflections(
        self,
        review: ReviewResponseModel,
        all_file_ids: list[str],
        num_reflections: int,
    ) -> ReviewResponseModel:
        """Run reflection rounds.

        Args:
            review: Initial review to reflect on
            all_file_ids: File IDs for the paper and fewshot examples
            num_reflections: Number of reflection rounds (0 = none, 1 = one round, etc.)
        """
        for reflection_round in range(num_reflections):
            step_progress = reflection_round / num_reflections
            self._emit_progress(
                step="reflection",
                substep=f"Reflection {reflection_round + 1} of {num_reflections}",
                progress=0.85 + 0.15 * step_progress,
                step_progress=step_progress,
            )

            reflection_prompt = render_text(
                template_name="llm_review/reflection_prompt.txt.j2",
                context={
                    "current_round": reflection_round + 1,
                    "num_reflections": num_reflections,
                },
            )

            full_prompt = (
                f"Previous review:\n```json\n{json.dumps(review.model_dump(by_alias=True), indent=2)}\n```\n\n"
                f"{reflection_prompt}"
            )

            review = self._provider.structured_chat(
                file_ids=all_file_ids,
                prompt=full_prompt,
                system_message=_reviewer_system_prompt_balanced,
                temperature=self._temperature,
                schema_class=ReviewResponseModel,
                usage=self._usage,
            )

            if not review.should_continue:
                break

        return review

    def _cleanup(self) -> None:
        """Delete all uploaded files."""
        for file_id in self._uploaded_file_ids:
            try:
                self._provider.delete_file(file_id=file_id)
            except Exception as exc:
                logger.warning("Failed to delete file %s: %s", file_id, exc)


# =============================================================================
# Common utilities
# =============================================================================


def _build_fewshot_review_text(fewshot_examples: list[FewshotExample]) -> str:
    """Build few-shot review text (without paper content - that's in the PDFs)."""
    if not fewshot_examples:
        return ""

    intro = render_text(
        template_name="llm_review/fewshot_intro.txt.j2",
        context={},
    )

    parts = [intro]
    for idx, example in enumerate(fewshot_examples, start=1):
        ordinal = _ordinal(idx)
        parts.append(
            f"\nExample {idx} (see {ordinal} PDF document):\n"
            f"Review:\n```\n{example.review_text}\n```\n"
        )

    return "\n".join(parts)


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_context(
    related_papers: list,  # type: ignore[type-arg]
    s2_message: str | None,
) -> str:
    """Format Semantic Scholar results into a string for the review prompt."""
    if related_papers:
        lines = ["Novelty Scan (Related Papers):"]
        for paper in related_papers:
            year_str = str(paper.year) if paper.year else "unknown year"
            lines.append(
                f"- {paper.title} ({year_str}, {paper.venue}) — "
                f"citations: {paper.citation_count}; authors: {paper.authors}; "
                f"abstract: {paper.abstract_snippet}"
            )
        return "\n".join(lines)
    elif s2_message:
        return f"Novelty Scan:\n{s2_message}"
    return ""


def _average_ensemble_scores(
    review: ReviewResponseModel,
    parsed_reviews: list[ReviewResponseModel],
) -> None:
    """Average scores from ensemble reviews into the review."""
    parsed_dicts = [parsed.model_dump() for parsed in parsed_reviews]
    for score, limits in [
        ("Originality", (1, 4)),
        ("Quality", (1, 4)),
        ("Clarity", (1, 4)),
        ("Significance", (1, 4)),
        ("Soundness", (1, 4)),
        ("Presentation", (1, 4)),
        ("Contribution", (1, 4)),
        ("Overall", (1, 10)),
        ("Confidence", (1, 5)),
    ]:
        collected: List[float] = []
        for parsed_dict in parsed_dicts:
            value = parsed_dict.get(score)
            if isinstance(value, (int, float)) and limits[0] <= value <= limits[1]:
                collected.append(float(value))
        if collected:
            mean_value = round(sum(collected) / len(collected), 2)
            setattr(review, score, float(mean_value))


def _get_meta_review(
    provider: NativePDFProvider,
    temperature: float,
    reviews: list[ReviewResponseModel],
    usage: TokenUsage,
) -> ReviewResponseModel | None:
    """Aggregate multiple reviews into a meta-review."""
    review_json_strings = [json.dumps(r.model_dump(by_alias=True)) for r in reviews]
    base_prompt = render_text(
        template_name="llm_review/meta_review_prompt.txt.j2",
        context={"reviews": review_json_strings},
    )
    system_message = render_text(
        template_name="llm_review/meta_reviewer_system_prompt.txt.j2",
        context={"reviewer_count": len(reviews)},
    )
    try:
        # Meta-review doesn't need PDF files, just aggregate text reviews
        return provider.structured_chat(
            file_ids=[],
            prompt=base_prompt,
            system_message=system_message,
            temperature=temperature,
            schema_class=ReviewResponseModel,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to generate meta-review.")
        return None


# =============================================================================
# Main entry point
# =============================================================================


def perform_review(
    pdf_path: Path,
    *,
    model: str,
    temperature: float,
    event_callback: Callable[[ReviewProgressEvent], None],
    num_reflections: int,
    num_fs_examples: int,
    num_reviews_ensemble: int,
) -> ReviewResult:
    """Perform a paper review using LLM.

    Args:
        pdf_path: Path to the PDF file to review
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-5")
        temperature: Sampling temperature
        event_callback: Callback for progress events
        num_reflections: Number of reflection rounds
        num_fs_examples: Number of few-shot examples to include
        num_reviews_ensemble: Number of ensemble reviews

    Returns:
        ReviewResult containing the review and token usage
    """
    logger.info(
        "Starting paper review (model=%s, ensemble=%d, reflections=%d)",
        model,
        num_reviews_ensemble,
        num_reflections,
    )

    provider = get_provider(model=model)
    usage = TokenUsage()

    orchestrator = ReviewOrchestrator(
        provider=provider,
        model=model,
        temperature=temperature,
        event_callback=event_callback,
        usage=usage,
    )

    return orchestrator.run(
        pdf_path=pdf_path,
        num_reflections=num_reflections,
        num_fs_examples=num_fs_examples,
        num_reviews_ensemble=num_reviews_ensemble,
    )


def extract_abstract_from_pdf(
    pdf_path: Path,
    model: str,
) -> AbstractExtractionResult:
    """Extract abstract from a PDF using native PDF provider.

    Uses LLM-based extraction instead of regex parsing for more reliable results.

    Args:
        pdf_path: Path to the PDF file
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-5")

    Returns:
        AbstractExtractionResult containing the abstract and token usage
    """
    provider = get_provider(model=model)
    usage = TokenUsage()

    try:
        file_id = provider.upload_pdf(pdf_path=pdf_path, filename="paper.pdf")

        try:
            extraction = provider.structured_chat(
                file_ids=[file_id],
                prompt=render_text(
                    template_name="context_extraction/extract_context.txt.j2",
                    context={},
                ),
                system_message=render_text(
                    template_name="context_extraction/system_prompt.txt.j2",
                    context={},
                ),
                temperature=0.1,
                schema_class=PaperContextExtraction,
                usage=usage,
            )
            return AbstractExtractionResult(
                abstract=extraction.abstract or "",
                token_usage=usage,
            )
        finally:
            try:
                provider.delete_file(file_id=file_id)
            except Exception as exc:
                logger.warning("Failed to delete file %s: %s", file_id, exc)

    except Exception as exc:
        logger.warning("Failed to extract abstract from PDF: %s", exc)
        return AbstractExtractionResult(abstract="", token_usage=usage)
