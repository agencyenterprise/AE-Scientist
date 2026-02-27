"""
Database helpers for standalone paper reviews.
"""

from datetime import datetime
from enum import Enum
from typing import NamedTuple

from ae_paper_review import Conference
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider


class PaperReviewStatus(str, Enum):
    """Status of a paper review."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaperReviewBase(NamedTuple):
    """Infrastructure fields for a paper review (shared across all conferences)."""

    id: int
    user_id: int
    original_filename: str
    s3_key: str | None
    model: str
    tier: str
    status: str
    error_message: str | None
    created_at: datetime
    progress: float
    progress_step: str
    conference: str | None
    has_enough_credits: bool | None = None


class NeurIPSReviewContent(NamedTuple):
    """NeurIPS-specific review content."""

    summary: str
    strengths_and_weaknesses: str
    questions: list
    limitations: str
    ethical_concerns: bool
    ethical_concerns_explanation: str
    clarity_issues: list
    quality: int
    clarity: int
    significance: int
    originality: int
    overall: int
    confidence: int
    decision: str


class ICLRReviewContent(NamedTuple):
    """ICLR-specific review content."""

    summary: str
    strengths: list
    weaknesses: list
    questions: list
    limitations: str
    ethical_concerns: bool
    ethical_concerns_explanation: str
    clarity_issues: list
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str


class ICMLReviewContent(NamedTuple):
    """ICML-specific review content."""

    summary: str
    claims_and_evidence: str
    relation_to_prior_work: str
    other_aspects: str
    questions: list
    ethical_issues: bool
    ethical_issues_explanation: str
    clarity_issues: list
    overall: int
    decision: str


ReviewContent = NeurIPSReviewContent | ICLRReviewContent | ICMLReviewContent


class PreReviewAnalysis(NamedTuple):
    """Pre-review analysis results (novelty search, citation check, etc.)."""

    novelty_search: dict | None
    citation_check: dict | None
    missing_references: dict | None
    presentation_check: dict | None


class PaperReviewListItem(NamedTuple):
    """Base fields plus summary/overall/decision for list views."""

    id: int
    user_id: int
    original_filename: str
    model: str
    tier: str
    status: str
    created_at: datetime
    has_enough_credits: bool | None
    progress: float
    progress_step: str
    conference: str | None
    summary: str | None
    overall: int | None
    decision: str | None


_NEURIPS_CONTENT_COLUMNS = """
    n.summary, n.strengths_and_weaknesses, n.questions, n.limitations,
    n.ethical_concerns, n.ethical_concerns_explanation, n.clarity_issues,
    n.quality, n.clarity, n.significance, n.originality, n.overall, n.confidence, n.decision
"""

_ICLR_CONTENT_COLUMNS = """
    i.summary, i.strengths, i.weaknesses, i.questions, i.limitations,
    i.ethical_concerns, i.ethical_concerns_explanation, i.clarity_issues,
    i.soundness, i.presentation, i.contribution, i.overall, i.confidence, i.decision
"""

_ICML_CONTENT_COLUMNS = """
    m.summary, m.claims_and_evidence, m.relation_to_prior_work, m.other_aspects,
    m.questions, m.ethical_issues, m.ethical_issues_explanation, m.clarity_issues,
    m.overall, m.decision
"""

_BASE_COLUMNS = """
    pr.id, pr.user_id, pr.original_filename, pr.s3_key, pr.model, pr.tier, pr.status,
    pr.error_message, pr.created_at, pr.progress, pr.progress_step, pr.conference,
    pr.has_enough_credits
"""


def _row_to_base(row: dict) -> PaperReviewBase:
    return PaperReviewBase(
        id=row["id"],
        user_id=row["user_id"],
        original_filename=row["original_filename"],
        s3_key=row["s3_key"],
        model=row["model"],
        tier=row["tier"],
        status=row["status"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        progress=row["progress"],
        progress_step=row["progress_step"],
        conference=row["conference"],
        has_enough_credits=row["has_enough_credits"],
    )


def _row_to_neurips_content(row: dict) -> NeurIPSReviewContent:
    return NeurIPSReviewContent(
        summary=row["summary"],
        strengths_and_weaknesses=row["strengths_and_weaknesses"],
        questions=row["questions"],
        limitations=row["limitations"],
        ethical_concerns=row["ethical_concerns"],
        ethical_concerns_explanation=row["ethical_concerns_explanation"],
        clarity_issues=row["clarity_issues"],
        quality=row["quality"],
        clarity=row["clarity"],
        significance=row["significance"],
        originality=row["originality"],
        overall=row["overall"],
        confidence=row["confidence"],
        decision=row["decision"],
    )


def _row_to_iclr_content(row: dict) -> ICLRReviewContent:
    return ICLRReviewContent(
        summary=row["summary"],
        strengths=row["strengths"],
        weaknesses=row["weaknesses"],
        questions=row["questions"],
        limitations=row["limitations"],
        ethical_concerns=row["ethical_concerns"],
        ethical_concerns_explanation=row["ethical_concerns_explanation"],
        clarity_issues=row["clarity_issues"],
        soundness=row["soundness"],
        presentation=row["presentation"],
        contribution=row["contribution"],
        overall=row["overall"],
        confidence=row["confidence"],
        decision=row["decision"],
    )


def _row_to_icml_content(row: dict) -> ICMLReviewContent:
    return ICMLReviewContent(
        summary=row["summary"],
        claims_and_evidence=row["claims_and_evidence"],
        relation_to_prior_work=row["relation_to_prior_work"],
        other_aspects=row["other_aspects"],
        questions=row["questions"],
        ethical_issues=row["ethical_issues"],
        ethical_issues_explanation=row["ethical_issues_explanation"],
        clarity_issues=row["clarity_issues"],
        overall=row["overall"],
        decision=row["decision"],
    )


def _row_to_content(row: dict, conference: Conference) -> ReviewContent:
    if conference == Conference.NEURIPS_2025:
        return _row_to_neurips_content(row)
    if conference == Conference.ICLR_2025:
        return _row_to_iclr_content(row)
    if conference == Conference.ICML:
        return _row_to_icml_content(row)
    raise ValueError(f"Unknown conference: {conference}")


class PaperReviewsMixin(ConnectionProvider):
    """Database operations for standalone paper reviews."""

    async def create_pending_paper_review(
        self,
        *,
        user_id: int,
        original_filename: str,
        s3_key: str,
        model: str,
        tier: str,
        conference: Conference,
    ) -> int:
        """Create a pending paper review and return its ID."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_reviews
                        (user_id, original_filename, s3_key, model, tier, status,
                         progress, progress_step, conference)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        original_filename,
                        s3_key,
                        model,
                        tier,
                        PaperReviewStatus.PENDING.value,
                        0.0,
                        "",
                        conference.value,
                    ),
                )
                result = await cursor.fetchone()
                if not result:
                    raise ValueError("Failed to create pending paper review")
                return int(result["id"])

    async def update_paper_review_status(
        self,
        review_id: int,
        status: PaperReviewStatus,
        error_message: str | None = None,
    ) -> None:
        """Update the status of a paper review."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET status = %s, error_message = %s
                    WHERE id = %s
                    """,
                    (status.value, error_message, review_id),
                )

    async def complete_paper_review(
        self,
        *,
        review_id: int,
        content: ReviewContent,
    ) -> None:
        """Insert conference-specific content and mark the review as completed."""
        async with self.aget_connection() as conn:
            if isinstance(content, NeurIPSReviewContent):
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO paper_review_neurips
                            (paper_review_id, summary, strengths_and_weaknesses, questions,
                             limitations, ethical_concerns, ethical_concerns_explanation,
                             clarity_issues, quality, clarity, significance, originality,
                             overall, confidence, decision)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            review_id,
                            content.summary,
                            content.strengths_and_weaknesses,
                            Jsonb(content.questions),
                            content.limitations,
                            content.ethical_concerns,
                            content.ethical_concerns_explanation,
                            Jsonb(content.clarity_issues),
                            content.quality,
                            content.clarity,
                            content.significance,
                            content.originality,
                            content.overall,
                            content.confidence,
                            content.decision,
                        ),
                    )
            elif isinstance(content, ICLRReviewContent):
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO paper_review_iclr
                            (paper_review_id, summary, strengths, weaknesses, questions,
                             limitations, ethical_concerns, ethical_concerns_explanation,
                             clarity_issues, soundness, presentation, contribution,
                             overall, confidence, decision)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            review_id,
                            content.summary,
                            Jsonb(content.strengths),
                            Jsonb(content.weaknesses),
                            Jsonb(content.questions),
                            content.limitations,
                            content.ethical_concerns,
                            content.ethical_concerns_explanation,
                            Jsonb(content.clarity_issues),
                            content.soundness,
                            content.presentation,
                            content.contribution,
                            content.overall,
                            content.confidence,
                            content.decision,
                        ),
                    )
            elif isinstance(content, ICMLReviewContent):
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO paper_review_icml
                            (paper_review_id, summary, claims_and_evidence,
                             relation_to_prior_work, other_aspects, questions,
                             ethical_issues, ethical_issues_explanation,
                             clarity_issues, overall, decision)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            review_id,
                            content.summary,
                            content.claims_and_evidence,
                            content.relation_to_prior_work,
                            content.other_aspects,
                            Jsonb(content.questions),
                            content.ethical_issues,
                            content.ethical_issues_explanation,
                            Jsonb(content.clarity_issues),
                            content.overall,
                            content.decision,
                        ),
                    )
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE paper_reviews SET status = %s WHERE id = %s",
                    (PaperReviewStatus.COMPLETED.value, review_id),
                )

    async def insert_pre_review_analysis(
        self,
        *,
        review_id: int,
        novelty_search: dict | None,
        citation_check: dict | None,
        missing_references: dict | None,
        presentation_check: dict | None,
    ) -> None:
        """Insert pre-review analysis results for a paper review."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO paper_review_analysis
                        (paper_review_id, novelty_search, citation_check,
                         missing_references, presentation_check)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        review_id,
                        Jsonb(novelty_search) if novelty_search is not None else None,
                        Jsonb(citation_check) if citation_check is not None else None,
                        Jsonb(missing_references) if missing_references is not None else None,
                        Jsonb(presentation_check) if presentation_check is not None else None,
                    ),
                )

    async def get_pre_review_analysis(self, review_id: int) -> PreReviewAnalysis | None:
        """Fetch pre-review analysis results for a paper review."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT novelty_search, citation_check, missing_references, presentation_check
                    FROM paper_review_analysis
                    WHERE paper_review_id = %s
                    """,
                    (review_id,),
                )
                row = await cursor.fetchone()

        if not row:
            return None
        return PreReviewAnalysis(
            novelty_search=row["novelty_search"],
            citation_check=row["citation_check"],
            missing_references=row["missing_references"],
            presentation_check=row["presentation_check"],
        )

    async def get_pending_reviews_by_user(self, user_id: int) -> list[PaperReviewBase]:
        """Get all pending or processing reviews for a user."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    f"""
                    SELECT {_BASE_COLUMNS}
                    FROM paper_reviews pr
                    WHERE pr.user_id = %s AND pr.status IN (%s, %s)
                    ORDER BY pr.created_at DESC
                    """,
                    (
                        user_id,
                        PaperReviewStatus.PENDING.value,
                        PaperReviewStatus.PROCESSING.value,
                    ),
                )
                rows = await cursor.fetchall() or []
        return [_row_to_base(row) for row in rows]

    async def get_paper_review_by_id(
        self, review_id: int
    ) -> tuple[PaperReviewBase, ReviewContent | None] | None:
        """Fetch a paper review with its conference-specific content."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    f"SELECT {_BASE_COLUMNS} FROM paper_reviews pr WHERE pr.id = %s",
                    (review_id,),
                )
                base_row = await cursor.fetchone()

        if not base_row:
            return None

        base = _row_to_base(base_row)

        if base.status != PaperReviewStatus.COMPLETED.value or not base.conference:
            return (base, None)

        content = await self._fetch_review_content(review_id, Conference(base.conference))
        return (base, content)

    async def _fetch_review_content(
        self, review_id: int, conference: Conference
    ) -> ReviewContent | None:
        """Fetch conference-specific content for a completed review."""
        if conference == Conference.NEURIPS_2025:
            query = f"SELECT {_NEURIPS_CONTENT_COLUMNS} FROM paper_review_neurips n WHERE n.paper_review_id = %s"
        elif conference == Conference.ICLR_2025:
            query = f"SELECT {_ICLR_CONTENT_COLUMNS} FROM paper_review_iclr i WHERE i.paper_review_id = %s"
        elif conference == Conference.ICML:
            query = f"SELECT {_ICML_CONTENT_COLUMNS} FROM paper_review_icml m WHERE m.paper_review_id = %s"

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (review_id,))
                row = await cursor.fetchone()

        if not row:
            return None
        return _row_to_content(row, conference)

    async def list_paper_reviews_by_user(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[PaperReviewListItem]:
        """List paper reviews for a user with summary fields from conference tables."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        pr.id, pr.user_id, pr.original_filename, pr.model, pr.tier, pr.status,
                        pr.created_at, pr.has_enough_credits, pr.progress,
                        pr.progress_step, pr.conference,
                        COALESCE(n.summary, i.summary, m.summary) AS summary,
                        COALESCE(n.overall, i.overall, m.overall) AS overall,
                        COALESCE(n.decision, i.decision, m.decision) AS decision
                    FROM paper_reviews pr
                    LEFT JOIN paper_review_neurips n ON n.paper_review_id = pr.id
                    LEFT JOIN paper_review_iclr i ON i.paper_review_id = pr.id
                    LEFT JOIN paper_review_icml m ON m.paper_review_id = pr.id
                    WHERE pr.user_id = %s
                    ORDER BY pr.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset),
                )
                rows = await cursor.fetchall() or []
        return [PaperReviewListItem(**row) for row in rows]

    async def mark_stale_reviews_as_failed(self, stale_threshold_minutes: int = 15) -> int:
        """Mark paper reviews stuck in pending/processing as failed."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET status = %s,
                        error_message = %s
                    WHERE status IN (%s, %s)
                      AND created_at < NOW() - (%s * INTERVAL '1 minute')
                    """,
                    (
                        PaperReviewStatus.FAILED.value,
                        "Review interrupted by server restart. Please try again.",
                        PaperReviewStatus.PENDING.value,
                        PaperReviewStatus.PROCESSING.value,
                        stale_threshold_minutes,
                    ),
                )
                return cursor.rowcount or 0

    async def set_paper_review_has_enough_credits(
        self, review_id: int, has_enough_credits: bool
    ) -> None:
        """Set the has_enough_credits flag for a paper review."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = %s
                    WHERE id = %s
                    """,
                    (has_enough_credits, review_id),
                )

    async def unlock_paper_reviews_for_user(self, user_id: int) -> int:
        """Unlock paper reviews for a user by setting has_enough_credits to TRUE."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = TRUE
                    WHERE user_id = %s
                      AND has_enough_credits = FALSE
                    """,
                    (user_id,),
                )
                return cursor.rowcount or 0

    async def lock_active_paper_reviews_for_user(self, user_id: int) -> int:
        """Lock active paper reviews for a user by setting has_enough_credits to FALSE."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET has_enough_credits = FALSE
                    WHERE user_id = %s
                      AND status IN ('pending', 'processing')
                    """,
                    (user_id,),
                )
                return cursor.rowcount or 0

    def update_paper_review_progress_sync(
        self,
        review_id: int,
        progress: float,
        progress_step: str,
    ) -> None:
        """Update the progress of a paper review (sync version for use from threads)."""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET progress = %s, progress_step = %s
                    WHERE id = %s
                    """,
                    (progress, progress_step, review_id),
                )

    async def clear_paper_review_progress(self, review_id: int) -> None:
        """Clear progress for a completed/failed review."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE paper_reviews
                    SET progress = 1.0, progress_step = ''
                    WHERE id = %s
                    """,
                    (review_id,),
                )
