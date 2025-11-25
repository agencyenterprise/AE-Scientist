"""
Grok service for generating conversation summaries and ideas.

This module handles communication with xAI's Grok API to generate summaries
of conversations and transform them into structured research ideas.
Since Grok API is OpenAI-compatible, this service extends OpenAIService
and only overrides the client initialization with Grok-specific configuration.
"""

import logging
import os

from app.models import LLMModel
from app.services import SummarizerService
from app.services.openai_service import OpenAIService
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


SUPPORTED_MODELS = [
    LLMModel(
        id="grok-code-fast-1",
        provider="grok",
        label="Grok Code Fast 1",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=256_000,
    ),
    LLMModel(
        id="grok-4-0709",
        provider="grok",
        label="Grok 4 0709",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=256_000,
    ),
    LLMModel(
        id="grok-3",
        provider="grok",
        label="Grok 3",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=131_000,
    ),
    LLMModel(
        id="grok-3-mini",
        provider="grok",
        label="Grok 3 Mini",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=131_000,
    ),
]


class GrokService(OpenAIService):
    """Service for interacting with xAI's Grok API using OpenAI-compatible interface."""

    def __init__(self, summarizer_service: SummarizerService) -> None:
        """Initialize the Grok service."""
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable is required")

        # Initialize async OpenAI client with Grok-specific base URL
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.summarizer_service = summarizer_service
        logger.info("Grok service initialized with xAI API endpoint")

    def get_context_window_tokens(self, llm_model: str) -> int:
        for model in SUPPORTED_MODELS:
            if model.id == llm_model:
                return model.context_window_tokens
        raise ValueError(f"Unknown Grok model for context window: {llm_model}")
