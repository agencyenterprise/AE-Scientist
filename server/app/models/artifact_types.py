"""Artifact type enum for research pipeline runs."""

from enum import Enum


class ArtifactType(str, Enum):
    """Supported artifact types for research pipeline runs."""

    PLOT = "plot"
    PAPER_PDF = "paper_pdf"
    LATEX_ARCHIVE = "latex_archive"
    WORKSPACE_ARCHIVE = "workspace_archive"
    LLM_REVIEW = "llm_review"
    RUN_LOG = "run_log"
    RUN_CONFIG = "run_config"
    COMMIT_HASH = "commit_hash"
