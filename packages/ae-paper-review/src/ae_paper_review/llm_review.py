"""LLM-based paper review functionality."""

import importlib.resources
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import pymupdf  # type: ignore[import-untyped]
from langchain_core.messages import AIMessage, BaseMessage
from pypdf import PdfReader

from .llm.llm import get_structured_response_from_llm
from .llm.token_tracking import TokenUsage, TokenUsageDetail, TokenUsageSummary
from .models import ReviewResponseModel
from .prompts import render_text

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of a paper review including the review and token usage."""

    review: ReviewResponseModel
    token_usage: TokenUsageSummary
    token_usage_detailed: list[TokenUsageDetail]


# Pre-render static templates
_reviewer_system_prompt_balanced = render_text(
    template_name="llm_review/reviewer_system_prompt_balanced.txt.j2",
    context={},
)

_neurips_form = render_text(template_name="llm_review/neurips_form.md.j2", context={})
_calibration_guide = render_text(template_name="llm_review/calibration_guide.txt.j2", context={})


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


def _format_mapping_block(title: str, data: Dict[str, Any]) -> str:
    """Format a dictionary as a markdown block."""
    if not data:
        return ""
    lines = [title + ":"]
    for key, value in data.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lines.append(f"- {key}: {text}")
    return "\n".join(lines)


def _render_context_block(context: Optional[Dict[str, Any]]) -> str:
    """Render review context as a formatted text block."""
    if not context:
        return ""

    blocks: list[str] = []

    overview = context.get("idea_overview")
    if isinstance(overview, dict):
        block = _format_mapping_block("Idea Overview", overview)
        if block:
            blocks.append(block)

    signals = context.get("paper_signals")
    if isinstance(signals, dict):
        block = _format_mapping_block("Automatic Checks", signals)
        if block:
            blocks.append(block)

    section_highlights = context.get("section_highlights")
    if isinstance(section_highlights, dict):
        for section, text in section_highlights.items():
            if not text:
                continue
            blocks.append(f"{section} Highlights:\n{text}")

    novelty = context.get("novelty_review")
    if novelty:
        if isinstance(novelty, str):
            blocks.append(f"Novelty Scan:\n{novelty}")
        elif isinstance(novelty, Iterable):
            formatted = "\n".join(f"- {item}" for item in novelty if item)
            if formatted:
                blocks.append(f"Novelty Scan:\n{formatted}")

    additional = context.get("additional_notes")
    if additional:
        blocks.append(f"Additional Notes:\n{additional}")

    blocks = [b for b in blocks if b]
    return "\n\n".join(blocks)


def perform_review(
    text: str,
    model: str,
    temperature: float,
    *,
    context: dict[str, str] | None = None,
    num_reflections: int = 2,
    num_fs_examples: int = 1,
    num_reviews_ensemble: int = 3,
    msg_history: list[BaseMessage] | None = None,
    reviewer_system_prompt: str | None = None,
    review_instruction_form: str | None = None,
    calibration_notes: str | None = None,
    event_callback: Optional[Callable[[ReviewProgressEvent], None]] = None,
) -> ReviewResult:
    """Perform a paper review using LLM.

    Args:
        text: The paper text to review
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        context: Optional context dict with idea_overview, paper_signals, etc.
        num_reflections: Number of reflection rounds (default 2)
        num_fs_examples: Number of few-shot examples to include (default 1)
        num_reviews_ensemble: Number of ensemble reviews (default 3)
        msg_history: Optional message history for continuation
        reviewer_system_prompt: Custom system prompt (uses default if None)
        review_instruction_form: Custom review form (uses NeurIPS form if None)
        calibration_notes: Custom calibration notes (uses default if None)
        event_callback: Optional callback for progress events

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

    # Use defaults if not provided
    if reviewer_system_prompt is None:
        reviewer_system_prompt = _reviewer_system_prompt_balanced
    if review_instruction_form is None:
        review_instruction_form = _neurips_form
    if calibration_notes is None:
        calibration_notes = _calibration_guide

    context_block = _render_context_block(context)
    base_prompt = review_instruction_form
    if calibration_notes:
        base_prompt += f"\n\nCalibration notes:\n{calibration_notes.strip()}\n"
    if context_block:
        base_prompt += f"\n\nContext for your evaluation:\n{context_block}\n"

    if num_fs_examples > 0:
        fs_prompt = get_review_fewshot_examples(num_fs_examples)
        base_prompt += fs_prompt

    base_prompt += f"""
Here is the paper you are asked to review:
```
{text}
```"""

    # Emit event: paper review starting
    if event_callback:
        event_callback(
            ReviewProgressEvent(
                step="paper_review",
                substep="Starting paper review...",
                progress=0.80,
                step_progress=0.0,
            )
        )

    # reviewer_system_prompt is guaranteed to be a str by this point (defaulted above)
    assert reviewer_system_prompt is not None
    _default_system_prompt: str = reviewer_system_prompt

    def _invoke_review_prompt(
        prompt_text: str,
        history: list[BaseMessage] | None = None,
        *,
        system_msg: str = _default_system_prompt,
    ) -> tuple[ReviewResponseModel, list[BaseMessage]]:
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

    review: Optional[ReviewResponseModel] = None
    if num_reviews_ensemble > 1:
        logger.info("Running ensemble reviews (%d reviews)", num_reviews_ensemble)
        parsed_reviews: List[ReviewResponseModel] = []
        histories: List[list[BaseMessage]] = []
        for idx in range(num_reviews_ensemble):
            try:
                # Emit event: review ensemble progress
                if event_callback:
                    step_progress = (idx + 1) / num_reviews_ensemble
                    event_callback(
                        ReviewProgressEvent(
                            step="paper_review",
                            substep=f"Review {idx + 1} of {num_reviews_ensemble}",
                            progress=0.80 + 0.20 * step_progress,
                            step_progress=step_progress,
                        )
                    )

                logger.info("Generating ensemble review %d/%d", idx + 1, num_reviews_ensemble)
                parsed, history = _invoke_review_prompt(base_prompt, msg_history)
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
                logger.warning(
                    "Ensemble review %d/%d failed: %s", idx + 1, num_reviews_ensemble, exc
                )

        if parsed_reviews:
            logger.info(
                "Ensemble complete: %d/%d reviews succeeded, generating meta-review",
                len(parsed_reviews),
                num_reviews_ensemble,
            )
            review = _get_meta_review(model, temperature, parsed_reviews, usage=usage)
            if review is None:
                logger.info("Meta-review failed, using first ensemble review as fallback")
                review = parsed_reviews[0]
            else:
                logger.info(
                    "Meta-review complete (overall=%s, decision=%s)",
                    review.overall,
                    review.decision,
                )
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
                if collected and review is not None:
                    # Replace numpy with pure Python
                    mean_value = round(sum(collected) / len(collected), 2)
                    setattr(review, score, float(mean_value))
            if review is not None:
                base_history = (
                    histories[0][:-1] if histories and histories[0] else (msg_history or [])
                )
                assistant_message = AIMessage(content=json.dumps(review.model_dump(by_alias=True)))
                msg_history = base_history + [assistant_message]
        else:
            logger.warning(
                "Warning: Failed to parse ensemble reviews; falling back to single review run."
            )

    if review is None:
        logger.info("Running single review (no ensemble)")
        review, msg_history = _invoke_review_prompt(base_prompt, msg_history)
        logger.info(
            "Single review complete (overall=%s, decision=%s)", review.overall, review.decision
        )
    assert review is not None

    if num_reflections > 1 and review is not None:
        logger.info("Starting reflection rounds (%d total)", num_reflections)
        for reflection_round in range(num_reflections - 1):
            logger.info("Running reflection round %d/%d", reflection_round + 2, num_reflections)
            reflection_prompt = _reviewer_reflection_prompt.format(
                current_round=reflection_round + 2,
                num_reflections=num_reflections,
            )
            reflection_response, msg_history = _invoke_review_prompt(
                reflection_prompt,
                msg_history,
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


_reviewer_reflection_prompt = """Round {current_round}/{num_reflections}.
Carefully consider the accuracy and soundness of the review you just created.
Include any factors that you think are important in evaluating the paper.
Ensure the review is clear and concise, and keep the JSON schema identical.
Do not make things overly complicated.
In the next attempt, try and refine and improve your review.
Stick to the spirit of the original review unless there are glaring issues.

Return an updated JSON object following the required schema.
Add a boolean field "should_continue" and set it to false only if no further changes are needed."""


def load_paper(pdf_path: str, num_pages: int | None = None, min_size: int = 100) -> str:
    """Load paper text from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        num_pages: Optional limit on number of pages to extract
        min_size: Minimum text size to consider valid

    Returns:
        Extracted text from the PDF
    """
    try:
        # Lazy import with stdout suppression to avoid polluting output
        import io
        import sys

        _original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        import pymupdf4llm  # type: ignore[import-untyped]

        sys.stdout = _original_stdout

        text: str
        if num_pages is None:
            text = str(pymupdf4llm.to_markdown(pdf_path))
        else:
            reader = PdfReader(pdf_path)
            min_pages = min(len(reader.pages), num_pages)
            text = str(pymupdf4llm.to_markdown(pdf_path, pages=list(range(min_pages))))
        if len(text) < min_size:
            raise Exception("Text too short")
    except Exception as e:
        logger.warning(f"Error with pymupdf4llm, falling back to pymupdf: {e}")
        try:
            doc = pymupdf.open(pdf_path)
            if num_pages:
                doc = doc[:num_pages]
            text = ""
            for page in doc:
                text += str(page.get_text())
            if len(text) < min_size:
                raise Exception("Text too short")
        except Exception as e:
            logger.warning(f"Error with pymupdf, falling back to pypdf: {e}")
            reader = PdfReader(pdf_path)
            if num_pages is None:
                pages = reader.pages
            else:
                pages = reader.pages[:num_pages]
            text = "".join(page.extract_text() for page in pages)
            if len(text) < min_size:
                raise Exception("Text too short")
    return text


def load_review(json_path: str) -> str:
    """Load a review from a JSON file."""
    with open(json_path, "r") as json_file:
        loaded = json.load(json_file)
    return str(loaded["review"])


def _get_fewshot_path(filename: str) -> str:
    """Get path to a fewshot example file using importlib.resources."""
    files = importlib.resources.files("ae_paper_review.fewshot_examples")
    # Return a path that can be used with open()
    # For installed packages, we need to use as_file context manager
    return str(files.joinpath(filename))


def get_review_fewshot_examples(num_fs_examples: int = 1) -> str:
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

    fewshot_prompt = """
Below are some sample reviews, copied from previous machine learning conferences.
Note that while each review is formatted differently according to each reviewer's style,
the reviews are well-structured and therefore easy to navigate.
"""

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

        fewshot_prompt += f"""
Paper:

```
{paper_text}
```

Review:

```
{review_text}
```
"""
    return fewshot_prompt


_meta_reviewer_system_prompt = """You are an Area Chair at a machine learning conference.
You are in charge of meta-reviewing a paper that was reviewed by {reviewer_count} reviewers.
Your job is to aggregate the reviews into a single meta-review in the same format.
Be critical and cautious in your decision, find consensus, and respect all reviewers' opinions."""


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
    review_text = ""
    for i, r in enumerate(reviews):
        review_text += f"""
Review {i + 1}/{len(reviews)}:
```
{json.dumps(r.model_dump(by_alias=True))}
```
"""
    base_prompt = _neurips_form + review_text
    try:
        response_dict, _ = get_structured_response_from_llm(
            prompt=base_prompt,
            model=model,
            system_message=_meta_reviewer_system_prompt.format(reviewer_count=len(reviews)),
            temperature=temperature,
            schema_class=ReviewResponseModel,
            msg_history=None,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to generate meta-review.")
        return None
    return ReviewResponseModel.model_validate(response_dict)
