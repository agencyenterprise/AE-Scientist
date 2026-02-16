"""Semantic Scholar API integration for novelty scanning."""

import logging
import os
from typing import NamedTuple

import requests

logger = logging.getLogger(__name__)


class RelatedPaper(NamedTuple):
    """A related paper from Semantic Scholar."""

    title: str
    year: int | None
    venue: str
    citation_count: int
    authors: str
    abstract_snippet: str


class SemanticScholarResult(NamedTuple):
    """Result of a Semantic Scholar novelty scan."""

    papers: list[RelatedPaper]
    message: str | None


def scan_for_related_papers(
    *,
    title: str | None,
    abstract: str | None,
    max_results: int,
) -> SemanticScholarResult:
    """Scan Semantic Scholar for related papers.

    Args:
        title: Paper title for search query
        abstract: Paper abstract (used if title not available)
        max_results: Maximum number of related papers to return

    Returns:
        SemanticScholarResult with related papers or status message
    """
    query = title or ""
    if not query and abstract:
        query = _truncate_text(text=abstract, limit=180)
    if not query:
        return SemanticScholarResult(
            papers=[],
            message="Semantic Scholar scan skipped (no title or abstract).",
        )

    headers: dict[str, str] = {}
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
        logger.warning("Semantic Scholar API call failed: %s", exc)
        return SemanticScholarResult(
            papers=[],
            message=f"Semantic Scholar scan failed: {exc}",
        )

    payload = response.json()
    data = payload.get("data", []) if isinstance(payload, dict) else []
    if not data:
        return SemanticScholarResult(
            papers=[],
            message="Semantic Scholar scan returned no overlaps.",
        )

    papers: list[RelatedPaper] = []
    sorted_data = sorted(data, key=lambda item: item.get("citationCount", 0), reverse=True)
    for entry in sorted_data[:max_results]:
        authors_list = entry.get("authors", [])[:3]
        authors_str = ", ".join(author.get("name", "Anon") for author in authors_list) or "n/a"
        papers.append(
            RelatedPaper(
                title=entry.get("title", "Untitled"),
                year=entry.get("year"),
                venue=entry.get("venue", "unknown venue"),
                citation_count=entry.get("citationCount", 0),
                authors=authors_str,
                abstract_snippet=_truncate_text(text=entry.get("abstract", ""), limit=180),
            )
        )

    return SemanticScholarResult(papers=papers, message=None)


def _truncate_text(*, text: str | None, limit: int) -> str:
    """Truncate text to limit, breaking at word boundaries."""
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
