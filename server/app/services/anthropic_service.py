"""Anthropic (Claude) service implemented on the LangChain base."""

import base64
import logging
from typing import Any, Dict, List, cast

from langchain_anthropic import ChatAnthropic

from app.config import settings
from app.models import LLMModel
from app.services.base_llm_service import FileAttachmentData as LLMFileAttachmentData
from app.services.langchain_llm_service import LangChainLLMService

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    LLMModel(
        id="claude-3-opus-20240229",
        provider="anthropic",
        label="Claude Opus 3",
        supports_images=True,
        supports_pdfs=False,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-opus-4-20250514",
        provider="anthropic",
        label="Claude Opus 4",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-opus-4-1-20250805",
        provider="anthropic",
        label="Claude Opus 4.1",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-3-haiku-20240307",
        provider="anthropic",
        label="Claude Haiku 3",
        supports_images=True,
        supports_pdfs=False,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-3-5-haiku-20241022",
        provider="anthropic",
        label="Claude Haiku 3.5",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-3-7-sonnet-20250219",
        provider="anthropic",
        label="Claude Sonnet 3.7",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="claude-sonnet-4-20250514",
        provider="anthropic",
        label="Claude Sonnet 4",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
]


class AnthropicService(LangChainLLMService):
    """LangChain service for Anthropic Claude models."""

    def __init__(self) -> None:
        super().__init__(
            supported_models=SUPPORTED_MODELS,
            provider_name="anthropic",
        )

    def _build_chat_model(self, *, model_id: str) -> ChatAnthropic:
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        logger.info("Initializing Anthropic model '%s'", model_id)
        chat_model_cls: Any = ChatAnthropic
        return cast(
            ChatAnthropic,
            chat_model_cls(
                model_name=model_id,
                temperature=0,
                streaming=True,
            ),
        )

    def render_image_attachments(
        self, *, image_attachments: List[LLMFileAttachmentData]
    ) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for attachment in image_attachments:
            try:
                file_bytes = self.s3_service.download_file_content(attachment.s3_key)
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": attachment.file_type,
                            "data": encoded,
                        },
                    }
                )
            except Exception as exc:
                logger.exception(
                    "Failed to render image attachment %s: %s",
                    attachment.filename,
                    exc,
                )
                blocks.append(
                    {
                        "type": "text",
                        "text": f"[Unable to load image {attachment.filename}]",
                    }
                )
        return blocks

    def render_image_url(self, *, image_url: str) -> List[Dict[str, Any]]:
        return [
            {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": image_url,
                },
            }
        ]
