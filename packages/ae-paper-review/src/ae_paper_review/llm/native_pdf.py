"""Native PDF handling using provider SDKs directly.

All providers use their native SDKs for file-based PDF chat:
- Anthropic: Files API with beta headers
- OpenAI: Files API with responses API
- xAI: xai_sdk

This module provides a unified interface for all providers.
"""

import logging
import os
import warnings
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import TypeVar

import anthropic
from openai import OpenAI
from pydantic import BaseModel
from xai_sdk import Client as XAIClient  # type: ignore[import-untyped]
from xai_sdk.chat import file, system, user  # type: ignore[import-untyped]

from .token_tracking import TokenUsage

logger = logging.getLogger(__name__)

# Prefix for fewshot files to identify them when listing
FEWSHOT_FILE_PREFIX = "ae_fewshot_"

# Suppress verbose debug logging from SDK clients that logs full request bodies (including PDFs)
logging.getLogger("anthropic._base_client").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

T = TypeVar("T", bound=BaseModel)


class NativePDFProvider(ABC):
    """Abstract base class for native PDF providers."""

    @abstractmethod
    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        """Upload a PDF and return the file_id."""

    @abstractmethod
    def delete_file(self, file_id: str) -> None:
        """Delete an uploaded file."""

    @abstractmethod
    def get_or_upload_fewshot(self, pdf_path: Path, filename: str) -> str:
        """Get existing fewshot file or upload if not found.

        Fewshot files are cached across calls and never deleted.
        Uses a class-level cache and checks the provider's file listing.

        Args:
            pdf_path: Path to the PDF file
            filename: Original filename (will be prefixed with ae_fewshot_)

        Returns:
            file_id of the existing or newly uploaded file
        """

    @abstractmethod
    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        usage: TokenUsage,
    ) -> T:
        """Make a structured chat call with PDF files."""


class AnthropicPDFProvider(NativePDFProvider):
    """Anthropic native PDF provider using Files API beta."""

    # Class-level cache for fewshot file IDs (shared across instances)
    _fewshot_cache: dict[str, str] = {}

    def __init__(self, model: str) -> None:
        self._model = model.split(":", 1)[1] if ":" in model else model
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self._client = anthropic.Anthropic(api_key=api_key)

    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        pdf_bytes = pdf_path.read_bytes()
        logger.info("Uploading PDF to Anthropic Files API: %s", filename)
        response = self._client.beta.files.upload(
            file=(filename, pdf_bytes, "application/pdf"),
        )
        logger.info("Uploaded PDF to Anthropic, file_id=%s", response.id)
        return response.id

    def delete_file(self, file_id: str) -> None:
        self._client.beta.files.delete(file_id=file_id)
        logger.info("Deleted file %s from Anthropic", file_id)

    def get_or_upload_fewshot(self, pdf_path: Path, filename: str) -> str:
        prefixed_filename = f"{FEWSHOT_FILE_PREFIX}{filename}"

        # Check class-level cache first
        if prefixed_filename in AnthropicPDFProvider._fewshot_cache:
            file_id = AnthropicPDFProvider._fewshot_cache[prefixed_filename]
            logger.info(
                "Using cached Anthropic fewshot file_id=%s for %s", file_id, prefixed_filename
            )
            return file_id

        # Check if file already exists in Anthropic
        logger.info("Checking Anthropic for existing fewshot file: %s", prefixed_filename)
        files = self._client.beta.files.list(betas=["files-api-2025-04-14"])
        matching = [f for f in files.data if f.filename == prefixed_filename]

        if matching:
            file_id = matching[0].id
            logger.info(
                "Found existing Anthropic fewshot file_id=%s for %s", file_id, prefixed_filename
            )
            AnthropicPDFProvider._fewshot_cache[prefixed_filename] = file_id
            return file_id

        # Upload new file
        file_id = self.upload_pdf(pdf_path=pdf_path, filename=prefixed_filename)
        AnthropicPDFProvider._fewshot_cache[prefixed_filename] = file_id
        logger.info("Uploaded new Anthropic fewshot file_id=%s for %s", file_id, prefixed_filename)
        return file_id

    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        usage: TokenUsage,
    ) -> T:
        # Build content blocks with all PDF files
        content_blocks: list[dict] = []  # type: ignore[type-arg]
        for file_id in file_ids:
            content_blocks.append(
                {
                    "type": "document",
                    "source": {"type": "file", "file_id": file_id},
                }
            )
        content_blocks.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content_blocks}]

        logger.info(
            "Invoking Anthropic beta messages with %d PDF files (model=%s)",
            len(file_ids),
            self._model,
        )
        # Suppress deprecation warning for output_format (SDK recommends output_config
        # but .parse() with output_format gives cleaner Pydantic integration)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            response = self._client.beta.messages.parse(
                model=self._model,
                max_tokens=8192,
                temperature=temperature,
                system=system_message,
                messages=messages,  # type: ignore[arg-type]
                betas=["files-api-2025-04-14"],
                output_format=schema_class,
            )

        # Track token usage
        if not response.usage:
            logger.warning("Anthropic response missing usage data (model=%s)", self._model)
            input_tokens = 0
            output_tokens = 0
            cached_input_tokens = 0
        else:
            input_tokens = response.usage.input_tokens or 0
            output_tokens = response.usage.output_tokens or 0
            cached_input_tokens = 0
            if hasattr(response.usage, "cache_read_input_tokens"):
                cached_input_tokens = response.usage.cache_read_input_tokens or 0

        if input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "Anthropic returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "Anthropic token usage: input=%d, cached=%d, output=%d (model=%s)",
            input_tokens,
            cached_input_tokens,
            output_tokens,
            self._model,
        )

        usage.add(
            model=f"anthropic:{self._model}",
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )

        # Get parsed output directly
        if response.parsed_output is None:
            raise ValueError("Anthropic returned no parsed content")

        return response.parsed_output


class XAIPDFProvider(NativePDFProvider):
    """xAI native PDF provider using xai_sdk.

    Uses native structured outputs via chat.parse() for grok-4 family models.
    """

    # Class-level cache for fewshot file IDs (shared across instances)
    _fewshot_cache: dict[str, str] = {}

    def __init__(self, model: str) -> None:
        self._model = model.split(":", 1)[1] if ":" in model else model
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable is required")
        self._client = XAIClient(api_key=api_key)

    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        pdf_bytes = pdf_path.read_bytes()
        logger.info("Uploading PDF to xAI Files API: %s", filename)
        response = self._client.files.upload(pdf_bytes, filename=filename)
        file_id: str = response.id
        logger.info("Uploaded PDF to xAI, file_id=%s", file_id)
        return file_id

    def delete_file(self, file_id: str) -> None:
        self._client.files.delete(file_id)
        logger.info("Deleted file %s from xAI", file_id)

    def get_or_upload_fewshot(self, pdf_path: Path, filename: str) -> str:
        prefixed_filename = f"{FEWSHOT_FILE_PREFIX}{filename}"

        # Check class-level cache first
        if prefixed_filename in XAIPDFProvider._fewshot_cache:
            cached_file_id = XAIPDFProvider._fewshot_cache[prefixed_filename]
            logger.info(
                "Using cached xAI fewshot file_id=%s for %s", cached_file_id, prefixed_filename
            )
            return cached_file_id

        # Check if file already exists in xAI
        logger.info("Checking xAI for existing fewshot file: %s", prefixed_filename)
        files_response = self._client.files.list()
        matching = [f for f in files_response.data if f.filename == prefixed_filename]

        if matching:
            file_id: str = matching[0].id
            logger.info("Found existing xAI fewshot file_id=%s for %s", file_id, prefixed_filename)
            XAIPDFProvider._fewshot_cache[prefixed_filename] = file_id
            return file_id

        # Upload new file
        file_id = self.upload_pdf(pdf_path=pdf_path, filename=prefixed_filename)
        XAIPDFProvider._fewshot_cache[prefixed_filename] = file_id
        logger.info("Uploaded new xAI fewshot file_id=%s for %s", file_id, prefixed_filename)
        return file_id

    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        usage: TokenUsage,
    ) -> T:
        chat = self._client.chat.create(model=self._model, temperature=temperature)
        chat.append(system(system_message))

        # Attach all files to the user message
        attachments = [file(fid) for fid in file_ids]
        chat.append(user(prompt, *attachments))

        logger.info("Invoking xAI chat with %d PDF files (model=%s)", len(file_ids), self._model)
        response, parsed = chat.parse(shape=schema_class)

        # Track token usage
        input_tokens = 0
        output_tokens = 0
        cached_input_tokens = 0
        usage_extracted = False
        try:
            if hasattr(response, "usage") and response.usage is not None:
                resp_usage = response.usage
                input_tokens = getattr(resp_usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(resp_usage, "completion_tokens", 0) or 0
                if hasattr(resp_usage, "prompt_tokens_details"):
                    details = getattr(resp_usage, "prompt_tokens_details", None)
                    if details:
                        cached_input_tokens = getattr(details, "cached_tokens", 0) or 0
                usage_extracted = True
            elif hasattr(response, "proto") and hasattr(response.proto, "usage"):
                proto_usage = response.proto.usage
                input_tokens = getattr(proto_usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(proto_usage, "completion_tokens", 0) or 0
                usage_extracted = True
            else:
                logger.warning("xAI response missing usage data (model=%s)", self._model)
        except Exception as exc:
            logger.warning("Could not extract token usage from xAI response: %s", exc)

        if usage_extracted and input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "xAI returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "xAI token usage: input=%d, cached=%d, output=%d (model=%s)",
            input_tokens,
            cached_input_tokens,
            output_tokens,
            self._model,
        )

        usage.add(
            model=f"xai:{self._model}",
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )

        return parsed  # type: ignore[no-any-return]


class OpenAIPDFProvider(NativePDFProvider):
    """OpenAI native PDF provider using Files API."""

    # Class-level cache for fewshot file IDs (shared across instances)
    _fewshot_cache: dict[str, str] = {}

    def __init__(self, model: str) -> None:
        self._model = model.split(":", 1)[1] if ":" in model else model
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self._client = OpenAI(api_key=api_key)

    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        pdf_bytes = pdf_path.read_bytes()
        file_obj = BytesIO(pdf_bytes)
        file_obj.name = filename
        logger.info("Uploading PDF to OpenAI Files API: %s", filename)
        response = self._client.files.create(
            file=file_obj,
            purpose="user_data",
        )
        logger.info("Uploaded PDF to OpenAI, file_id=%s", response.id)
        return response.id

    def delete_file(self, file_id: str) -> None:
        self._client.files.delete(file_id=file_id)
        logger.info("Deleted file %s from OpenAI", file_id)

    def get_or_upload_fewshot(self, pdf_path: Path, filename: str) -> str:
        prefixed_filename = f"{FEWSHOT_FILE_PREFIX}{filename}"

        # Check class-level cache first
        if prefixed_filename in OpenAIPDFProvider._fewshot_cache:
            file_id = OpenAIPDFProvider._fewshot_cache[prefixed_filename]
            logger.info("Using cached OpenAI fewshot file_id=%s for %s", file_id, prefixed_filename)
            return file_id

        # Check if file already exists in OpenAI
        logger.info("Checking OpenAI for existing fewshot file: %s", prefixed_filename)
        files = self._client.files.list()
        matching = [f for f in files.data if f.filename == prefixed_filename]

        if matching:
            file_id = matching[0].id
            logger.info(
                "Found existing OpenAI fewshot file_id=%s for %s", file_id, prefixed_filename
            )
            OpenAIPDFProvider._fewshot_cache[prefixed_filename] = file_id
            return file_id

        # Upload new file
        file_id = self.upload_pdf(pdf_path=pdf_path, filename=prefixed_filename)
        OpenAIPDFProvider._fewshot_cache[prefixed_filename] = file_id
        logger.info("Uploaded new OpenAI fewshot file_id=%s for %s", file_id, prefixed_filename)
        return file_id

    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        usage: TokenUsage,
    ) -> T:
        # Build content blocks with all PDF files
        content_blocks: list[dict] = []  # type: ignore[type-arg]
        for file_id in file_ids:
            content_blocks.append(
                {
                    "type": "file",
                    "file": {"file_id": file_id},
                }
            )
        content_blocks.append({"type": "text", "text": prompt})

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": content_blocks},
        ]

        logger.info(
            "Invoking OpenAI chat completions with %d PDF files (model=%s)",
            len(file_ids),
            self._model,
        )
        response = self._client.beta.chat.completions.parse(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            response_format=schema_class,
        )

        # Track token usage
        input_tokens = 0
        output_tokens = 0
        cached_input_tokens = 0
        if response.usage:
            input_tokens = response.usage.prompt_tokens or 0
            output_tokens = response.usage.completion_tokens or 0
            if (
                hasattr(response.usage, "prompt_tokens_details")
                and response.usage.prompt_tokens_details
            ):
                cached_input_tokens = (
                    getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
                )
        else:
            logger.warning("OpenAI response missing usage data (model=%s)", self._model)

        if input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "OpenAI returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "OpenAI token usage: input=%d, cached=%d, output=%d (model=%s)",
            input_tokens,
            cached_input_tokens,
            output_tokens,
            self._model,
        )

        usage.add(
            model=f"openai:{self._model}",
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )

        # Extract parsed content from response
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("OpenAI returned no parsed content")

        return parsed


def get_provider(model: str) -> NativePDFProvider:
    """Get the PDF provider for a model.

    Args:
        model: Model in "provider:model" format

    Returns:
        NativePDFProvider instance

    Raises:
        ValueError: If the provider is not supported
    """
    provider_name = model.split(":")[0].lower() if ":" in model else ""

    if provider_name == "anthropic":
        return AnthropicPDFProvider(model=model)
    elif provider_name == "xai":
        return XAIPDFProvider(model=model)
    elif provider_name == "openai":
        return OpenAIPDFProvider(model=model)
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")
