"""LLM-based paper review functionality."""

import importlib.resources
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, List

from langchain_core.messages import AIMessage, BaseMessage

from .llm.llm import get_structured_response_from_llm
from .llm.token_tracking import TokenUsage, TokenUsageDetail, TokenUsageSummary
from .models import ReviewResponseModel
from .pdf_loader import load_paper
from .prompts import render_text

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of a paper review including the review and token usage."""

    review: ReviewResponseModel
    token_usage: TokenUsageSummary
    token_usage_detailed: list[TokenUsageDetail]


# Pre-render static system prompt
_reviewer_system_prompt_balanced = render_text(
    template_name="llm_review/reviewer_system_prompt_balanced.txt.j2",
    context={},
)


def _invoke_review_prompt(
    prompt_text: str,
    model: str,
    temperature: float,
    usage: TokenUsage,
    history: list[BaseMessage] | None,
    system_msg: str,
) -> tuple[ReviewResponseModel, list[BaseMessage]]:
    """Invoke LLM to generate a review response."""
    response_dict, updated_history = get_structured_response_from_llm(
        prompt=prompt_text,
        model=model,
        system_message=system_msg,
        temperature=temperature,
        schema_class=ReviewResponseModel,
        msg_history=history,
        usage=usage,
    )
    review_model = ReviewResponseModel.model_validate(response_dict)
    return review_model, updated_history


@dataclass
class _EnsembleResult:
    """Result of ensemble review step."""

    review: ReviewResponseModel
    msg_history: list[BaseMessage]


def _run_ensemble_reviews(
    base_prompt: str,
    model: str,
    temperature: float,
    usage: TokenUsage,
    num_reviews_ensemble: int,
    event_callback: Callable[["ReviewProgressEvent"], None],
) -> _EnsembleResult | None:
    """Run ensemble reviews and generate meta-review.

    Args:
        base_prompt: The base review prompt
        model: Model in "provider:model" format
        temperature: Sampling temperature
        usage: Token usage accumulator
        num_reviews_ensemble: Number of ensemble reviews to generate
        event_callback: Callback for progress events

    Returns:
        EnsembleResult with aggregated review and history, or None if all reviews failed
    """
    logger.info("Running ensemble reviews (%d reviews)", num_reviews_ensemble)
    parsed_reviews: List[ReviewResponseModel] = []
    histories: List[list[BaseMessage]] = []

    for idx in range(num_reviews_ensemble):
        try:
            step_progress = idx / num_reviews_ensemble
            event_callback(
                ReviewProgressEvent(
                    step="ensemble",
                    substep=f"Review {idx + 1} of {num_reviews_ensemble}",
                    progress=0.10 + 0.60 * step_progress,
                    step_progress=step_progress,
                )
            )

            logger.info("Generating ensemble review %d/%d", idx + 1, num_reviews_ensemble)
            parsed, history = _invoke_review_prompt(
                prompt_text=base_prompt,
                model=model,
                temperature=temperature,
                usage=usage,
                history=None,
                system_msg=_reviewer_system_prompt_balanced,
            )
            logger.info(
                "Ensemble review %d/%d complete (overall=%s, decision=%s)",
                idx + 1,
                num_reviews_ensemble,
                parsed.overall,
                parsed.decision,
            )
            parsed_reviews.append(parsed)
            histories.append(history)
        except Exception as exc:
            logger.warning("Ensemble review %d/%d failed: %s", idx + 1, num_reviews_ensemble, exc)

    if not parsed_reviews:
        logger.warning(
            "Warning: Failed to parse ensemble reviews; falling back to single review run."
        )
        return None

    logger.info(
        "Ensemble complete: %d/%d reviews succeeded, generating meta-review",
        len(parsed_reviews),
        num_reviews_ensemble,
    )
    event_callback(
        ReviewProgressEvent(
            step="meta_review",
            substep="Generating meta-review...",
            progress=0.70,
            step_progress=0.0,
        )
    )

    review = _get_meta_review(
        model=model,
        temperature=temperature,
        reviews=parsed_reviews,
        usage=usage,
    )
    if review is None:
        logger.info("Meta-review failed, using first ensemble review as fallback")
        review = parsed_reviews[0]
    else:
        logger.info(
            "Meta-review complete (overall=%s, decision=%s)",
            review.overall,
            review.decision,
        )

    # Average scores from ensemble reviews
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

    # Build message history for reflections
    base_history = histories[0][:-1] if histories and histories[0] else []
    assistant_message = AIMessage(content=json.dumps(review.model_dump(by_alias=True)))
    msg_history = base_history + [assistant_message]

    return _EnsembleResult(review=review, msg_history=msg_history)


def _run_reflections(
    review: ReviewResponseModel,
    msg_history: list[BaseMessage],
    model: str,
    temperature: float,
    usage: TokenUsage,
    num_reflections: int,
    event_callback: Callable[["ReviewProgressEvent"], None],
) -> tuple[ReviewResponseModel, list[BaseMessage]]:
    """Run reflection rounds to refine the review.

    Args:
        review: Initial review to refine
        msg_history: Message history from initial review
        model: Model in "provider:model" format
        temperature: Sampling temperature
        usage: Token usage accumulator
        num_reflections: Total number of reflection rounds (including initial)
        event_callback: Callback for progress events

    Returns:
        Tuple of (refined review, updated message history)
    """
    logger.info("Starting reflection rounds (%d total)", num_reflections)
    total_reflection_rounds = num_reflections - 1

    for reflection_round in range(total_reflection_rounds):
        step_progress = reflection_round / total_reflection_rounds
        event_callback(
            ReviewProgressEvent(
                step="reflection",
                substep=f"Reflection {reflection_round + 1} of {total_reflection_rounds}",
                progress=0.85 + 0.15 * step_progress,
                step_progress=step_progress,
            )
        )

        logger.info("Running reflection round %d/%d", reflection_round + 2, num_reflections)
        reflection_prompt = render_text(
            template_name="llm_review/reflection_prompt.txt.j2",
            context={
                "current_round": reflection_round + 2,
                "num_reflections": num_reflections,
            },
        )
        reflection_response, msg_history = _invoke_review_prompt(
            prompt_text=reflection_prompt,
            model=model,
            temperature=temperature,
            usage=usage,
            history=msg_history,
            system_msg=_reviewer_system_prompt_balanced,
        )
        review = reflection_response
        logger.info(
            "Reflection round %d/%d complete (overall=%s, decision=%s, continue=%s)",
            reflection_round + 2,
            num_reflections,
            review.overall,
            review.decision,
            reflection_response.should_continue,
        )
        if not reflection_response.should_continue:
            logger.info("Model indicated no further reflections needed, stopping early")
            break

    return review, msg_history


# Progress event type for callbacks
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


def perform_review(
    text: str,
    *,
    model: str,
    temperature: float,
    event_callback: Callable[[ReviewProgressEvent], None],
    num_reflections: int,
    num_fs_examples: int,
    num_reviews_ensemble: int,
    context: str | None = None,
) -> ReviewResult:
    """Perform a paper review using LLM.

    Args:
        text: The paper text to review
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        event_callback: Callback for progress events
        num_reflections: Number of reflection rounds
        num_fs_examples: Number of few-shot examples to include
        num_reviews_ensemble: Number of ensemble reviews
        context: Optional pre-formatted context string to include in the prompt

    Returns:
        ReviewResult containing the review and token usage
    """
    logger.info(
        "Starting paper review (model=%s, ensemble=%d, reflections=%d, paper_length=%d chars)",
        model,
        num_reviews_ensemble,
        num_reflections,
        len(text),
    )

    # Create internal token usage tracker
    usage = TokenUsage()

    fewshot_examples = get_review_fewshot_examples(num_fs_examples) if num_fs_examples > 0 else ""
    base_prompt = render_text(
        template_name="llm_review/review_prompt.txt.j2",
        context={
            "context": context,
            "fewshot_examples": fewshot_examples,
            "paper_text": text,
        },
    )

    # Emit event: paper review starting
    # Progress scale: 0-10% init, 10-70% ensemble, 70-85% meta-review, 85-100% reflections
    event_callback(
        ReviewProgressEvent(
            step="init",
            substep="Starting paper review...",
            progress=0.10,
            step_progress=0.0,
        )
    )

    # Run ensemble reviews if requested
    review: ReviewResponseModel | None = None
    msg_history: list[BaseMessage] | None = None

    if num_reviews_ensemble > 1:
        ensemble_result = _run_ensemble_reviews(
            base_prompt=base_prompt,
            model=model,
            temperature=temperature,
            usage=usage,
            num_reviews_ensemble=num_reviews_ensemble,
            event_callback=event_callback,
        )
        if ensemble_result is not None:
            review = ensemble_result.review
            msg_history = ensemble_result.msg_history

    # Fall back to single review if ensemble failed or wasn't requested
    if review is None:
        logger.info("Running single review (no ensemble)")
        review, msg_history = _invoke_review_prompt(
            prompt_text=base_prompt,
            model=model,
            temperature=temperature,
            usage=usage,
            history=None,
            system_msg=_reviewer_system_prompt_balanced,
        )
        logger.info(
            "Single review complete (overall=%s, decision=%s)", review.overall, review.decision
        )

    # Run reflection rounds if requested
    if num_reflections > 1:
        assert msg_history is not None
        review, msg_history = _run_reflections(
            review=review,
            msg_history=msg_history,
            model=model,
            temperature=temperature,
            usage=usage,
            num_reflections=num_reflections,
            event_callback=event_callback,
        )

    total_usage = usage.get_total()
    logger.info(
        "Paper review complete (decision=%s, overall=%s, input_tokens=%d, output_tokens=%d)",
        review.decision,
        review.overall,
        total_usage.input_tokens,
        total_usage.output_tokens,
    )

    return ReviewResult(
        review=review,
        token_usage=total_usage,
        token_usage_detailed=usage.get_detailed(),
    )


def get_review_fewshot_examples(num_fs_examples: int) -> str:
    """Get few-shot examples for review prompts.

    Args:
        num_fs_examples: Number of examples to include (max 3)

    Returns:
        Formatted few-shot prompt string
    """
    fewshot_files = [
        ("132_automated_relational", "132_automated_relational"),
        ("attention", "attention"),
        ("2_carpe_diem", "2_carpe_diem"),
    ]

    fewshot_prompt = render_text(
        template_name="llm_review/fewshot_intro.txt.j2",
        context={},
    )

    files = importlib.resources.files("ae_paper_review.fewshot_examples")

    for paper_name, review_name in fewshot_files[:num_fs_examples]:
        # Try to load pre-extracted text first, fall back to PDF
        txt_file = files.joinpath(f"{paper_name}.txt")
        pdf_file = files.joinpath(f"{paper_name}.pdf")
        json_file = files.joinpath(f"{review_name}.json")

        try:
            paper_text = txt_file.read_text()
        except Exception:
            # Fall back to extracting from PDF
            with importlib.resources.as_file(pdf_file) as pdf_path:
                paper_text = load_paper(str(pdf_path))

        review_data = json.loads(json_file.read_text())
        review_text = str(review_data["review"])

        fewshot_prompt += "\n\n" + render_text(
            template_name="llm_review/fewshot_example.txt.j2",
            context={"paper_text": paper_text, "review_text": review_text},
        )

    return fewshot_prompt


def _get_meta_review(
    model: str,
    temperature: float,
    reviews: list[ReviewResponseModel],
    usage: TokenUsage,
) -> ReviewResponseModel | None:
    """Aggregate multiple reviews into a meta-review (internal function).

    Args:
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        reviews: List of individual reviews to aggregate
        usage: Token usage accumulator

    Returns:
        Aggregated ReviewResponseModel or None if failed
    """
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
        response_dict, _ = get_structured_response_from_llm(
            prompt=base_prompt,
            model=model,
            system_message=system_message,
            temperature=temperature,
            schema_class=ReviewResponseModel,
            msg_history=None,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to generate meta-review.")
        return None
    return ReviewResponseModel.model_validate(response_dict)
