"""Integration layer between ae-paper-review and research_pipeline.

This module provides adapters that connect the standalone ae-paper-review package
with the research_pipeline's webhook-based telemetry and event systems.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from ae_paper_review import (
    ReviewProgressEvent,
    ReviewResult,
)
from ae_paper_review import detect_duplicate_figures as _detect_duplicate_figures
from ae_paper_review import generate_vlm_img_review as _generate_vlm_img_review
from ae_paper_review import perform_imgs_cap_ref_review as _perform_imgs_cap_ref_review
from ae_paper_review import (
    perform_imgs_cap_ref_review_selection as _perform_imgs_cap_ref_review_selection,
)
from ae_paper_review import perform_review as _perform_review
from ae_paper_review.llm.token_tracking import TokenUsage
from ae_paper_review.models import FigureImageCaptionRefReview
from langchain_core.messages import BaseMessage

from ai_scientist.api_types import TokenUsageEvent
from ai_scientist.telemetry.event_persistence import WebhookClient
from ai_scientist.treesearch.events import BaseEvent, PaperGenerationProgressEvent

logger = logging.getLogger(__name__)


def _load_idea_json(idea_dir: str, idea_json: dict[str, Any] | None) -> dict[str, Any] | None:
    """Load idea JSON from file or return provided dict.

    Args:
        idea_dir: Directory containing idea.json
        idea_json: Optional pre-loaded idea dict

    Returns:
        Idea payload dict or None
    """
    if idea_json:
        return idea_json
    idea_path = Path(idea_dir) / "idea.json"
    if idea_path.exists():
        try:
            result = json.loads(idea_path.read_text())
            return result if isinstance(result, dict) else None
        except Exception:
            logger.warning("Could not read idea.json for review context", exc_info=True)
    return None


def _get_webhook_client() -> WebhookClient | None:
    """Get webhook client if configured."""
    run_id = os.environ.get("RUN_ID")
    webhook_url = os.environ.get("TELEMETRY_WEBHOOK_URL")
    webhook_token = os.environ.get("TELEMETRY_WEBHOOK_TOKEN")

    if webhook_url and webhook_token and run_id:
        return WebhookClient(base_url=webhook_url, token=webhook_token, run_id=run_id)
    return None


def _publish_token_usage(
    webhook_client: WebhookClient | None,
    token_usage_detailed: list[dict[str, Any]],
) -> None:
    """Publish token usage records to webhook if available."""
    if not webhook_client:
        return

    for usage_record in token_usage_detailed:
        try:
            webhook_client.publish(
                kind="token_usage",
                payload=TokenUsageEvent(
                    model=usage_record.get("model", "unknown"),
                    input_tokens=usage_record.get("input_tokens", 0),
                    cached_input_tokens=usage_record.get("cached_input_tokens", 0),
                    output_tokens=usage_record.get("output_tokens", 0),
                ),
            )
        except Exception:
            logger.exception("Failed to publish token usage webhook (non-fatal)")


def make_event_callback_adapter(
    run_id: str,
    callback: Callable[[BaseEvent], None],
) -> Callable[[ReviewProgressEvent], None]:
    """Create an adapter that converts ReviewProgressEvent to PaperGenerationProgressEvent.

    Args:
        run_id: The run ID for the event
        callback: The original callback that expects BaseEvent

    Returns:
        Adapted callback that accepts ReviewProgressEvent
    """

    def wrapper(event: ReviewProgressEvent) -> None:
        callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step=event.step,
                substep=event.substep,
                progress=event.progress,
                step_progress=event.step_progress,
            )
        )

    return wrapper


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
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> ReviewResult:
    """Perform paper review with research_pipeline integration.

    This wraps the ae-paper-review perform_review function with:
    - Automatic webhook-based token usage publishing when telemetry is configured
    - Event callback adaptation for PaperGenerationProgressEvent

    Args:
        text: Paper text to review
        model: LLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        context: Optional review context
        num_reflections: Number of reflection rounds
        num_fs_examples: Number of few-shot examples
        num_reviews_ensemble: Number of ensemble reviews
        msg_history: Optional message history
        event_callback: Optional callback for progress events (expects BaseEvent)
        run_id: Optional run ID for events

    Returns:
        ReviewResult containing review and token usage
    """
    # Adapt event callback if provided
    adapted_callback = None
    if event_callback and run_id:
        adapted_callback = make_event_callback_adapter(run_id, event_callback)

    # Perform the review (returns ReviewResult with token usage)
    result = _perform_review(
        text=text,
        model=model,
        temperature=temperature,
        context=context,
        num_reflections=num_reflections,
        num_fs_examples=num_fs_examples,
        num_reviews_ensemble=num_reviews_ensemble,
        msg_history=msg_history,
        event_callback=adapted_callback,
    )

    # Publish token usage to webhook if configured
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, result.token_usage_detailed)

    return result


def perform_imgs_cap_ref_review(
    model: str,
    pdf_path: str,
    temperature: float,
) -> list[FigureImageCaptionRefReview]:
    """Perform VLM figure review with research_pipeline integration.

    This wraps the ae-paper-review perform_imgs_cap_ref_review function
    with automatic webhook-based token usage publishing.

    Args:
        model: VLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature

    Returns:
        List of figure reviews
    """
    # Create a usage tracker to accumulate VLM token usage
    usage = TokenUsage()

    reviews = _perform_imgs_cap_ref_review(
        model=model,
        pdf_path=pdf_path,
        temperature=temperature,
        usage=usage,
    )

    # Publish token usage to webhook if configured
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, usage.get_detailed())

    return reviews


def detect_duplicate_figures(
    model: str,
    pdf_path: str,
    temperature: float,
) -> str | dict[str, str]:
    """Detect duplicate figures with token tracking.

    Args:
        model: VLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature

    Returns:
        Analysis string or error dict
    """
    usage = TokenUsage()
    result = _detect_duplicate_figures(
        model=model,
        pdf_path=pdf_path,
        temperature=temperature,
        usage=usage,
    )
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, usage.get_detailed())
    return result


def generate_vlm_img_review(
    img: dict[str, Any],
    model: str,
    temperature: float,
) -> dict[str, Any] | None:
    """Generate VLM image review with token tracking.

    Args:
        img: Dict with images list
        model: VLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature

    Returns:
        Review dict or None if failed
    """
    usage = TokenUsage()
    result = _generate_vlm_img_review(
        img=img,
        model=model,
        temperature=temperature,
        usage=usage,
    )
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, usage.get_detailed())
    return result


def perform_imgs_cap_ref_review_selection(
    model: str,
    pdf_path: str,
    reflection_page_info: str,
    temperature: float,
) -> dict[str, Any]:
    """Review figures for selection with token tracking.

    Args:
        model: VLM model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        reflection_page_info: Page limit information
        temperature: Sampling temperature

    Returns:
        Dict mapping figure names to reviews
    """
    usage = TokenUsage()
    result = _perform_imgs_cap_ref_review_selection(
        model=model,
        pdf_path=pdf_path,
        reflection_page_info=reflection_page_info,
        temperature=temperature,
        usage=usage,
    )
    webhook_client = _get_webhook_client()
    _publish_token_usage(webhook_client, usage.get_detailed())
    return result


def _bool_label(value: bool) -> str:
    """Convert boolean to 'yes'/'no' string."""
    return "yes" if value else "no"


def _shorten_text(text: Optional[str], limit: int) -> str:
    """Shorten text to a limit, breaking at word boundaries."""
    if not text:
        return ""
    squashed = " ".join(text.split())
    if len(squashed) <= limit:
        return squashed
    truncated = squashed[:limit]
    cutoff = truncated.rfind(" ")
    if cutoff > 20:
        truncated = truncated[:cutoff]
    return truncated.rstrip() + " ..."


def _extract_section(text: str, header: str, limit: int = 800) -> str:
    """Extract and shorten a section from markdown text."""
    if not text:
        return ""
    pattern = re.compile(rf"^#+\s*{re.escape(header)}.*?$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_header = re.compile(r"^#+\s+.+$", re.MULTILINE)
    next_match = next_header.search(text, start)
    end = next_match.start() if next_match else len(text)
    section_text = text[start:end].strip()
    return _shorten_text(section_text, limit)


def _semantic_scholar_scan(
    title: Optional[str], abstract: Optional[str], max_results: int = 3
) -> str:
    """Scan Semantic Scholar for related papers."""
    if os.getenv("AI_SCIENTIST_DISABLE_SEMANTIC_SCHOLAR", "").lower() in {"1", "true", "yes"}:
        return "Semantic Scholar scan disabled via environment flag."

    query = title or ""
    if not query and abstract:
        query = _shorten_text(abstract, 180)
    if not query:
        return "Semantic Scholar scan skipped (no title or abstract)."

    headers: Dict[str, str] = {}
    api_key = os.getenv("S2_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            headers=headers,
            params={
                "query": query,
                "limit": str(max_results),
                "fields": "title,authors,year,venue,citationCount,abstract",
            },
            timeout=10,
        )
        response.raise_for_status()
    except Exception as exc:
        return f"Semantic Scholar scan failed: {exc}"

    payload = response.json()
    data: List[Dict[str, Any]] = payload.get("data", []) if isinstance(payload, dict) else []
    if not data:
        return "Semantic Scholar scan returned no overlaps."

    formatted: List[str] = []
    for entry in sorted(data, key=lambda item: item.get("citationCount", 0), reverse=True):
        title_text = entry.get("title", "Untitled")
        year_text = entry.get("year", "unknown year")
        venue = entry.get("venue", "unknown venue")
        citations = entry.get("citationCount", "N/A")
        abstract_snip = _shorten_text(entry.get("abstract", ""), 180)
        authors = ", ".join(author.get("name", "Anon") for author in entry.get("authors", [])[:3])
        lead_authors = authors or "n/a"
        formatted.append(
            f"{title_text} ({year_text}, {venue}) — citations: {citations}; "
            f"lead authors: {lead_authors}; abstract: {abstract_snip}"
        )
    return "\n".join(formatted[:max_results])


def build_auto_review_context(
    idea_dir: str,
    idea_json: dict[str, Any] | None,
    paper_content: str,
) -> dict[str, Any]:
    """Build review context from paper content and optional idea information.

    Args:
        idea_dir: Directory containing idea.json
        idea_json: Optional pre-loaded idea dict
        paper_content: Full paper text in markdown format

    Returns:
        Context dict with idea_overview, paper_signals, section_highlights, novelty_review
    """
    # Load idea.json from disk if not already provided
    idea_payload = _load_idea_json(idea_dir, idea_json)

    context: dict[str, Any] = {}

    if isinstance(idea_payload, dict):
        context["idea_overview"] = {
            "Title": idea_payload.get("Title"),
            "Short Hypothesis": _shorten_text(idea_payload.get("Short Hypothesis"), 220),
            "Abstract": _shorten_text(idea_payload.get("Abstract"), 260),
            "Planned Experiments": _shorten_text(idea_payload.get("Experiments"), 260),
        }
        limitations = _shorten_text(idea_payload.get("Risk Factors and Limitations"), 240)
        if limitations:
            context["additional_notes"] = f"Idea limitations: {limitations}"

    # Analyze paper signals
    word_count = len(paper_content.split())
    has_results = bool(
        re.search(
            r"^#+\s*(results|evaluation|experiments)", paper_content, re.IGNORECASE | re.MULTILINE
        )
    )
    has_limitations_section = bool(
        re.search(
            r"^#+\s*(limitations|ethical|broader impacts)",
            paper_content,
            re.IGNORECASE | re.MULTILINE,
        )
    )
    has_citations = bool(
        re.search(r"\[[0-9]{1,3}\]", paper_content)
        or re.search(r"\(.*?et al\.,?\s*\d{4}\)", paper_content)
    )
    mentions_code = "github" in paper_content.lower() or "code" in paper_content.lower()
    mentions_figures = bool(re.search(r"\b(fig(ure)?|table)\b", paper_content, re.IGNORECASE))

    context["paper_signals"] = {
        "Word Count": word_count,
        "Has Results Section": _bool_label(has_results),
        "Mentions Limitations": _bool_label(has_limitations_section),
        "Contains Citations": _bool_label(has_citations),
        "Mentions Code/Data": _bool_label(mentions_code),
        "Figures Or Tables": _bool_label(mentions_figures),
    }

    # Extract section highlights
    section_highlights: dict[str, str] = {}
    for header in (
        "Abstract",
        "Introduction",
        "Results",
        "Experiments",
        "Conclusion",
        "Limitations",
    ):
        summary = _extract_section(paper_content, header)
        if summary:
            section_highlights[header] = summary
    if section_highlights:
        context["section_highlights"] = section_highlights

    # Novelty scan via Semantic Scholar
    paper_title_match = re.search(r"^#\s+(.+)$", paper_content, re.MULTILINE)
    paper_title = paper_title_match.group(1).strip() if paper_title_match else None
    abstract_section = section_highlights.get("Abstract")

    context["novelty_review"] = _semantic_scholar_scan(
        paper_title or (idea_payload.get("Title") if isinstance(idea_payload, dict) else None),
        abstract_section,
    )

    return context
