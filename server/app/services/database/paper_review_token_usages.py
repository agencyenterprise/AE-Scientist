"""
Database helpers for paper review token usages.
"""

from datetime import datetime
from typing import List, NamedTuple

from ae_paper_review import TokenUsageDetail
from psycopg.rows import dict_row

from .base import ConnectionProvider


class PaperReviewTokenUsage(NamedTuple):
    """Represents token usage for a paper review."""

    id: int
    paper_review_id: int
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    created_at: datetime


class PaperReviewTokenUsagesMixin(ConnectionProvider):
    """Database operations for paper review token usages."""

    async def insert_paper_review_token_usage(
        self,
        *,
        paper_review_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        cache_write_input_tokens: int,
        output_tokens: int,
    ) -> int:
        """Insert a token usage record and return its ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_review_token_usages
                        (paper_review_id, provider, model, input_tokens,
                         cached_input_tokens, cache_write_input_tokens, output_tokens)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        paper_review_id,
                        provider,
                        model,
                        input_tokens,
                        cached_input_tokens,
                        cache_write_input_tokens,
                        output_tokens,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to insert paper review token usage")
                return int(result["id"])

    async def insert_paper_review_token_usages_batch(
        self,
        *,
        paper_review_id: int,
        usages: List[TokenUsageDetail],
    ) -> None:
        """Insert multiple token usage records for a paper review.

        Args:
            paper_review_id: The paper review ID
            usages: List of TokenUsageDetail with provider, model, input_tokens,
                    cached_input_tokens, cache_write_input_tokens, output_tokens
        """
        if not usages:
            return

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                for usage in usages:
                    await cursor.execute(
                        """
                        INSERT INTO paper_review_token_usages
                            (paper_review_id, provider, model, input_tokens,
                             cached_input_tokens, cache_write_input_tokens, output_tokens)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            paper_review_id,
                            usage.provider,
                            usage.model,
                            usage.input_tokens,
                            usage.cached_input_tokens,
                            usage.cache_write_input_tokens,
                            usage.output_tokens,
                        ),
                    )

    async def get_token_usages_by_review_id(
        self, paper_review_id: int
    ) -> List[PaperReviewTokenUsage]:
        """Get all token usages for a paper review."""
        query = """
            SELECT id, paper_review_id, provider, model, input_tokens,
                   cached_input_tokens, cache_write_input_tokens, output_tokens, created_at
            FROM paper_review_token_usages
            WHERE paper_review_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (paper_review_id,))
                rows = await cursor.fetchall() or []
        return [PaperReviewTokenUsage(**row) for row in rows]

    async def get_total_token_usage_by_review_id(self, paper_review_id: int) -> dict:
        """Get aggregated token usage for a paper review."""
        query = """
            SELECT
                SUM(input_tokens) as input_tokens,
                SUM(cached_input_tokens) as cached_input_tokens,
                SUM(cache_write_input_tokens) as cache_write_input_tokens,
                SUM(output_tokens) as output_tokens
            FROM paper_review_token_usages
            WHERE paper_review_id = %s
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (paper_review_id,))
                row = await cursor.fetchone()
        if not row:
            return {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 0,
            }
        return {
            "input_tokens": row["input_tokens"] or 0,
            "cached_input_tokens": row["cached_input_tokens"] or 0,
            "cache_write_input_tokens": row["cache_write_input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
        }
