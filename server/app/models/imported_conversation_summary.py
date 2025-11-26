"""
Imported conversation summary Pydantic models.

This module contains all models related to imported conversation summary.
"""

from pydantic import BaseModel, Field


class ImportedConversationSummaryUpdate(BaseModel):
    """Data required to update a conversation summary."""

    summary: str = Field(..., description="Updated summary text", min_length=1)
