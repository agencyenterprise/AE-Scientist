"""Baseline LLM-based paper review (pre-prompt-tuning).

This module implements the review pipeline from before prompt tuning (commit 553991f).
It does NOT include the missing_references or presentation_check steps that were
added during prompt tuning.
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from ..llm import (
    LLMProvider,
    Provider,
    TokenUsage,
    get_provider,
)
from ..llm_review import ReviewProgressEvent, ReviewResult
from ..models import (
    CitationCheckResults,
    Conference,
    NoveltySearchResults,
)
from ..prompts import render_text as render_shared_text
from .models import (
    BaselineICLRReviewModel,
    BaselineICMLReviewModel,
    BaselineNeurIPSReviewModel,
    BaselineReviewModel,
)
from .prompts import render_text as render_baseline_text

# Type alias for baseline schema classes
_BaselineSchemaClass = (
    type[BaselineNeurIPSReviewModel] | type[BaselineICLRReviewModel] | type[BaselineICMLReviewModel]
)

# Mapping from Conference to baseline rubric template name
_CONFERENCE_RUBRIC_TEMPLATES: dict[Conference, str] = {
    Conference.ICLR_2025: "llm_review/iclr_form.md.j2",
    Conference.NEURIPS_2025: "llm_review/neurips_form.md.j2",
    Conference.ICML: "llm_review/icml_form.md.j2",
}

# Mapping from Conference to baseline schema class
_CONFERENCE_SCHEMAS: dict[Conference, _BaselineSchemaClass] = {
    Conference.ICLR_2025: BaselineICLRReviewModel,
    Conference.NEURIPS_2025: BaselineNeurIPSReviewModel,
    Conference.ICML: BaselineICMLReviewModel,
}

# Conferences whose rubrics mention reproducibility criteria,
# enabling web search during the review step.
_REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY: list[Conference] = [Conference.NEURIPS_2025]

_REVIEW_MAX_WEB_SEARCHES = 3

logger = logging.getLogger(__name__)


class BaselineReviewOrchestrator:
    """Orchestrates the baseline paper review process (pre-prompt-tuning).

    Uses baseline prompts and models without missing_references or presentation_check steps.
    """

    def __init__(
        self,
        provider_instance: LLMProvider,
        temperature: float,
        event_callback: Callable[[ReviewProgressEvent], None],
        usage: TokenUsage,
        conference: Conference,
        provide_rubric: bool,
        skip_novelty_search: bool,
        skip_citation_check: bool,
        is_vanilla_prompt: bool,
    ) -> None:
        self._provider = provider_instance
        self._temperature = temperature
        self._event_callback = event_callback
        self._usage = usage
        self._conference = conference
        self._provide_rubric = provide_rubric
        self._skip_novelty_search = skip_novelty_search
        self._skip_citation_check = skip_citation_check
        self._uploaded_file_ids: list[str] = []

        if is_vanilla_prompt:
            system_template = "llm_review/reviewer_system_prompt_vanilla.txt.j2"
            self._review_prompt_template = "llm_review/review_prompt_vanilla.txt.j2"
        else:
            system_template = "llm_review/reviewer_system_prompt_balanced.txt.j2"
            self._review_prompt_template = "llm_review/review_prompt.txt.j2"

        self._system_prompt = render_baseline_text(
            template_name=system_template,
            context={
                "conference_rubric": conference.value,
            },
        )
        self._schema_class: _BaselineSchemaClass = _CONFERENCE_SCHEMAS[conference]

    def run(
        self,
        pdf_path: Path,
        num_reflections: int,
    ) -> ReviewResult:
        """Run the full baseline review process."""
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

            # Novelty search via web search
            if self._skip_novelty_search:
                novelty_results = None
            else:
                self._emit_progress(
                    step="novelty_search",
                    substep="Searching for related work...",
                    progress=0.02,
                    step_progress=0.0,
                )

                novelty_results = self._provider.web_search_chat(
                    file_ids=[paper_file_id],
                    prompt=render_shared_text(
                        template_name="novelty_search/search_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_shared_text(
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
                    progress=0.03,
                    step_progress=0.0,
                )

                citation_check_results = self._provider.web_search_chat(
                    file_ids=[paper_file_id],
                    prompt=render_shared_text(
                        template_name="citation_check/search_prompt.txt.j2",
                        context={},
                    ),
                    system_message=render_shared_text(
                        template_name="citation_check/system_prompt.txt.j2",
                        context={},
                    ),
                    temperature=0.1,
                    schema_class=CitationCheckResults,
                    max_searches=5,
                )

            # Build base prompt (baseline uses baseline render for llm_review templates)
            rubric_template = (
                _CONFERENCE_RUBRIC_TEMPLATES[self._conference] if self._provide_rubric else None
            )
            prompt_context: dict[str, Any] = {
                "novelty_results": novelty_results,
                "citation_check_results": citation_check_results,
                "rubric_template": rubric_template,
                "conference_rubric": self._conference.value,
            }

            base_prompt = render_baseline_text(
                template_name=self._review_prompt_template,
                context=prompt_context,
            )

            # File IDs for review calls
            all_file_ids = [paper_file_id]

            self._emit_progress(
                step="init",
                substep="Starting paper review...",
                progress=0.05,
                step_progress=0.0,
            )

            # Run single review
            logger.info("Running baseline single review")
            review: BaselineReviewModel = self._review_chat(
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
                "Baseline review complete (input_tokens=%d, output_tokens=%d)",
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

    def _review_chat(
        self,
        file_ids: list[str],
        prompt: str,
    ) -> BaselineReviewModel:
        """Make a review chat call, using web search if the conference mentions reproducibility."""
        schema_class = self._schema_class
        if self._conference in _REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY:
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
        return result

    def _run_reflections(
        self,
        review: BaselineReviewModel,
        all_file_ids: list[str],
        num_reflections: int,
        base_prompt: str,
    ) -> BaselineReviewModel:
        """Run reflection rounds."""
        for reflection_round in range(num_reflections):
            step_progress = reflection_round / num_reflections
            self._emit_progress(
                step="reflection",
                substep=f"Reflection {reflection_round + 1} of {num_reflections}",
                progress=0.85 + 0.15 * step_progress,
                step_progress=step_progress,
            )

            reflection_prompt = render_baseline_text(
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


def perform_baseline_review(
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
    is_vanilla_prompt: bool,
) -> ReviewResult:
    """Perform a baseline paper review (pre-prompt-tuning) using LLM.

    Uses the original prompts and models from before prompt tuning.
    Does not include missing_references or presentation_check pipeline steps.

    Args:
        pdf_path: Path to the PDF file to review
        provider: The LLM provider to use
        model: Model name (e.g., "gpt-5.2")
        temperature: Sampling temperature
        event_callback: Callback for progress events
        num_reflections: Number of reflection rounds
        conference: Conference to use for schema and system prompt
        provide_rubric: Whether to include detailed rubric form instructions
        skip_novelty_search: Whether to skip the novelty web search phase
        skip_citation_check: Whether to skip the citation verification phase
        is_vanilla_prompt: Whether to use the minimal vanilla prompt

    Returns:
        ReviewResult containing the review and token usage
    """
    logger.info(
        "Starting baseline paper review (provider=%s, model=%s, reflections=%d, conference=%s, rubric=%s, vanilla=%s)",
        provider.value,
        model,
        num_reflections,
        conference.value,
        provide_rubric,
        is_vanilla_prompt,
    )

    usage = TokenUsage()
    llm_provider = get_provider(provider=provider, model=model, usage=usage)

    orchestrator = BaselineReviewOrchestrator(
        provider_instance=llm_provider,
        temperature=temperature,
        event_callback=event_callback,
        usage=usage,
        conference=conference,
        provide_rubric=provide_rubric,
        skip_novelty_search=skip_novelty_search,
        skip_citation_check=skip_citation_check,
        is_vanilla_prompt=is_vanilla_prompt,
    )

    return orchestrator.run(
        pdf_path=pdf_path,
        num_reflections=num_reflections,
    )
