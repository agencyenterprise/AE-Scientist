"""OpenAI provider using Responses API with native PDF and web search support."""

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from openai.types.responses import Response
from pydantic import BaseModel

from .base import LLMProvider, Provider
from .token_tracking import TokenUsage

logger = logging.getLogger(__name__)

# Suppress verbose debug logging from SDK clients
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

T = TypeVar("T", bound=BaseModel)


class OpenAIPDFProvider(LLMProvider):
    """OpenAI native PDF provider using Files API."""

    _provider = Provider.OPENAI

    def __init__(self, model: str, usage: TokenUsage) -> None:
        self._model = model
        self._usage = usage
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

    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
    ) -> T:
        # Build input with files and prompt
        input_content: list[dict[str, object]] = []
        for fid in file_ids:
            input_content.append({"type": "input_file", "file_id": fid})
        input_content.append({"type": "input_text", "text": prompt})

        logger.info(
            "Invoking OpenAI Responses API with %d PDF files (model=%s, schema=%s)",
            len(file_ids),
            self._model,
            schema_class.__name__,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", system_message)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        response = self._client.responses.create(  # type: ignore[call-overload]
            model=self._model,
            instructions=system_message,
            input=[{"role": "user", "content": input_content}],  # fmt: skip  # pyright: ignore[reportArgumentType]
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_class.__name__,
                    "schema": schema_class.model_json_schema(),
                    "strict": True,
                }
            },
            temperature=temperature,
        )

        self._track_usage(response=response)

        if response.output_text:
            logger.debug("LLM_RESPONSE output:\n%s", response.output_text)
            return schema_class.model_validate_json(response.output_text)

        raise ValueError("OpenAI Responses API returned no parsed content")

    def web_search_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        max_searches: int,
    ) -> T:
        # Note: OpenAI Responses API doesn't support max_searches directly,
        # so we include it as guidance in the system message
        enhanced_system = (
            f"{system_message}\n\n" f"Limit your web searches to at most {max_searches} queries."
        )

        # Build input with files and prompt
        input_content: list[dict[str, object]] = []
        for fid in file_ids:
            input_content.append({"type": "input_file", "file_id": fid})
        input_content.append({"type": "input_text", "text": prompt})

        logger.info(
            "Invoking OpenAI Responses API with web search + %d PDF files (model=%s, schema=%s, max_searches=%d)",
            len(file_ids),
            self._model,
            schema_class.__name__,
            max_searches,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", enhanced_system)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        # Use Responses API with web_search tool and structured output
        response = self._client.responses.create(  # type: ignore[call-overload]
            model=self._model,
            instructions=enhanced_system,
            input=[{"role": "user", "content": input_content}],  # fmt: skip  # pyright: ignore[reportArgumentType]
            tools=[{"type": "web_search"}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_class.__name__,
                    "schema": schema_class.model_json_schema(),
                    "strict": True,
                }
            },
            temperature=temperature,
        )

        self._track_usage(response=response)

        # Parse the structured output from response
        if response.output_text:
            logger.debug("LLM_RESPONSE output:\n%s", response.output_text)
            return schema_class.model_validate_json(response.output_text)

        raise ValueError("OpenAI Responses API returned no parsed content")

    def _track_usage(self, response: Response) -> None:
        """Track token usage from OpenAI Responses API."""
        if response.usage is None:
            logger.warning("OpenAI Responses API missing usage data (model=%s)", self._model)
            return

        resp_usage = response.usage
        total_input_tokens = resp_usage.input_tokens
        output_tokens = resp_usage.output_tokens
        cached_input_tokens = resp_usage.input_tokens_details.cached_tokens
        # OpenAI returns total input tokens (including cached).
        # Subtract to get non-cached tokens, matching Anthropic's convention
        # where input_tokens already excludes cache_read and cache_creation.
        non_cached_input_tokens = total_input_tokens - cached_input_tokens

        if total_input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "OpenAI returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "OpenAI Responses API token usage: input=%d (non-cached), cached=%d, output=%d (model=%s)",
            non_cached_input_tokens,
            cached_input_tokens,
            output_tokens,
            self._model,
        )

        self._usage.add(
            provider=self._provider.value,
            model=self._model,
            input_tokens=non_cached_input_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=0,
            output_tokens=output_tokens,
        )
