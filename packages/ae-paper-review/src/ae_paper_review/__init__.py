"""ae-paper-review: Standalone paper review functionality for AI Scientist.

This package provides LLM and VLM-based paper review capabilities that can be
used independently of the full research pipeline.

Example usage:
    from ae_paper_review import perform_review, load_paper

    # Load paper from PDF
    paper_text = load_paper("paper.pdf")

    # Perform review using "provider:model" format (LangChain native format)
    result = perform_review(
        text=paper_text,
        model="anthropic:claude-sonnet-4-20250514",
        temperature=0.1,
        num_reviews_ensemble=3,
        num_reflections=2,
    )

    # Access review results
    print(f"Decision: {result.review.decision}")
    print(f"Overall Score: {result.review.overall}")
    print(f"Tokens used: {result.token_usage}")
"""

from .llm.token_tracking import TokenUsageDetail, TokenUsageSummary
from .llm_review import (
    ReviewProgressEvent,
    ReviewResult,
    get_review_fewshot_examples,
    load_paper,
    load_review,
    perform_review,
)
from .models import (
    FigureImageCaptionRefReview,
    ImageCaptionRefReview,
    ImageReview,
    ImageSelectionReview,
    ReviewResponseModel,
)
from .vlm_review import (
    detect_duplicate_figures,
    extract_abstract,
    extract_figure_screenshots,
    generate_vlm_img_cap_ref_review,
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
    "ImageCaptionRefReview",
    "ImageSelectionReview",
    "ImageReview",
    "FigureImageCaptionRefReview",
    # LLM Review
    "perform_review",
    "ReviewResult",
    "load_paper",
    "load_review",
    "get_review_fewshot_examples",
    "ReviewProgressEvent",
    # Token Usage
    "TokenUsageSummary",
    "TokenUsageDetail",
    # VLM Review
    "extract_figure_screenshots",
    "extract_abstract",
    "generate_vlm_img_cap_ref_review",
    "generate_vlm_img_review",
    "perform_imgs_cap_ref_review",
    "perform_imgs_cap_ref_review_selection",
    "detect_duplicate_figures",
]
