"""
Mem0 Memory Search service.

This module handles communication with Mem0 API to search through user memories
using semantic search with AI-powered similarity matching.
"""

import logging
import traceback
from typing import Dict, List, Optional

import aiohttp
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


class Mem0Memory(BaseModel):
    """Mem0 memory search result."""

    id: str
    memory: str
    hash: str
    metadata: Dict
    score: float
    created_at: str
    updated_at: Optional[str]
    user_id: str


class Mem0SearchResult(BaseModel):
    """Mem0 search response container."""

    results: List[Mem0Memory]


def _format_memories_context(summaries: List[str]) -> str:
    """
    Format a list of memory summaries into a concise context block.

    Args:
        summaries: List of memory summary strings

    Returns:
        Formatted context string to embed into prompts
    """
    if not summaries:
        return ""

    lines: List[str] = []
    for idx, summary in enumerate(summaries, start=1):
        text = (summary or "").strip()
        if not text:
            continue
        lines.append(f"{idx}. {text}")

    if not lines:
        return ""

    return "\n".join(lines)


class Mem0Service:
    """Service for interacting with Mem0 Memory Search API."""

    # Limit the number of memories used in prompts/estimations to avoid context bloat
    MAX_MEMORIES_FOR_CONTEXT: int = 4
    SCORE_THRESHOLD: float = 0.38

    def __init__(self) -> None:
        """Initialize Mem0 service."""
        if not settings.MEM0_API_URL:
            raise ValueError("MEM0_API_URL environment variable is required")
        if not settings.MEM0_USER_ID:
            raise ValueError("MEM0_USER_ID environment variable is required")

        self.api_url = settings.MEM0_API_URL.rstrip("/")
        self.user_id = settings.MEM0_USER_ID

    async def generate_project_creation_memories(
        self, imported_chat_keywords: str
    ) -> tuple[list[dict], str]:
        """Generate project creation memories."""
        metadata = {
            "type": "summary",
        }
        logger.info("Generating project creation memories for %s", imported_chat_keywords)
        raw_results = await self._search(query=imported_chat_keywords, metadata=metadata)
        # Filter out low-scoring memories
        good_score_results = [m for m in raw_results.results if m.score >= self.SCORE_THRESHOLD]
        logger.info(
            "Filtered out %d low-scoring memories, %d remaining",
            len(raw_results.results) - len(good_score_results),
            len(good_score_results),
        )

        # Sort and limit
        limited_sorted: List[Mem0Memory] = sorted(
            good_score_results, key=lambda m: m.score, reverse=True
        )[: self.MAX_MEMORIES_FOR_CONTEXT]

        dumped_results = [m.model_dump() for m in limited_sorted]
        return dumped_results, _format_memories_context(
            summaries=[m.memory for m in limited_sorted]
        )

    async def _search(self, query: str, metadata: Dict[str, str]) -> Mem0SearchResult:
        """
        Search through user memories using semantic search.

        Args:
            query: Natural language search query
            metadata: Metadata to filter the search
        Returns:
            Mem0SearchResult containing list of matching memories

        Raises:
            Exception: If API request fails or returns unexpected format
        """
        search_url = f"{self.api_url}/search"

        request_data: Dict[str, str | Dict[str, str]] = {
            "query": query,
            "user_id": self.user_id,
        }
        if metadata:
            request_data["metadata"] = metadata

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    search_url,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Mem0 API request failed: status={response.status}, response={error_text}"
                        )
                        raise Exception(f"Mem0 API request failed with status {response.status}")

                    response_data = await response.json()

                    if "results" not in response_data:
                        logger.error(f"Unexpected Mem0 API response format: {response_data}")
                        raise Exception("Unexpected API response format: missing 'results' key")

                    # Parse response into structured data
                    memories = []
                    for result in response_data["results"]:
                        try:
                            memory = Mem0Memory(
                                id=result["id"],
                                memory=result["memory"],
                                hash=result["hash"],
                                metadata=result.get("metadata", {}),
                                score=float(result["score"]),
                                created_at=result["created_at"],
                                updated_at=result.get("updated_at"),
                                user_id=result["user_id"],
                            )
                            memories.append(memory)
                        except (KeyError, ValueError, TypeError) as e:
                            logger.exception(
                                f"Skipping invalid memory result: {result}, error: {e}"
                            )
                            continue

                    logger.info(f"Mem0 search returned {len(memories)} results for query: {query}")
                    return Mem0SearchResult(results=memories)

        except aiohttp.ClientError as e:
            logger.error(f"Mem0 API network error: {e}")
            traceback.print_exc()
            raise Exception(f"Network error communicating with Mem0 API: {e}")
        except Exception as e:
            logger.error(f"Mem0 search error: {e}")
            traceback.print_exc()
            raise
