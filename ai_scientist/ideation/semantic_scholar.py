"""
Semantic Scholar API integration with parallel search and rate limiting.

This module provides:
1. SemanticScholarSearchTool: A tool-based interface for searching papers
2. search_for_papers(): Individual paper search with rate limiting
3. search_for_papers_batch(): Parallel search for multiple queries
4. RateLimiter: Thread-safe rate limiting for API calls

Key Features:
- Intelligent rate limiting (0.9 req/sec without API key, 5 req/sec with key)
- Thread-safe parallel search capability
- Automatic backoff on API errors
- Backward compatible with existing code

Example Usage:
    # Single search
    papers = search_for_papers("transformer attention", result_limit=10)

    # Batch search (parallel)
    results = search_for_papers_batch(
        queries=["transformers", "reinforcement learning"],
        result_limit=10,
        max_workers=3
    )

For more details, see: ai_scientist/tools/SEMANTIC_SCHOLAR_IMPROVEMENTS.md
"""

import logging
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Dict, List, Optional

import backoff
import requests
from backoff.types import Details

from ai_scientist.ideation.base_tool import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


def on_backoff(details: Details) -> None:
    logger.debug(
        f"Backing off {details['wait']:0.1f} seconds after {details['tries']} tries "
        f"calling function {details['target'].__name__} at {time.strftime('%X')}"
    )


class RateLimiter:
    """Thread-safe rate limiter for API calls."""

    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 1.0
        self.last_call = 0.0
        self.lock = Lock()

    def wait(self) -> None:
        """Wait until the next call is allowed."""
        with self.lock:
            now = time.time()
            time_since_last_call = now - self.last_call
            if time_since_last_call < self.min_interval:
                sleep_time = self.min_interval - time_since_last_call
                time.sleep(sleep_time)
            self.last_call = time.time()


# Global rate limiter instances
_rate_limiter_with_key = RateLimiter(calls_per_second=5.0)  # Conservative limit with API key
_rate_limiter_without_key = RateLimiter(calls_per_second=0.9)  # Slightly under 1/sec without key


class SemanticScholarSearchTool(BaseTool):
    def __init__(
        self,
        name: str = "SearchSemanticScholar",
        description: str = (
            "Search for relevant literature using Semantic Scholar. "
            "Provide a search query to find relevant papers."
        ),
        max_results: int = 10,
    ):
        parameters: list[ToolParameter] = [
            ToolParameter(
                {
                    "name": "query",
                    "type": "str",
                    "description": "The search query to find relevant papers.",
                }
            )
        ]
        super().__init__(name, description, parameters)
        self.max_results = max_results
        self.S2_API_KEY = os.getenv("S2_API_KEY")
        if not self.S2_API_KEY:
            warnings.warn(
                "No Semantic Scholar API key found. Requests will be subject to stricter rate limits. "
                "Set the S2_API_KEY environment variable for higher limits."
            )

    def use_tool(self, query: str, **kwargs: str) -> str | None:  # type: ignore[override]
        papers = self.search_for_papers(query)
        if papers:
            return self.format_papers(papers)
        else:
            return "No papers found."

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
        on_backoff=on_backoff,
    )
    def search_for_papers(self, query: str) -> Optional[List[Dict]]:
        if not query:
            return None

        headers = {}
        has_api_key = bool(self.S2_API_KEY)
        if self.S2_API_KEY:
            headers["X-API-KEY"] = self.S2_API_KEY

        # Use appropriate rate limiter
        rate_limiter = _rate_limiter_with_key if has_api_key else _rate_limiter_without_key
        rate_limiter.wait()

        rsp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            headers=headers,
            params={
                "query": query,
                "limit": str(self.max_results),
                "fields": "title,authors,venue,year,abstract,citationCount",
            },
        )
        logger.debug(f"Response Status Code: {rsp.status_code}")
        logger.debug(f"Response Content: {rsp.text[:500]}")
        rsp.raise_for_status()
        results = rsp.json()
        total = results.get("total", 0)
        if total == 0:
            return None

        papers = results.get("data", [])
        # Sort papers by citationCount in descending order
        papers.sort(key=lambda x: x.get("citationCount", 0), reverse=True)
        return papers if isinstance(papers, list) else []

    def format_papers(self, papers: List[Dict]) -> str:
        paper_strings = []
        for i, paper in enumerate(papers):
            authors = ", ".join(
                [author.get("name", "Unknown") for author in paper.get("authors", [])]
            )
            paper_strings.append(
                f"""{i + 1}: {paper.get("title", "Unknown Title")}. {authors}. {paper.get("venue", "Unknown Venue")}, {paper.get("year", "Unknown Year")}.
Number of citations: {paper.get("citationCount", "N/A")}
Abstract: {paper.get("abstract", "No abstract available.")}"""
            )
        return "\n\n".join(paper_strings)


@backoff.on_exception(backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff)
def search_for_papers(query: str, result_limit: int = 10) -> list[Dict[Any, Any]] | None:
    S2_API_KEY = os.getenv("S2_API_KEY")
    headers = {}
    has_api_key = bool(S2_API_KEY)

    if not has_api_key:
        warnings.warn(
            "No Semantic Scholar API key found. Requests will be subject to stricter rate limits."
        )
    else:
        headers["X-API-KEY"] = S2_API_KEY

    if not query:
        return None

    # Use appropriate rate limiter
    rate_limiter = _rate_limiter_with_key if has_api_key else _rate_limiter_without_key
    rate_limiter.wait()

    rsp = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        headers=headers,
        params={
            "query": query,
            "limit": str(result_limit),
            "fields": "title,authors,venue,year,abstract,citationStyles,citationCount",
        },
    )
    logger.debug(f"Response Status Code: {rsp.status_code}")
    logger.debug(f"Response Content: {rsp.text[:500]}")
    rsp.raise_for_status()
    results = rsp.json()
    total = results["total"]
    if not total:
        return None

    papers = results["data"]
    return papers if isinstance(papers, list) else []


def search_for_papers_batch(
    queries: list[str], result_limit: int = 10, max_workers: int = 3
) -> dict[str, list[Dict[Any, Any]] | None]:
    """
    Search for multiple queries in parallel with rate limiting.

    Args:
        queries: List of search queries
        result_limit: Maximum number of results per query
        max_workers: Maximum number of parallel workers (default: 3, conservative for shared rate limits)

    Returns:
        Dictionary mapping queries to their results
    """
    if not queries:
        return {}

    results = {}

    def search_single(query: str) -> tuple[str, list[Dict[Any, Any]] | None]:
        """Helper to search a single query and return (query, result) tuple."""
        try:
            papers = search_for_papers(query, result_limit)
            return (query, papers)
        except Exception as e:
            logger.exception(f"Error searching for '{query}': {e}")
            return (query, None)

    # Use ThreadPoolExecutor for parallel requests
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_query = {executor.submit(search_single, q): q for q in queries}

        for future in as_completed(future_to_query):
            query, result = future.result()
            results[query] = result

    return results
