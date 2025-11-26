"""
LLM Prompt-related Pydantic models.

This module contains all models related to LLM prompt management,
including CRUD operations and response handling.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class LLMPromptCreateRequest(BaseModel):
    """Request model for creating a new LLM prompt."""

    prompt_type: str = Field(..., description="Type of prompt", min_length=1)
    system_prompt: str = Field(..., description="The system prompt text", min_length=1)


class LLMPromptResponse(BaseModel):
    """Response model for LLM prompt operations."""

    system_prompt: str = Field(..., description="The system prompt text")
    is_default: bool = Field(..., description="Whether this is using the default prompt from code")


class LLMPromptDeleteRequest(BaseModel):
    """Request model for deleting/deactivating an LLM prompt."""

    prompt_type: str = Field(..., description="Type of prompt to deactivate", min_length=1)


class LLMPromptDeleteResponse(BaseModel):
    """Response model for LLM prompt deletion."""

    message: str = Field(..., description="Success or error message")


class LLMModel(BaseModel):
    """Model representing an LLM with ID and label."""

    id: str = Field(..., description="Model ID")
    provider: str = Field(..., description="LLM provider name")
    label: str = Field(..., description="Human-readable model label")
    supports_images: bool = Field(..., description="Whether the model supports images")
    supports_pdfs: bool = Field(..., description="Whether the model supports PDFs")
    context_window_tokens: int = Field(
        ..., description="Approximate maximum context window size in tokens"
    )


class LLMDefault(BaseModel):
    """Model for LLM default settings."""

    llm_provider: str = Field(..., description="LLM provider name", min_length=1)
    llm_model: str = Field(..., description="LLM model name", min_length=1)


class LLMDefaultsResponse(BaseModel):
    """Response model for getting LLM defaults."""

    current_default: LLMDefault = Field(..., description="Current default LLM settings")


class LLMDefaultsUpdateRequest(BaseModel):
    """Request model for updating LLM defaults."""

    llm_provider: str = Field(..., description="LLM provider name", min_length=1)
    llm_model: str = Field(..., description="LLM model name", min_length=1)


class LLMDefaultsUpdateResponse(BaseModel):
    """Response model for updating LLM defaults."""

    message: str = Field(..., description="Success message")
    updated_default: LLMDefault = Field(..., description="The updated default settings")


class LLMProvidersResponse(BaseModel):
    """Response model for getting available LLM providers."""

    providers: Dict[str, List[LLMModel]] = Field(
        ..., description="Available providers and their models"
    )
