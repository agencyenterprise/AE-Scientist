"""
Database helpers for research pipeline VLM figure reviews.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider


class VlmFigureReview(NamedTuple):
    id: int
    run_id: str
    figure_name: str
    img_description: str
    img_review: str
    caption_review: str
    figrefs_review: str
    source_path: Optional[str]
    created_at: datetime


class ResearchPipelineVlmFigureReviewsMixin(ConnectionProvider):
    """Helpers to read and write VLM figure review data stored in rp_vlm_figure_reviews."""

    async def insert_vlm_figure_reviews(
        self,
        *,
        run_id: str,
        reviews: List[dict],
        created_at: Optional[datetime] = None,
    ) -> List[int]:
        """Insert multiple VLM figure reviews and return their IDs.

        Args:
            run_id: The run ID
            reviews: List of dicts with keys: figure_name, img_description, img_review,
                     caption_review, figrefs_review, source_path (optional)
            created_at: Timestamp for all reviews (defaults to now)

        Returns:
            List of inserted review IDs
        """
        if created_at is None:
            created_at = datetime.now()

        if not reviews:
            return []

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                placeholders = []
                flat_values = []
                for i, review in enumerate(reviews):
                    offset = i * 8
                    placeholders.append(
                        f"(${offset+1}, ${offset+2}, ${offset+3}, ${offset+4}, "
                        f"${offset+5}, ${offset+6}, ${offset+7}, ${offset+8})"
                    )
                    flat_values.extend(
                        [
                            run_id,
                            review["figure_name"],
                            review["img_description"],
                            review["img_review"],
                            review["caption_review"],
                            review["figrefs_review"],
                            review.get("source_path"),
                            created_at,
                        ]
                    )

                query = f"""
                    INSERT INTO rp_vlm_figure_reviews
                        (run_id, figure_name, img_description, img_review, caption_review,
                         figrefs_review, source_path, created_at)
                    VALUES {', '.join(placeholders)}
                    RETURNING id
                """

                await cursor.execute(query, flat_values)
                results = await cursor.fetchall()
                if not results:
                    raise ValueError("Failed to insert VLM figure reviews")
                return [int(row["id"]) for row in results]

    async def list_vlm_figure_reviews(self, run_id: str) -> List[VlmFigureReview]:
        """Fetch all VLM figure reviews for a run."""
        query = """
            SELECT id, run_id, figure_name, img_description, img_review, caption_review,
                   figrefs_review, source_path, created_at
            FROM rp_vlm_figure_reviews
            WHERE run_id = %s
            ORDER BY created_at ASC
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                rows = await cursor.fetchall() or []
        return [VlmFigureReview(**row) for row in rows]
