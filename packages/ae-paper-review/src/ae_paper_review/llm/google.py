"""Google Gemini provider with native PDF and web search support."""

import logging
import os
from pathlib import Path
from typing import TypeVar

from google import genai  # type: ignore[import-untyped]
from google.genai import types  # type: ignore[import-untyped]
from pydantic import BaseModel
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import LLMProvider, Provider
from .token_tracking import TokenUsage

logger = logging.getLogger(__name__)


def _log_retry(retry_state: RetryCallState) -> None:
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Gemini API error (attempt %d/3), retrying in %.0fs: %s",
        retry_state.attempt_number,
        retry_state.next_action.sleep if retry_state.next_action else 0,
        exception,
    )


_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type(ValueError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    before_sleep=_log_retry,
    reraise=True,
)

T = TypeVar("T", bound=BaseModel)


class GooglePDFProvider(LLMProvider):
    """Google Gemini native PDF provider using the google-genai SDK."""

    _provider = Provider.GOOGLE

    def __init__(self, model: str, usage: TokenUsage) -> None:
        self._model = model
        self._usage = usage
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self._client = genai.Client(api_key=api_key)

    def upload_pdf(self, pdf_path: Path, filename: str) -> str:
        logger.info("Uploading PDF to Google Files API: %s", filename)
        uploaded_file = self._client.files.upload(
            file=str(pdf_path),
            config=types.UploadFileConfig(display_name=filename),
        )
        file_name = uploaded_file.name
        if file_name is None:
            raise ValueError("Google Files API returned no file name")
        logger.info("Uploaded PDF to Google, file_name=%s", file_name)
        return str(file_name)

    def delete_file(self, file_id: str) -> None:
        self._client.files.delete(name=file_id)
        logger.info("Deleted file %s from Google", file_id)

    @_RETRY_DECORATOR
    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
    ) -> T:
        contents = _build_contents(client=self._client, file_ids=file_ids, prompt=prompt)

        logger.info(
            "Invoking Gemini generate_content with %d PDF files (model=%s, schema=%s)",
            len(file_ids),
            self._model,
            schema_class.__name__,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", system_message)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                response_mime_type="application/json",
                response_schema=schema_class.model_json_schema(),
                temperature=temperature,
            ),
        )

        self._track_usage(response=response)

        if response.text:
            logger.debug("LLM_RESPONSE output:\n%s", response.text)
            return schema_class.model_validate_json(response.text)

        raise ValueError("Gemini returned no text content")

    @_RETRY_DECORATOR
    def web_search_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        max_searches: int,
    ) -> T:
        # Gemini doesn't support max_searches directly,
        # so we include it as guidance in the system message
        enhanced_system = (
            f"{system_message}\n\n" f"Limit your web searches to at most {max_searches} queries."
        )

        contents = _build_contents(client=self._client, file_ids=file_ids, prompt=prompt)

        logger.info(
            "Invoking Gemini with web search + %d PDF files (model=%s, schema=%s, max_searches=%d)",
            len(file_ids),
            self._model,
            schema_class.__name__,
            max_searches,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", enhanced_system)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=enhanced_system,
                response_mime_type="application/json",
                response_schema=schema_class.model_json_schema(),
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=temperature,
            ),
        )

        self._track_usage(response=response)

        if response.text:
            logger.debug("LLM_RESPONSE output:\n%s", response.text)
            return schema_class.model_validate_json(response.text)

        raise ValueError("Gemini returned no text content")

    def _track_usage(self, response: types.GenerateContentResponse) -> None:
        """Track token usage from Gemini response."""
        metadata = response.usage_metadata
        if metadata is None:
            logger.warning("Gemini response missing usage metadata (model=%s)", self._model)
            return

        total_input_tokens = metadata.prompt_token_count or 0
        output_tokens = metadata.candidates_token_count or 0
        cached_input_tokens = metadata.cached_content_token_count or 0
        # Gemini returns total input tokens (including cached).
        # Subtract to get non-cached tokens, matching Anthropic's convention
        # where input_tokens already excludes cache_read and cache_creation.
        non_cached_input_tokens = total_input_tokens - cached_input_tokens

        if total_input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "Gemini returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "Gemini token usage: input=%d (non-cached), cached=%d, output=%d (model=%s)",
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


def _build_contents(
    client: genai.Client,
    file_ids: list[str],
    prompt: str,
) -> list[types.File | str]:
    """Build contents list with file references and prompt text."""
    contents: list[types.File | str] = []
    for fid in file_ids:
        file_ref = client.files.get(name=fid)
        contents.append(file_ref)
    contents.append(prompt)
    return contents
