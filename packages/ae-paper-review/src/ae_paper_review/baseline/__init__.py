"""Baseline paper review (pre-prompt-tuning).

This subpackage provides the review pipeline from before prompt tuning
(commit 553991f in the ae-paper-reviewer repo). It uses the original prompts
and review models without ClarityIssue fields, missing_references, or
presentation_check pipeline steps.
"""

from .llm_review import perform_baseline_review
from .models import (
    BaselineICLRReviewModel,
    BaselineICMLReviewModel,
    BaselineNeurIPSReviewModel,
    BaselineReviewModel,
)

__all__ = [
    "perform_baseline_review",
    "BaselineNeurIPSReviewModel",
    "BaselineICLRReviewModel",
    "BaselineICMLReviewModel",
    "BaselineReviewModel",
]
