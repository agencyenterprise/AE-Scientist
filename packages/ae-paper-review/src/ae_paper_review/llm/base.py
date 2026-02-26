"""Base class for LLM providers with native PDF support."""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .token_tracking import TokenUsage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class Provider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    XAI = "xai"
    GOOGLE = "google"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    _usage: TokenUsage
    _model: str

    @abstractmethod
    def __init__(self, model: str, usage: TokenUsage) -> None:
        """Initialize the provider with model and usage tracker."""

    @abstractmethod
    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        """Upload a PDF and return the file_id."""

    @abstractmethod
    def delete_file(self, file_id: str) -> None:
        """Delete an uploaded file."""

    @abstractmethod
    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
    ) -> T:
        """Make a structured chat call with PDF files."""

    @abstractmethod
    def web_search_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        max_searches: int,
    ) -> T:
        """Make a structured chat call with PDF files and web search enabled.

        Args:
            file_ids: List of uploaded file IDs to include
            prompt: The user prompt
            system_message: System message for the model
            temperature: Sampling temperature
            schema_class: Pydantic model class for structured output
            max_searches: Maximum number of web searches allowed

        Returns:
            Parsed response matching schema_class
        """
