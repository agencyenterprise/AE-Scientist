"""Anthropic provider with native PDF and web search support."""

import logging
import os
import warnings
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from anthropic.types.beta.parsed_beta_message import ParsedBetaMessage
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
        "Anthropic API error (attempt %d/3), retrying in %.0fs: %s",
        retry_state.attempt_number,
        retry_state.next_action.sleep if retry_state.next_action else 0,
        exception,
    )


_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type((anthropic.InternalServerError, anthropic.APIConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    before_sleep=_log_retry,
    reraise=True,
)

# Suppress verbose debug logging from SDK clients
logging.getLogger("anthropic._base_client").setLevel(logging.WARNING)

T = TypeVar("T", bound=BaseModel)


class AnthropicPDFProvider(LLMProvider):
    """Anthropic native PDF provider using Files API beta."""

    _provider = Provider.ANTHROPIC

    def __init__(self, model: str, usage: TokenUsage) -> None:
        self._model = model
        self._usage = usage
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

    @_RETRY_DECORATOR
    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
    ) -> T:
        content_blocks = _build_content_blocks(file_ids=file_ids, prompt=prompt)
        messages = [{"role": "user", "content": content_blocks}]

        logger.info(
            "Invoking Anthropic beta messages with %d PDF files (model=%s, schema=%s)",
            len(file_ids),
            self._model,
            schema_class.__name__,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", system_message)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

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

        self._track_usage(response=response)

        if response.parsed_output is None:
            raise ValueError("Anthropic returned no parsed content")

        logger.debug(
            "LLM_RESPONSE output:\n%s",
            response.parsed_output.model_dump_json(indent=2),
        )
        return response.parsed_output

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
        content_blocks = _build_content_blocks(file_ids=file_ids, prompt=prompt)
        messages = [{"role": "user", "content": content_blocks}]

        logger.info(
            "Invoking Anthropic with web search + %d PDF files (model=%s, schema=%s, max_searches=%d)",
            len(file_ids),
            self._model,
            schema_class.__name__,
            max_searches,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", system_message)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

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
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": max_searches,
                    }
                ],
            )

        self._track_usage(response=response)

        if response.parsed_output is None:
            raise ValueError("Anthropic returned no parsed content")

        logger.debug(
            "LLM_RESPONSE output:\n%s",
            response.parsed_output.model_dump_json(indent=2),
        )
        return response.parsed_output

    def _track_usage(self, response: ParsedBetaMessage[Any]) -> None:
        """Track token usage from Anthropic response."""
        resp_usage = response.usage
        input_tokens = resp_usage.input_tokens
        output_tokens = resp_usage.output_tokens
        cache_read = resp_usage.cache_read_input_tokens or 0
        cache_write = resp_usage.cache_creation_input_tokens or 0

        if input_tokens == 0 and output_tokens == 0:
            logger.warning(
                "Anthropic returned zero tokens (model=%s) - possible tracking issue",
                self._model,
            )

        logger.info(
            "Anthropic token usage: input=%d, cache_read=%d, cache_write=%d, output=%d (model=%s)",
            input_tokens,
            cache_read,
            cache_write,
            output_tokens,
            self._model,
        )

        self._usage.add(
            provider=self._provider.value,
            model=self._model,
            input_tokens=input_tokens,
            cached_input_tokens=cache_read,
            cache_write_input_tokens=cache_write,
            output_tokens=output_tokens,
        )


def _build_content_blocks(file_ids: list[str], prompt: str) -> list[dict[str, object]]:
    """Build content blocks with PDF files and prompt.

    Places a cache_control breakpoint on the last document block so that
    the PDF prefix is cached across calls with different prompts.
    """
    content_blocks: list[dict[str, object]] = []
    for i, file_id in enumerate(file_ids):
        block: dict[str, object] = {
            "type": "document",
            "source": {"type": "file", "file_id": file_id},
        }
        is_last_document = i == len(file_ids) - 1
        if is_last_document:
            block["cache_control"] = {"type": "ephemeral"}
        content_blocks.append(block)
    content_blocks.append({"type": "text", "text": prompt})
    return content_blocks
