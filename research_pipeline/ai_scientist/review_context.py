import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def bool_label(value: bool) -> str:
    return "yes" if value else "no"


def shorten_text(text: Optional[str], limit: int) -> str:
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


def extract_section(text: str, header: str, limit: int = 800) -> str:
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
    return shorten_text(section_text, limit)


def _load_idea_payload(
    idea_dir: str, idea_json: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if idea_json:
        return idea_json
    idea_path = Path(idea_dir) / "idea.json"
    if idea_path.exists():
        try:
            result = json.loads(idea_path.read_text())
            return result if isinstance(result, dict) else None
        except Exception as exc:
            logger.warning(f"Warning: could not read idea.json for review context ({exc})")
    return None


def _semantic_scholar_scan(
    title: Optional[str], abstract: Optional[str], max_results: int = 3
) -> str:
    if os.getenv("AI_SCIENTIST_DISABLE_SEMANTIC_SCHOLAR", "").lower() in {"1", "true", "yes"}:
        return "Semantic Scholar scan disabled via environment flag."

    query = title or ""
    if not query and abstract:
        query = shorten_text(abstract, 180)
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
        abstract_snip = shorten_text(entry.get("abstract", ""), 180)
        authors = ", ".join(author.get("name", "Anon") for author in entry.get("authors", [])[:3])
        formatted.append(
            f"{title_text} ({year_text}, {venue}) — citations: {citations}; lead authors: {authors or 'n/a'}; abstract: {abstract_snip}"
        )
    return "\n".join(formatted[:max_results])


def build_auto_review_context(
    idea_dir: str,
    idea_json: Optional[Dict[str, Any]],
    paper_content: str,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {}

    idea_payload = _load_idea_payload(idea_dir, idea_json)
    if isinstance(idea_payload, dict):
        context["idea_overview"] = {
            "Title": idea_payload.get("Title"),
            "Short Hypothesis": shorten_text(idea_payload.get("Short Hypothesis"), 220),
            "Abstract": shorten_text(idea_payload.get("Abstract"), 260),
            "Planned Experiments": shorten_text(idea_payload.get("Experiments"), 260),
        }
        limitations = shorten_text(idea_payload.get("Risk Factors and Limitations"), 240)
        if limitations:
            context["additional_notes"] = f"Idea limitations: {limitations}"

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
        "Has Results Section": bool_label(has_results),
        "Mentions Limitations": bool_label(has_limitations_section),
        "Contains Citations": bool_label(has_citations),
        "Mentions Code/Data": bool_label(mentions_code),
        "Figures Or Tables": bool_label(mentions_figures),
    }

    section_highlights: Dict[str, str] = {}
    for header in (
        "Abstract",
        "Introduction",
        "Results",
        "Experiments",
        "Conclusion",
        "Limitations",
    ):
        summary = extract_section(paper_content, header)
        if summary:
            section_highlights[header] = summary
    if section_highlights:
        context["section_highlights"] = section_highlights

    paper_title_match = re.search(r"^#\s+(.+)$", paper_content, re.MULTILINE)
    paper_title = paper_title_match.group(1).strip() if paper_title_match else None
    abstract_section = section_highlights.get("Abstract")

    context["novelty_review"] = _semantic_scholar_scan(
        paper_title or (idea_payload.get("Title") if isinstance(idea_payload, dict) else None),
        abstract_section,
    )

    return context
