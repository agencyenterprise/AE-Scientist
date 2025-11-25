"""
OpenAI service for generating conversation summaries and project drafts.

This module handles communication with OpenAI API to generate summaries
of conversations and transform them into structured project proposals.
"""

import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Union, cast

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services import SummarizerService
from app.services.base_llm_service import BaseLLMService, FileAttachmentData, LLMProjectGeneration
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamProjectUpdateEvent,
    StreamStatusEvent,
)
from app.services.database import get_database
from app.services.mem0_service import Mem0Service
from app.services.openai.chat_with_project_draft import ChatWithProjectDraftStream
from app.services.prompts import get_project_generation_prompt
from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

logger = logging.getLogger(__name__)
mem0 = Mem0Service()

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

# Models that use OpenAI's Responses API instead of Chat Completions API
RESPONSES_API_MODELS = [
    "o1",
    "o1-pro",
    "o3",
    "o3-pro",
    "o3-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
]


class OpenAIService(BaseLLMService):
    """Service for interacting with OpenAI API."""

    def __init__(self, summarizer_service: SummarizerService) -> None:
        """Initialize the OpenAI service."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Initialize async OpenAI client with minimal configuration
        self.client = AsyncOpenAI(api_key=api_key)
        self.summarizer_service = summarizer_service

    def get_context_window_tokens(self, llm_model: str) -> int:
        """Return context window tokens for a given model id from SUPPORTED_MODELS."""
        for model in SUPPORTED_MODELS:
            if model.id == llm_model:
                return model.context_window_tokens
        raise ValueError(f"Unknown OpenAI model for context window: {llm_model}")

    def _convert_messages_to_responses_input(
        self,
        messages: List[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam],
    ) -> List[Dict[str, object]]:
        """Convert chat-completions style messages into Responses API input blocks.

        This supports text content and image_url items.
        """
        converted: List[Dict[str, object]] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            blocks: List[Dict[str, object]] = []

            if isinstance(content, str):
                blocks.append({"type": "input_text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    try:
                        item_type = item.get("type")
                    except Exception:
                        item_type = None

                    if item_type == "text":
                        text_val = item.get("text", "")
                        blocks.append({"type": "input_text", "text": text_val})
                    elif item_type == "image_url":
                        img_url_obj = item.get("image_url", {})
                        url_val = (
                            img_url_obj.get("url", "") if isinstance(img_url_obj, dict) else ""
                        )
                        if url_val:
                            blocks.append({"type": "input_image", "image_url": url_val})
                    else:
                        # Fallback to string representation
                        blocks.append({"type": "input_text", "text": str(item)})
            else:
                blocks.append({"type": "input_text", "text": str(content)})

            converted.append({"role": role, "content": blocks})

        return converted

    async def _openai_unified_stream(
        self,
        model_id: str,
        messages: List[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam],
        max_completion_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks from either Responses API or Chat Completions API. Always streams."""
        use_responses_api = model_id in RESPONSES_API_MODELS
        if use_responses_api:
            responses_input = self._convert_messages_to_responses_input(messages)
            responses_stream = await self.client.responses.create(
                model=model_id,
                input=cast(Any, responses_input),
                stream=True,
            )
            async for event in cast(AsyncStream[object], responses_stream):
                # Duck-type to capture both ResponseTextDeltaEvent and ResponseOutputTextDelta
                text_delta = getattr(event, "delta", None)
                if isinstance(text_delta, str) and text_delta:
                    yield text_delta
            return
        completions_stream = await self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=True,
            max_tokens=max_completion_tokens,
        )

        any_yielded = False
        async for chunk in completions_stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                any_yielded = True
                yield chunk.choices[0].delta.content
        if not any_yielded:
            logger.warning("Chat completions stream yielded no content for model %s", model_id)

    def _parse_project_draft_response(self, content: str) -> LLMProjectGeneration:
        """Parse project draft from streamed content with title/description tags."""

        # Extract title
        logger.debug(f"Parsing project draft response: {content}")
        title_match = re.search(r"<title>(.*?)</title>", content, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        if len(title) > settings.MAX_PROJECT_TITLE_LENGTH:
            title = title[: settings.MAX_PROJECT_TITLE_LENGTH - 3] + "..."
            logger.warning(
                f"Truncated project title from {len(title)} to {settings.MAX_PROJECT_TITLE_LENGTH} characters for Linear compatibility"
            )

        # Extract description
        description_match = re.search(r"<description>(.*?)</description>", content, re.DOTALL)
        description = description_match.group(1).strip() if description_match else ""

        logger.debug(f"Parsed title: {title}")
        logger.debug(f"Parsed description: {description}")

        if not title or not description:
            raise ValueError(
                f"Failed to parse title or description from response. Content: {content[:200]}..."
            )

        return LLMProjectGeneration(title=title, description=description)

    async def generate_text_single_call(
        self,
        llm_model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
    ) -> str:
        """Single non-streaming generation by consuming the unified streaming helper."""

        messages: List[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_prompt),
        ]
        collected = ""
        async for piece in self._openai_unified_stream(
            model_id=llm_model,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        ):
            collected += piece
        logger.debug("Generated text: %s", collected.strip())
        return collected.strip()

    async def generate_imported_chat_keywords(
        self, llm_model: str, imported_conversation_text: str
    ) -> str:
        return await self._generate_imported_chat_keywords(
            llm_model=llm_model, conversation_text=imported_conversation_text
        )

    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        """Generate a concise summary with map-reduce if needed to respect context size."""
        return await self._summarize_document(llm_model=llm_model, content=content)

    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        """Use LLM to generate a detailed caption for an image URL."""

        system_prompt = (
            "You are an expert image describer. Provide a concise but information-dense description "
            "covering scene, objects, text, layout, and any notable artifacts or anomalies."
        )
        messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(
                role="user",
                content=[
                    {"type": "text", "text": "Please describe this image precisely:"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            ),
        ]
        collected = ""
        async for piece in self._openai_unified_stream(
            model_id=llm_model.id,
            messages=messages,
            max_completion_tokens=settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS,
        ):
            collected += piece
        return collected.strip()

    async def generate_project_draft(
        self, llm_model: str, conversation_text: str, _user_id: int, conversation_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Generate a project draft with streaming content.

        Args:
            messages: List of conversation messages

        Yields:
            Content chunks as they are generated
        """

        # Get system prompt (custom or default)
        db = get_database()
        stored_memories = db.get_memories_block(
            conversation_id=conversation_id, source="imported_chat"
        )
        memories = []
        for idx, m in enumerate(stored_memories.memories, start=1):
            try:
                memories.append(f"{idx}. {m['memory']}")
            except KeyError:
                continue
        system_prompt = get_project_generation_prompt(db=db, context="\n".join(memories))

        logger.debug(f"System prompt: {system_prompt}")

        api_messages: List[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(
                role="system",
                content=system_prompt,
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content=f"Analyze this conversation and generate a project draft:\n\n{conversation_text}",
            ),
        ]

        logger.info("Sending streaming project draft generation request")
        logger.debug(f"Model: {llm_model}")

        async for content in self._openai_unified_stream(
            model_id=llm_model,
            messages=api_messages,
            max_completion_tokens=settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS,
        ):
            logger.debug(f"Content chunk: {content}")
            yield content

    async def chat_with_project_draft_stream(
        self,
        llm_model: LLMModel,
        conversation_id: int,
        project_draft_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
        user_id: int,
    ) -> AsyncGenerator[
        Union[
            StreamStatusEvent,
            StreamContentEvent,
            StreamProjectUpdateEvent,
            StreamConversationLockedEvent,
            StreamErrorEvent,
            StreamDoneEvent,
        ],
        None,
    ]:
        chat_wiht_project_draft_stream = ChatWithProjectDraftStream(self, self.summarizer_service)
        async for item in chat_wiht_project_draft_stream.chat_with_project_draft_stream(
            self.client,
            llm_model,
            conversation_id=conversation_id,
            project_draft_id=project_draft_id,
            user_message=user_message,
            chat_history=chat_history,
            attached_files=attached_files,
            user_id=user_id,
        ):
            yield item
