"""
OpenAI service for generating conversation summaries and ideas.

This module handles communication with OpenAI API to generate summaries
of conversations and transform them into structured research ideas.
"""

import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Union, cast

from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services import SummarizerService
from app.services.base_llm_service import BaseLLMService, FileAttachmentData, LLMIdeaGeneration
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamIdeaUpdateEvent,
    StreamStatusEvent,
)
from app.services.database import get_database
from app.services.mem0_service import Mem0Service
from app.services.openai.chat_with_idea import ChatWithIdeaStream
from app.services.prompts import get_idea_generation_prompt

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
    "gpt-5.1",
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

    def _parse_idea_response(self, content: str) -> LLMIdeaGeneration:
        """Parse research idea from streamed content with XML-style tags."""
        logger.debug(f"Parsing idea response: {content[:500]}...")

        # Extract all fields
        title_match = re.search(r"<title>(.*?)</title>", content, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        short_hypothesis_match = re.search(
            r"<short_hypothesis>(.*?)</short_hypothesis>", content, re.DOTALL
        )
        short_hypothesis = short_hypothesis_match.group(1).strip() if short_hypothesis_match else ""

        related_work_match = re.search(r"<related_work>(.*?)</related_work>", content, re.DOTALL)
        related_work = related_work_match.group(1).strip() if related_work_match else ""

        abstract_match = re.search(r"<abstract>(.*?)</abstract>", content, re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else ""

        experiments_match = re.search(r"<experiments>(.*?)</experiments>", content, re.DOTALL)
        experiments_raw = experiments_match.group(1).strip() if experiments_match else "[]"
        try:
            experiments = json.loads(experiments_raw)
            if not isinstance(experiments, list):
                experiments = [str(experiments)]
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse experiments as JSON: {experiments_raw[:100]}")
            experiments = [experiments_raw]

        expected_outcome_match = re.search(
            r"<expected_outcome>(.*?)</expected_outcome>", content, re.DOTALL
        )
        expected_outcome = expected_outcome_match.group(1).strip() if expected_outcome_match else ""

        risk_factors_match = re.search(
            r"<risk_factors_and_limitations>(.*?)</risk_factors_and_limitations>",
            content,
            re.DOTALL,
        )
        risk_factors_raw = risk_factors_match.group(1).strip() if risk_factors_match else "[]"
        try:
            risk_factors_and_limitations = json.loads(risk_factors_raw)
            if not isinstance(risk_factors_and_limitations, list):
                risk_factors_and_limitations = [str(risk_factors_and_limitations)]
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse risk factors as JSON: {risk_factors_raw[:100]}")
            risk_factors_and_limitations = [risk_factors_raw]

        logger.debug(f"Parsed title: {title}")
        logger.debug(f"Parsed experiments count: {len(experiments)}")

        if not title or not short_hypothesis or not abstract:
            raise ValueError(
                f"Failed to parse required fields from response. Content: {content[:200]}..."
            )

        return LLMIdeaGeneration(
            title=title,
            short_hypothesis=short_hypothesis,
            related_work=related_work,
            abstract=abstract,
            experiments=experiments,
            expected_outcome=expected_outcome,
            risk_factors_and_limitations=risk_factors_and_limitations,
        )

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
            max_completion_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
        ):
            collected += piece
        return collected.strip()

    async def generate_idea(
        self, llm_model: str, conversation_text: str, _user_id: int, conversation_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Generate a research idea with streaming content.

        Args:
            llm_model: The model to use
            conversation_text: The conversation text to analyze
            _user_id: The user ID
            conversation_id: The conversation ID

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
        system_prompt = get_idea_generation_prompt(db=db, context="\n".join(memories))

        logger.debug(f"System prompt: {system_prompt}")

        api_messages: List[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(
                role="system",
                content=system_prompt,
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content=f"Analyze this conversation and generate a research idea:\n\n{conversation_text}",
            ),
        ]

        logger.info("Sending streaming idea generation request")
        logger.debug(f"Model: {llm_model}")

        async for content in self._openai_unified_stream(
            model_id=llm_model,
            messages=api_messages,
            max_completion_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
        ):
            logger.debug(f"Content chunk: {content}")
            yield content

    async def chat_with_idea_stream(
        self,
        llm_model: LLMModel,
        conversation_id: int,
        idea_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
        user_id: int,
    ) -> AsyncGenerator[
        Union[
            StreamStatusEvent,
            StreamContentEvent,
            StreamIdeaUpdateEvent,
            StreamConversationLockedEvent,
            StreamErrorEvent,
            StreamDoneEvent,
        ],
        None,
    ]:
        chat_with_idea_stream = ChatWithIdeaStream(self, self.summarizer_service)
        async for item in chat_with_idea_stream.chat_with_idea_stream(
            self.client,
            llm_model,
            conversation_id=conversation_id,
            idea_id=idea_id,
            user_message=user_message,
            chat_history=chat_history,
            attached_files=attached_files,
            user_id=user_id,
        ):
            yield item
