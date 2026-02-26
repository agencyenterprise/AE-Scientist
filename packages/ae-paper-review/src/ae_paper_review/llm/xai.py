"""xAI provider with native PDF and web search support."""

import logging
import os
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from xai_sdk import Client as XAIClient  # type: ignore[import-untyped]
from xai_sdk.chat import Response as XAIResponse  # type: ignore[import-untyped]
from xai_sdk.chat import file, system, user
from xai_sdk.tools import web_search  # type: ignore[import-untyped]

from .base import LLMProvider, Provider
from .token_tracking import TokenUsage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class XAIPDFProvider(LLMProvider):
    """xAI native PDF provider using xai_sdk.

    Uses native structured outputs via chat.parse() for grok-4 family models.
    """

    _provider = Provider.XAI

    def __init__(self, model: str, usage: TokenUsage) -> None:
        self._model = model
        self._usage = usage
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

    def structured_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
    ) -> T:
        chat = self._client.chat.create(model=self._model, temperature=temperature)
        chat.append(system(system_message))

        # Attach all files to the user message
        attachments = [file(fid) for fid in file_ids]
        chat.append(user(prompt, *attachments))

        logger.info(
            "Invoking xAI chat with %d PDF files (model=%s, schema=%s)",
            len(file_ids),
            self._model,
            schema_class.__name__,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", system_message)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        response, parsed = chat.parse(shape=schema_class)

        self._track_usage(response=response)

        logger.debug("LLM_RESPONSE output:\n%s", parsed.model_dump_json(indent=2))
        return parsed  # type: ignore[no-any-return]

    def web_search_chat(
        self,
        file_ids: list[str],
        prompt: str,
        system_message: str,
        temperature: float,
        schema_class: type[T],
        max_searches: int,
    ) -> T:
        # Note: xAI doesn't support max_searches directly,
        # so we include it as guidance in the system message
        enhanced_system = (
            f"{system_message}\n\n" f"Limit your web searches to at most {max_searches} queries."
        )

        chat = self._client.chat.create(
            model=self._model,
            temperature=temperature,
            tools=[web_search()],
        )
        chat.append(system(enhanced_system))

        # Attach all files to the user message
        attachments = [file(fid) for fid in file_ids]
        chat.append(user(prompt, *attachments))

        logger.info(
            "Invoking xAI chat with web search + %d PDF files (model=%s, schema=%s, max_searches=%d)",
            len(file_ids),
            self._model,
            schema_class.__name__,
            max_searches,
        )
        logger.debug("LLM_REQUEST system_message:\n%s", enhanced_system)
        logger.debug("LLM_REQUEST prompt:\n%s", prompt)

        response, parsed = chat.parse(shape=schema_class)

        self._track_usage(response=response)

        logger.debug("LLM_RESPONSE output:\n%s", parsed.model_dump_json(indent=2))
        return parsed  # type: ignore[no-any-return]

    def _track_usage(self, response: XAIResponse) -> None:
        """Track token usage from xAI response.

        The xai_sdk is untyped, so we access usage via the proto attribute.
        """
        input_tokens = 0
        output_tokens = 0
        cached_input_tokens = 0

        # xAI SDK stores usage in response.proto.usage
        proto: Any = response.proto
        if proto is not None and proto.usage is not None:
            proto_usage = proto.usage
            input_tokens = proto_usage.prompt_tokens or 0
            output_tokens = proto_usage.completion_tokens or 0
        else:
            logger.warning("xAI response missing usage data (model=%s)", self._model)

        if input_tokens == 0 and output_tokens == 0:
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

        self._usage.add(
            provider=self._provider.value,
            model=self._model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=0,
            output_tokens=output_tokens,
        )
