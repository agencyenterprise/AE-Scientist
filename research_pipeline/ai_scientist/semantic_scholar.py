"""
Semantic Scholar API integration with parallel search and rate limiting.
"""

import logging
import os
import time
import warnings
from threading import Lock
from typing import Any, Dict

import backoff
import requests
from backoff.types import Details

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
