"""
LLM token usage models.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LlmTokenUsage(BaseModel):
    """Represents a record of LLM token usage."""

    conversation_id: int = Field(..., description="ID of the conversation")
    run_id: Optional[str] = Field(None, description="Research pipeline run ID, when available")
    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="LLM model name")
    input_tokens: int = Field(..., description="Number of input tokens")
    output_tokens: int = Field(..., description="Number of output tokens")


class LLMTokenUsageCost(LlmTokenUsage):
    """Represents a record of LLM token usage cost."""

    input_cost: float = Field(..., description="Cost of the LLM token usage for input tokens")
    output_cost: float = Field(..., description="Cost of the LLM token usage for output tokens")
