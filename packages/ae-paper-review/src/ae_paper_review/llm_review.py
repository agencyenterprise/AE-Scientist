"""LLM-based paper review functionality."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .llm import (
    LLMProvider,
    Provider,
    TokenUsage,
    TokenUsageDetail,
    TokenUsageSummary,
    get_provider,
)
from .models import (
    CitationCheckResults,
    Conference,
    ICLRReviewModel,
    ICMLReviewModel,
    MissingReferencesResults,
    NeurIPSReviewModel,
    NoveltySearchResults,
    PresentationCheckResults,
    ReviewModel,
)
from .prompts import render_text

# Type alias for schema classes
_SchemaClass = type[NeurIPSReviewModel] | type[ICLRReviewModel] | type[ICMLReviewModel]

# Mapping from Conference to rubric template name
_CONFERENCE_RUBRIC_TEMPLATES: dict[Conference, str] = {
    Conference.ICLR_2025: "llm_review/iclr_form.md.j2",
    Conference.NEURIPS_2025: "llm_review/neurips_form.md.j2",
    Conference.ICML: "llm_review/icml_form.md.j2",
}

# Mapping from Conference to schema class
_CONFERENCE_SCHEMAS: dict[Conference, _SchemaClass] = {
    Conference.ICLR_2025: ICLRReviewModel,
    Conference.NEURIPS_2025: NeurIPSReviewModel,
    Conference.ICML: ICMLReviewModel,
}

# Conferences whose rubrics mention reproducibility criteria,
# enabling web search during the review step.
REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY: list[Conference] = [Conference.NEURIPS_2025]

_REVIEW_MAX_WEB_SEARCHES = 3

logger = logging.getLogger(__name__)

# Progress milestones tuned for current standalone review flow.
# We assume num_reflections=1 in production, so most wall-clock time sits in the
# pre-review analysis stages and the main review call.
_PROGRESS_UPLOAD_START = 0.0
_PROGRESS_NOVELTY_START = 0.01
_PROGRESS_CITATION_START = 0.28
_PROGRESS_MISSING_REFERENCES_START = 0.52
_PROGRESS_PRESENTATION_START = 0.73
_PROGRESS_REVIEW_START = 0.84
_PROGRESS_REFLECTION_START = 0.95
_PROGRESS_COMPLETE = 1.0


@dataclass
class ReviewResult:
    """Result of a paper review including the review and token usage."""

    review: ReviewModel
    token_usage: TokenUsageSummary
    token_usage_detailed: list[TokenUsageDetail]


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
        provider: LLMProvider,
        model: str,
        temperature: float,
        event_callback: Callable[[ReviewProgressEvent], None],
        usage: TokenUsage,
        conference: Conference,
        provide_rubric: bool,
        skip_novelty_search: bool,
        skip_citation_check: bool,
        skip_missing_references: bool,
        skip_presentation_check: bool,
        is_vanilla_prompt: bool,
    ) -> None:
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._event_callback = event_callback
        self._usage = usage
        self._conference = conference
        self._provide_rubric = provide_rubric
        self._skip_novelty_search = skip_novelty_search
        self._skip_citation_check = skip_citation_check
        self._skip_missing_references = skip_missing_references
        self._skip_presentation_check = skip_presentation_check
        self._uploaded_file_ids: list[str] = []

        if is_vanilla_prompt:
            system_template = "llm_review/reviewer_system_prompt_vanilla.txt.j2"
            self._review_prompt_template = "llm_review/review_prompt_vanilla.txt.j2"
        else:
            system_template = "llm_review/reviewer_system_prompt_balanced.txt.j2"
            self._review_prompt_template = "llm_review/review_prompt.txt.j2"

        self._system_prompt = render_text(
            template_name=system_template,
            context={
                "conference_rubric": conference.value,
            },
        )
        self._schema_class: _SchemaClass = _CONFERENCE_SCHEMAS[conference]

    def run(
        self,
        pdf_path: Path,
        num_reflections: int,
    ) -> ReviewResult:
        """Run the full review process."""
        try:
            # Upload files
            self._emit_progress(
                step="upload",
                substep="Uploading files...",
                progress=_PROGRESS_UPLOAD_START,
                step_progress=0.0,
            )

            paper_file_id = self._provider.upload_pdf(pdf_path=pdf_path, filename="paper.pdf")
            self._uploaded_file_ids.append(paper_file_id)

            # Novelty search via web search
            if self._skip_novelty_search:
                novelty_results = None
            else:
                self._emit_progress(
                    step="novelty_search",
                    substep="Searching for related work...",
                    progress=_PROGRESS_NOVELTY_START,
                    step_progress=0.0,
                )

                novelty_results = self._provider.web_search_chat(
                    file_ids=[paper_file_id],
                    prompt=render_text(
                        template_name="novelty_search/search_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_text(
                        template_name="novelty_search/system_prompt.txt.j2",
                        context={},
                    ),
                    temperature=0.1,
                    schema_class=NoveltySearchResults,
                    max_searches=5,
                )

            # Citation verification via web search
            if self._skip_citation_check:
                citation_check_results = None
            else:
                self._emit_progress(
                    step="citation_check",
                    substep="Verifying key citations...",
                    progress=_PROGRESS_CITATION_START,
                    step_progress=0.0,
                )

                citation_check_results = self._provider.web_search_chat(
                    file_ids=[paper_file_id],
                    prompt=render_text(
                        template_name="citation_check/search_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_text(
                        template_name="citation_check/system_prompt.txt.j2",
                        context={},
                    ),
                    temperature=0.1,
                    schema_class=CitationCheckResults,
                    max_searches=5,
                )

            # Missing references search via web search
            if self._skip_missing_references:
                missing_references_results = None
            else:
                self._emit_progress(
                    step="missing_references",
                    substep="Searching for missing references...",
                    progress=_PROGRESS_MISSING_REFERENCES_START,
                    step_progress=0.0,
                )

                missing_references_results = self._provider.web_search_chat(
                    file_ids=[paper_file_id],
                    prompt=render_text(
                        template_name="missing_references/search_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_text(
                        template_name="missing_references/system_prompt.txt.j2",
                        context={},
                    ),
                    temperature=0.1,
                    schema_class=MissingReferencesResults,
                    max_searches=5,
                )

            # Presentation check via structured LLM call
            if self._skip_presentation_check:
                presentation_check_results = None
            else:
                self._emit_progress(
                    step="presentation_check",
                    substep="Inspecting figures, tables, and notation...",
                    progress=_PROGRESS_PRESENTATION_START,
                    step_progress=0.0,
                )

                presentation_check_results = self._provider.structured_chat(
                    file_ids=[paper_file_id],
                    prompt=render_text(
                        template_name="presentation_check/check_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_text(
                        template_name="presentation_check/system_prompt.txt.j2",
                        context={},
                    ),
                    temperature=0.1,
                    schema_class=PresentationCheckResults,
                )

            # Build base prompt
            rubric_template = (
                _CONFERENCE_RUBRIC_TEMPLATES[self._conference] if self._provide_rubric else None
            )
            prompt_context: dict[str, Any] = {
                "novelty_results": novelty_results,
                "citation_check_results": citation_check_results,
                "missing_references_results": missing_references_results,
                "presentation_check_results": presentation_check_results,
                "rubric_template": rubric_template,
                "conference_rubric": self._conference.value,
            }

            base_prompt = render_text(
                template_name=self._review_prompt_template,
                context=prompt_context,
            )

            # File IDs for review calls
            all_file_ids = [paper_file_id]

            self._emit_progress(
                step="init",
                substep="Synthesizing findings and drafting final review...",
                progress=_PROGRESS_REVIEW_START,
                step_progress=0.0,
            )

            # Run single review
            logger.info("Running single review")
            review: ReviewModel = self._review_chat(
                file_ids=all_file_ids,
                prompt=base_prompt,
            )

            # Run reflections
            if num_reflections > 0:
                review = self._run_reflections(
                    review=review,
                    all_file_ids=all_file_ids,
                    num_reflections=num_reflections,
                    base_prompt=base_prompt,
                )

            total_usage = self._usage.get_total()
            logger.info(
                "Review complete (input_tokens=%d, cached=%d, cache_write=%d, output_tokens=%d)",
                total_usage.input_tokens,
                total_usage.cached_input_tokens,
                total_usage.cache_write_input_tokens,
                total_usage.output_tokens,
            )
            self._emit_progress(
                step="complete",
                substep="Review complete.",
                progress=_PROGRESS_COMPLETE,
                step_progress=1.0,
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

    def _review_chat(
        self,
        file_ids: list[str],
        prompt: str,
    ) -> ReviewModel:
        """Make a review chat call, using web search if the conference mentions reproducibility."""
        schema_class = self._schema_class
        if self._conference in REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY:
            result = self._provider.web_search_chat(
                file_ids=file_ids,
                prompt=prompt,
                system_message=self._system_prompt,
                temperature=self._temperature,
                schema_class=schema_class,
                max_searches=_REVIEW_MAX_WEB_SEARCHES,
            )
        else:
            result = self._provider.structured_chat(
                file_ids=file_ids,
                prompt=prompt,
                system_message=self._system_prompt,
                temperature=self._temperature,
                schema_class=schema_class,
            )
        assert isinstance(result, (NeurIPSReviewModel, ICLRReviewModel, ICMLReviewModel))
        return result

    def _run_reflections(
        self,
        review: ReviewModel,
        all_file_ids: list[str],
        num_reflections: int,
        base_prompt: str,
    ) -> ReviewModel:
        """Run reflection rounds.

        Args:
            review: Initial review to reflect on
            all_file_ids: File IDs for the paper
            num_reflections: Number of reflection rounds (0 = none, 1 = one round, etc.)
            base_prompt: Original review prompt (rubric + novelty context)
        """
        for reflection_round in range(num_reflections):
            step_progress_start = reflection_round / num_reflections
            self._emit_progress(
                step="reflection",
                substep=f"Reflection {reflection_round + 1} of {num_reflections}",
                progress=_PROGRESS_REFLECTION_START,
                step_progress=step_progress_start,
            )

            reflection_prompt = render_text(
                template_name="llm_review/reflection_prompt.txt.j2",
                context={
                    "current_round": reflection_round + 1,
                    "num_reflections": num_reflections,
                },
            )

            review_json = json.dumps(review.model_dump(by_alias=True), indent=2)
            full_prompt = (
                f"{base_prompt}\n\n"
                f"Previous review:\n```json\n{review_json}\n```\n\n"
                f"{reflection_prompt}"
            )

            review = self._review_chat(
                file_ids=all_file_ids,
                prompt=full_prompt,
            )
            step_progress_end = (reflection_round + 1) / num_reflections
            self._emit_progress(
                step="reflection",
                substep=f"Completed reflection {reflection_round + 1} of {num_reflections}",
                progress=_PROGRESS_REFLECTION_START
                + (_PROGRESS_COMPLETE - _PROGRESS_REFLECTION_START) * step_progress_end,
                step_progress=step_progress_end,
            )

        return review

    def _cleanup(self) -> None:
        """Delete all uploaded files."""
        for file_id in self._uploaded_file_ids:
            try:
                self._provider.delete_file(file_id=file_id)
            except Exception as exc:
                logger.warning("Failed to delete file %s: %s", file_id, exc)


# =============================================================================
# Main entry point
# =============================================================================


def perform_review(
    pdf_path: Path,
    *,
    provider: Provider,
    model: str,
    temperature: float,
    event_callback: Callable[[ReviewProgressEvent], None],
    num_reflections: int,
    conference: Conference,
    provide_rubric: bool,
    skip_novelty_search: bool,
    skip_citation_check: bool,
    skip_missing_references: bool,
    skip_presentation_check: bool,
    is_vanilla_prompt: bool,
) -> ReviewResult:
    """Perform a paper review using LLM.

    Args:
        pdf_path: Path to the PDF file to review
        provider: The LLM provider to use
        model: Model name (e.g., "claude-sonnet-4-20250514")
        temperature: Sampling temperature
        event_callback: Callback for progress events
        num_reflections: Number of reflection rounds
        conference: Conference to use for schema and system prompt
        provide_rubric: Whether to include detailed rubric form instructions
        skip_novelty_search: Whether to skip the novelty web search phase
        skip_citation_check: Whether to skip the citation verification phase
        skip_missing_references: Whether to skip the missing references search phase
        skip_presentation_check: Whether to skip the presentation check phase
        is_vanilla_prompt: Whether to use the minimal vanilla prompt

    Returns:
        ReviewResult containing the review and token usage
    """
    logger.info(
        "Starting paper review (provider=%s, model=%s, reflections=%d, conference=%s, rubric=%s, vanilla=%s)",
        provider.value,
        model,
        num_reflections,
        conference.value,
        provide_rubric,
        is_vanilla_prompt,
    )

    usage = TokenUsage()
    llm_provider = get_provider(provider=provider, model=model, usage=usage)

    orchestrator = ReviewOrchestrator(
        provider=llm_provider,
        model=model,
        temperature=temperature,
        event_callback=event_callback,
        usage=usage,
        conference=conference,
        provide_rubric=provide_rubric,
        skip_novelty_search=skip_novelty_search,
        skip_citation_check=skip_citation_check,
        skip_missing_references=skip_missing_references,
        skip_presentation_check=skip_presentation_check,
        is_vanilla_prompt=is_vanilla_prompt,
    )

    return orchestrator.run(
        pdf_path=pdf_path,
        num_reflections=num_reflections,
    )
