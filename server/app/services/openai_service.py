"""OpenAI service implemented on top of the LangChain abstraction."""

import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import settings
from app.models import LLMModel
from app.services.base_llm_service import FileAttachmentData as LLMFileAttachmentData
from app.services.langchain_llm_service import LangChainLLMService

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    LLMModel(
        id="gpt-3.5-turbo",
        provider="openai",
        label="GPT-3.5 Turbo",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=4096,
    ),
    LLMModel(
        id="gpt-4o",
        provider="openai",
        label="GPT-4o",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=128_000,
    ),
    LLMModel(
        id="gpt-4o-mini",
        provider="openai",
        label="GPT-4o Mini",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=128_000,
    ),
    LLMModel(
        id="gpt-4",
        provider="openai",
        label="GPT-4",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=8192,
    ),
    LLMModel(
        id="gpt-4-turbo",
        provider="openai",
        label="GPT-4 Turbo",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=128_000,
    ),
    LLMModel(
        id="gpt-4.1",
        provider="openai",
        label="GPT-4.1",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=1_000_000,
    ),
    LLMModel(
        id="gpt-4.1-mini",
        provider="openai",
        label="GPT-4.1 Mini",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=1_000_000,
    ),
    LLMModel(
        id="gpt-4.1-nano",
        provider="openai",
        label="GPT-4.1 Nano",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=1_000_000,
    ),
    LLMModel(
        id="gpt-5",
        provider="openai",
        label="GPT-5",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=400_000,
    ),
    LLMModel(
        id="gpt-5.1",
        provider="openai",
        label="GPT-5.1",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=400_000,
    ),
    LLMModel(
        id="gpt-5-nano",
        provider="openai",
        label="GPT-5 Nano",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=400_000,
    ),
    LLMModel(
        id="gpt-5-mini",
        provider="openai",
        label="GPT-5 Mini",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=400_000,
    ),
    LLMModel(
        id="gpt-5.2",
        provider="openai",
        label="GPT-5.2",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=400_000,
    ),
    LLMModel(
        id="o1",
        provider="openai",
        label="o1",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="o1-pro",
        provider="openai",
        label="o1 Pro",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="o3",
        provider="openai",
        label="o3",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="o3-mini",
        provider="openai",
        label="o3 Mini",
        supports_images=False,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
    LLMModel(
        id="o3-pro",
        provider="openai",
        label="o3 Pro",
        supports_images=True,
        supports_pdfs=True,
        context_window_tokens=200_000,
    ),
]


class OpenAIService(LangChainLLMService):
    """LangChain implementation for OpenAI models."""

    def __init__(self) -> None:
        super().__init__(
            supported_models=SUPPORTED_MODELS,
            provider_name="openai",
        )

    def _build_chat_model(self, *, model_id: str) -> ChatOpenAI:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        logger.info("Initializing OpenAI model '%s'", model_id)
        return ChatOpenAI(
            model=model_id,
            api_key=SecretStr(api_key),
            temperature=0,
            streaming=True,
        )

    def render_image_attachments(
        self, *, image_attachments: List[LLMFileAttachmentData]
    ) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for attachment in image_attachments:
            try:
                image_url = self.s3_service.generate_download_url(attachment.s3_key)
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    }
                )
            except Exception as exc:
                logger.exception(
                    "Failed to build image_url block for %s: %s",
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
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            }
        ]
