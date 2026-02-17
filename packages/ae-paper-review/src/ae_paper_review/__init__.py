"""ae-paper-review: Standalone paper review functionality for AI Scientist.

This package provides LLM and VLM-based paper review capabilities that can be
used independently of the full research pipeline.

Example usage:
    from pathlib import Path
    from ae_paper_review import perform_review

    result = perform_review(
        Path("paper.pdf"),
        model="anthropic:claude-sonnet-4-20250514",
        temperature=0.1,
        event_callback=lambda e: print(f"Progress: {e.progress:.0%}"),
        num_reflections=1,
        num_fs_examples=1,
        num_reviews_ensemble=3,
    )

    # Access review results
    print(f"Decision: {result.review.decision}")
    print(f"Overall Score: {result.review.overall}")
    print(f"Tokens used: {result.token_usage}")
"""

from .llm.token_tracking import TokenUsage, TokenUsageDetail
from .llm_review import (
    AbstractExtractionResult,
    ReviewProgressEvent,
    ReviewResult,
    extract_abstract_from_pdf,
    perform_review,
)
from .models import FigureImageCaptionRefReview, ReviewResponseModel
from .vlm_review import (
    DuplicateFiguresResult,
    FigureReviewResult,
    FigureSelectionReviewResult,
    ImageReviewResult,
    detect_duplicate_figures,
    generate_vlm_img_review,
    perform_imgs_cap_ref_review,
    perform_imgs_cap_ref_review_selection,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Models
    "ReviewResponseModel",
    "FigureImageCaptionRefReview",
    # LLM Review
    "perform_review",
    "ReviewResult",
    "ReviewProgressEvent",
    "extract_abstract_from_pdf",
    "AbstractExtractionResult",
    # Token Usage
    "TokenUsage",
    "TokenUsageDetail",
    # VLM Review
    "generate_vlm_img_review",
    "perform_imgs_cap_ref_review",
    "perform_imgs_cap_ref_review_selection",
    "detect_duplicate_figures",
    "FigureReviewResult",
    "FigureSelectionReviewResult",
    "DuplicateFiguresResult",
    "ImageReviewResult",
]
