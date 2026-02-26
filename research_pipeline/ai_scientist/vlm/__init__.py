"""VLM-based figure review for AI Scientist papers."""

from .models import FigureImageCaptionRefReview, ImageCaptionRefReview, ImageReview
from .review import (
    AbstractExtractionResult,
    DuplicateFiguresResult,
    FigureReviewResult,
    FigureSelectionReviewResult,
    ImageReviewResult,
    detect_duplicate_figures,
    extract_abstract_from_pdf,
    generate_vlm_img_review,
    perform_imgs_cap_ref_review,
    perform_imgs_cap_ref_review_selection,
)

__all__ = [
    "AbstractExtractionResult",
    "FigureImageCaptionRefReview",
    "ImageCaptionRefReview",
    "ImageReview",
    "FigureReviewResult",
    "FigureSelectionReviewResult",
    "DuplicateFiguresResult",
    "ImageReviewResult",
    "detect_duplicate_figures",
    "extract_abstract_from_pdf",
    "generate_vlm_img_review",
    "perform_imgs_cap_ref_review",
    "perform_imgs_cap_ref_review_selection",
]
