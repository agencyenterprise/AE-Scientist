"""ae-paper-review: Standalone paper review functionality for AI Scientist.

This package provides LLM-based paper review capabilities that can be
used independently of the full research pipeline.

Each conference model matches the official review form structure:
- NeurIPS 2025: Combined strengths_and_weaknesses, 1-6 overall scale
- ICLR 2025: Separate strengths/weaknesses, soundness/presentation/contribution
- ICML 2025: Claims-based assessment, no confidence score

"""

from .llm.base import Provider
from .llm.token_tracking import TokenUsage, TokenUsageDetail, TokenUsageSummary
from .llm_review import (
    REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY,
    ReviewProgressEvent,
    ReviewResult,
    perform_ae_scientist_review,
    perform_review,
)
from .models import (
    AEScientistReviewModel,
    ClarityIssue,
    Conference,
    ICLRReviewModel,
    ICMLReviewModel,
    MissingReferencesResults,
    NeurIPSReviewModel,
    PresentationCheckResults,
    ReviewModel,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Provider
    "Provider",
    # Review models
    "AEScientistReviewModel",
    "ClarityIssue",
    "NeurIPSReviewModel",
    "ICLRReviewModel",
    "ICMLReviewModel",
    # Pipeline result models
    "MissingReferencesResults",
    "PresentationCheckResults",
    # Review
    "ReviewModel",
    "Conference",
    # LLM Review
    "REVIEW_RUBRIC_MENTIONS_REPRODUCIBILITY",
    "perform_review",
    "perform_ae_scientist_review",
    "ReviewResult",
    "ReviewProgressEvent",
    # Token Usage
    "TokenUsageSummary",
    "TokenUsage",
    "TokenUsageDetail",
]
