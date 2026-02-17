"""Pydantic models for paper metadata."""

from datetime import datetime
from enum import Enum
from typing import NamedTuple

from pydantic import BaseModel, Field


class Conference(str, Enum):
    """Supported conference venues."""

    ICLR = "ICLR"
    NEURIPS = "NeurIPS"
    ICML = "ICML"


class PresentationTier(str, Enum):
    """Presentation tier / acceptance type."""

    ORAL = "oral"
    SPOTLIGHT = "spotlight"
    POSTER = "poster"
    BEST_PAPER = "best_paper"
    REJECT = "reject"
    UNKNOWN = "unknown"


class SampleCategory(str, Enum):
    """Whether paper was sampled randomly or as top-tier."""

    RANDOM = "random"
    TOP_TIER = "top_tier"


class ReviewerScore(NamedTuple):
    """Individual reviewer score."""

    reviewer_id: str
    score: float
    confidence: float


class PaperMetadata(BaseModel):
    """Metadata for a sourced paper."""

    paper_id: str = Field(description="OpenReview paper ID")
    title: str = Field(description="Paper title")
    conference: Conference = Field(description="Conference venue")
    year: int = Field(description="Conference year")
    venue_id: str = Field(description="Full OpenReview venue ID")
    reviewer_scores: list[tuple[str, float, float]] = Field(
        description="List of (reviewer_id, score, confidence) tuples"
    )
    average_score: float = Field(description="Average reviewer score")
    decision: str = Field(description="Final decision string")
    presentation_tier: PresentationTier = Field(description="Presentation tier")
    sample_category: SampleCategory = Field(description="Whether random or top-tier sample")
    pdf_url: str = Field(description="URL to download PDF")
    pdf_path: str = Field(description="Local path to downloaded PDF")
    sourced_at: datetime = Field(description="When paper was sourced")


class SourcingConfig(BaseModel):
    """Configuration for paper sourcing run."""

    conferences: list[Conference] = Field(description="Conferences to source from")
    years: list[int] = Field(description="Years to source")
    papers_per_conference: int = Field(description="Total papers per conference")
    top_tier_per_conference: int = Field(description="Top-tier papers per conference")
    seed: int = Field(description="Random seed for reproducibility")


class SourcingResult(BaseModel):
    """Result of a sourcing run."""

    config: SourcingConfig = Field(description="Config used for sourcing")
    papers: list[PaperMetadata] = Field(description="Sourced papers")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")
