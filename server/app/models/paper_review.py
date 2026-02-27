"""
Paper review response models.

These are the Pydantic models used for API responses and service layer returns.
"""

from typing import List, Literal, Optional, Union

from ae_paper_review import Conference
from pydantic import BaseModel, Field

from app.services.database.paper_reviews import (
    ICLRReviewContent,
    ICMLReviewContent,
    NeurIPSReviewContent,
    PaperReviewBase,
    PreReviewAnalysis,
    ReviewContent,
)

TierLiteral = Literal["standard", "premium"]
ConferenceLiteral = Literal[Conference.NEURIPS_2025, Conference.ICLR_2025, Conference.ICML]


class TokenUsage(BaseModel):
    """Token usage summary for a paper review."""

    input_tokens: int = Field(..., description="Total input tokens used")
    cached_input_tokens: int = Field(..., description="Cached input tokens")
    cache_write_input_tokens: int = Field(..., description="Cache write input tokens")
    output_tokens: int = Field(..., description="Total output tokens used")


class ClarityIssue(BaseModel):
    """A specific clarity issue identified in the paper."""

    location: str = Field(
        ..., description="Where the issue occurs (e.g., 'Section 3.2', 'Figure 2')"
    )
    issue: str = Field(..., description="What is unclear, inconsistent, or misleading and why")


class NoveltySearchResultItem(BaseModel):
    """A single web search result from novelty search."""

    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    snippet: str = Field(..., description="Brief snippet from the search result")


class NoveltySearchResponse(BaseModel):
    """Results from novelty-focused web searches."""

    search_queries_used: List[str] = Field(..., description="Search queries executed")
    results: List[NoveltySearchResultItem] = Field(..., description="Relevant search results")
    summary: str = Field(..., description="Summary of prior work found")


class CitationCheckItemResponse(BaseModel):
    """A single citation verification result."""

    cited_text: str = Field(..., description="The citation claim being verified")
    found: bool = Field(..., description="Whether the cited work was found")
    url: str = Field(..., description="URL of the found work, or empty string")
    assessment: str = Field(
        ..., description="Assessment of whether the citation supports the claim"
    )


class CitationCheckResponse(BaseModel):
    """Results from citation verification web searches."""

    search_queries_used: List[str] = Field(..., description="Search queries executed")
    checks: List[CitationCheckItemResponse] = Field(..., description="Verification results")
    summary: str = Field(..., description="Summary of citation verification findings")


class MissingReferenceItemResponse(BaseModel):
    """A potentially missing reference identified via web search."""

    topic: str = Field(..., description="Topic area where references may be missing")
    missing_work: str = Field(..., description="Title and authors of the missing reference")
    url: str = Field(..., description="URL where the work was found")
    relevance: str = Field(..., description="Why this work should have been cited")


class MissingReferencesResponse(BaseModel):
    """Results from searching for important uncited related work."""

    search_queries_used: List[str] = Field(..., description="Search queries executed")
    missing_references: List[MissingReferenceItemResponse] = Field(
        ..., description="Potentially important uncited works"
    )
    summary: str = Field(..., description="Summary of gaps in related work coverage")


class PresentationIssueResponse(BaseModel):
    """A specific presentation issue found in the paper."""

    location: str = Field(..., description="Where the issue occurs")
    issue_type: str = Field(
        ..., description="Category: figure, table, notation, formatting, layout"
    )
    description: str = Field(..., description="What the problem is")


class PresentationCheckResponse(BaseModel):
    """Results from visual inspection of figures, tables, and notation."""

    issues: List[PresentationIssueResponse] = Field(..., description="Presentation issues found")
    summary: str = Field(..., description="Overall assessment of presentation quality")


class _ReviewBase(BaseModel):
    """Infrastructure fields shared across all conference review responses."""

    id: int
    status: str = Field(..., description="Review status: pending, processing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is failed")
    original_filename: str = Field(..., description="Original PDF filename")
    model: str = Field(..., description="Model used for review")
    tier: TierLiteral = Field(..., description="Review tier")
    created_at: str = Field(..., description="ISO timestamp of review creation")
    has_enough_credits: Optional[bool] = Field(
        None,
        description="Whether user had positive balance when review completed. NULL if still running.",
    )
    access_restricted: bool = Field(
        False,
        description="True if user cannot view full review details due to insufficient credits",
    )
    access_restricted_reason: Optional[str] = Field(
        None,
        description="Message explaining why access is restricted",
    )
    token_usage: Optional[TokenUsage] = Field(
        None, description="Token usage (null if not completed or restricted)"
    )
    cost_cents: Optional[int] = Field(
        None, description="Cost charged in cents (null if restricted)"
    )
    progress: float = Field(..., description="Review progress (0.0-1.0)")
    progress_step: str = Field(
        ..., description="Current step description (empty string when completed)"
    )
    novelty_search: Optional[NoveltySearchResponse] = Field(
        None, description="Novelty search results (null if restricted or not available)"
    )
    citation_check: Optional[CitationCheckResponse] = Field(
        None, description="Citation verification results (null if restricted or not available)"
    )
    missing_references: Optional[MissingReferencesResponse] = Field(
        None,
        description="Missing references results (null if restricted, not available, or standard tier)",
    )
    presentation_check: Optional[PresentationCheckResponse] = Field(
        None,
        description="Presentation check results (null if restricted, not available, or standard tier)",
    )


class NeurIPSPaperReviewDetail(_ReviewBase):
    """NeurIPS 2025 paper review response."""

    conference: Literal[Conference.NEURIPS_2025]
    summary: Optional[str] = None
    strengths_and_weaknesses: Optional[str] = None
    questions: Optional[List[str]] = None
    limitations: Optional[str] = None
    ethical_concerns: Optional[bool] = None
    ethical_concerns_explanation: str = ""
    clarity_issues: Optional[List[ClarityIssue]] = None
    quality: Optional[int] = None
    clarity: Optional[int] = None
    significance: Optional[int] = None
    originality: Optional[int] = None
    overall: Optional[int] = None
    confidence: Optional[int] = None
    decision: Optional[str] = None


class ICLRPaperReviewDetail(_ReviewBase):
    """ICLR 2025 paper review response."""

    conference: Literal[Conference.ICLR_2025]
    summary: Optional[str] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    limitations: Optional[str] = None
    ethical_concerns: Optional[bool] = None
    ethical_concerns_explanation: str = ""
    clarity_issues: Optional[List[ClarityIssue]] = None
    soundness: Optional[int] = None
    presentation: Optional[int] = None
    contribution: Optional[int] = None
    overall: Optional[int] = None
    confidence: Optional[int] = None
    decision: Optional[str] = None


class ICMLPaperReviewDetail(_ReviewBase):
    """ICML 2025 paper review response."""

    conference: Literal[Conference.ICML]
    summary: Optional[str] = None
    claims_and_evidence: Optional[str] = None
    relation_to_prior_work: Optional[str] = None
    other_aspects: Optional[str] = None
    questions: Optional[List[str]] = None
    ethical_issues: Optional[bool] = None
    ethical_issues_explanation: str = ""
    clarity_issues: Optional[List[ClarityIssue]] = None
    overall: Optional[int] = None
    decision: Optional[str] = None


AnyPaperReviewDetail = Union[NeurIPSPaperReviewDetail, ICLRPaperReviewDetail, ICMLPaperReviewDetail]

_ACCESS_RESTRICTED_REASON = "Your balance is negative. Add credits to view full review details."


def _build_analysis_kwargs(analysis: PreReviewAnalysis | None, access_restricted: bool) -> dict:
    """Build analysis keyword arguments for review detail models."""
    if access_restricted or analysis is None:
        return {
            "novelty_search": None,
            "citation_check": None,
            "missing_references": None,
            "presentation_check": None,
        }
    return {
        "novelty_search": (
            NoveltySearchResponse(**analysis.novelty_search)
            if analysis.novelty_search is not None
            else None
        ),
        "citation_check": (
            CitationCheckResponse(**analysis.citation_check)
            if analysis.citation_check is not None
            else None
        ),
        "missing_references": (
            MissingReferencesResponse(**analysis.missing_references)
            if analysis.missing_references is not None
            else None
        ),
        "presentation_check": (
            PresentationCheckResponse(**analysis.presentation_check)
            if analysis.presentation_check is not None
            else None
        ),
    }


def _common_kwargs(
    base: PaperReviewBase,
    token_usage: TokenUsage | None,
    cost_cents: int,
    analysis: PreReviewAnalysis | None,
) -> dict:
    access_restricted = base.has_enough_credits is False
    analysis_kwargs = _build_analysis_kwargs(analysis, access_restricted)
    return {
        "id": base.id,
        "status": base.status,
        "error_message": base.error_message,
        "original_filename": base.original_filename,
        "model": base.model,
        "tier": base.tier,
        "created_at": base.created_at.isoformat(),
        "has_enough_credits": base.has_enough_credits,
        "access_restricted": access_restricted,
        "access_restricted_reason": _ACCESS_RESTRICTED_REASON if access_restricted else None,
        "token_usage": None if access_restricted else token_usage,
        "cost_cents": None if access_restricted else cost_cents,
        "progress": base.progress,
        "progress_step": base.progress_step,
        **analysis_kwargs,
    }


def _build_neurips_detail(
    base: PaperReviewBase,
    content: NeurIPSReviewContent | None,
    token_usage: TokenUsage | None,
    cost_cents: int,
    analysis: PreReviewAnalysis | None,
) -> NeurIPSPaperReviewDetail:
    common = _common_kwargs(base, token_usage, cost_cents, analysis)
    visible = content if not common["access_restricted"] else None
    return NeurIPSPaperReviewDetail(
        **common,
        conference=Conference.NEURIPS_2025,
        summary=visible.summary if visible is not None else None,
        strengths_and_weaknesses=visible.strengths_and_weaknesses if visible is not None else None,
        questions=list(visible.questions) if visible is not None else None,
        limitations=visible.limitations if visible is not None else None,
        ethical_concerns=visible.ethical_concerns if visible is not None else None,
        ethical_concerns_explanation=(
            visible.ethical_concerns_explanation if visible is not None else ""
        ),
        clarity_issues=(
            [ClarityIssue(**ci) for ci in visible.clarity_issues] if visible is not None else None
        ),
        quality=visible.quality if visible is not None else None,
        clarity=visible.clarity if visible is not None else None,
        significance=visible.significance if visible is not None else None,
        originality=visible.originality if visible is not None else None,
        overall=visible.overall if visible is not None else None,
        confidence=visible.confidence if visible is not None else None,
        decision=visible.decision if visible is not None else None,
    )


def _build_iclr_detail(
    base: PaperReviewBase,
    content: ICLRReviewContent | None,
    token_usage: TokenUsage | None,
    cost_cents: int,
    analysis: PreReviewAnalysis | None,
) -> ICLRPaperReviewDetail:
    common = _common_kwargs(base, token_usage, cost_cents, analysis)
    visible = content if not common["access_restricted"] else None
    return ICLRPaperReviewDetail(
        **common,
        conference=Conference.ICLR_2025,
        summary=visible.summary if visible is not None else None,
        strengths=list(visible.strengths) if visible is not None else None,
        weaknesses=list(visible.weaknesses) if visible is not None else None,
        questions=list(visible.questions) if visible is not None else None,
        limitations=visible.limitations if visible is not None else None,
        ethical_concerns=visible.ethical_concerns if visible is not None else None,
        ethical_concerns_explanation=(
            visible.ethical_concerns_explanation if visible is not None else ""
        ),
        clarity_issues=(
            [ClarityIssue(**ci) for ci in visible.clarity_issues] if visible is not None else None
        ),
        soundness=visible.soundness if visible is not None else None,
        presentation=visible.presentation if visible is not None else None,
        contribution=visible.contribution if visible is not None else None,
        overall=visible.overall if visible is not None else None,
        confidence=visible.confidence if visible is not None else None,
        decision=visible.decision if visible is not None else None,
    )


def _build_icml_detail(
    base: PaperReviewBase,
    content: ICMLReviewContent | None,
    token_usage: TokenUsage | None,
    cost_cents: int,
    analysis: PreReviewAnalysis | None,
) -> ICMLPaperReviewDetail:
    common = _common_kwargs(base, token_usage, cost_cents, analysis)
    visible = content if not common["access_restricted"] else None
    return ICMLPaperReviewDetail(
        **common,
        conference=Conference.ICML,
        summary=visible.summary if visible is not None else None,
        claims_and_evidence=visible.claims_and_evidence if visible is not None else None,
        relation_to_prior_work=visible.relation_to_prior_work if visible is not None else None,
        other_aspects=visible.other_aspects if visible is not None else None,
        questions=list(visible.questions) if visible is not None else None,
        ethical_issues=visible.ethical_issues if visible is not None else None,
        ethical_issues_explanation=(
            visible.ethical_issues_explanation if visible is not None else ""
        ),
        clarity_issues=(
            [ClarityIssue(**ci) for ci in visible.clarity_issues] if visible is not None else None
        ),
        overall=visible.overall if visible is not None else None,
        decision=visible.decision if visible is not None else None,
    )


def build_review_detail(
    *,
    base: PaperReviewBase,
    content: ReviewContent | None,
    token_usage: TokenUsage | None,
    cost_cents: int,
    analysis: PreReviewAnalysis | None,
) -> AnyPaperReviewDetail | None:
    """Build the appropriate conference-specific review detail.

    Returns None if the conference is unknown.
    """
    if base.conference == Conference.NEURIPS_2025:
        neurips_content = content if isinstance(content, NeurIPSReviewContent) else None
        return _build_neurips_detail(base, neurips_content, token_usage, cost_cents, analysis)
    if base.conference == Conference.ICLR_2025:
        iclr_content = content if isinstance(content, ICLRReviewContent) else None
        return _build_iclr_detail(base, iclr_content, token_usage, cost_cents, analysis)
    if base.conference == Conference.ICML:
        icml_content = content if isinstance(content, ICMLReviewContent) else None
        return _build_icml_detail(base, icml_content, token_usage, cost_cents, analysis)
    return None
