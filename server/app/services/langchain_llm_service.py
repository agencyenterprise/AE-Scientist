"""LangChain-powered base service that removes per-provider duplication."""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Sequence, Union

from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.json import parse_partial_json
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services.base_llm_service import BaseLLMService
from app.services.base_llm_service import FileAttachmentData as LLMFileAttachmentData
from app.services.base_llm_service import LLMIdeaGeneration
from app.services.chat_models import (
    ChatStatus,
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneData,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamIdeaUpdateEvent,
    StreamStatusEvent,
    ToolCallResult,
)
from app.services.database import DatabaseManager, get_database
from app.services.database.file_attachments import FileAttachmentData as DBFileAttachmentData
from app.services.pdf_service import PDFService
from app.services.prompts import (
    format_pdf_content_for_context,
    get_chat_system_prompt,
    get_idea_generation_prompt,
    get_manual_seed_prompt,
)
from app.services.s3_service import S3Service, get_s3_service

logger = logging.getLogger(__name__)

THINKING_TAG_PATTERN = re.compile(r"<thinking>.*?</thinking>\s*", re.IGNORECASE | re.DOTALL)
IDEA_STREAM_LIST_FIELDS = {"experiments", "risk_factors_and_limitations"}
IDEA_STREAM_FIELD_ORDER = (
    "title",
    "short_hypothesis",
    "related_work",
    "abstract",
    "experiments",
    "expected_outcome",
    "risk_factors_and_limitations",
)


def get_idea_max_completion_tokens(model: BaseChatModel) -> int:
    model_max_output_tokens = (
        model.profile.get("max_output_tokens", settings.IDEA_MAX_COMPLETION_TOKENS)
        if model.profile
        else settings.IDEA_MAX_COMPLETION_TOKENS
    )
    return min(settings.IDEA_MAX_COMPLETION_TOKENS, model_max_output_tokens)


class LangChainLLMService(BaseLLMService, ABC):
    """Shared LangChain implementation that works across providers."""

    def __init__(
        self,
        *,
        supported_models: Sequence[LLMModel],
        provider_name: str,
    ) -> None:
        if not supported_models:
            raise ValueError("supported_models cannot be empty")

        self._supported_models = list(supported_models)
        self.provider_name = provider_name
        self._model_cache: Dict[str, BaseChatModel] = {}
        self._s3_service = get_s3_service()
        self._pdf_service = PDFService()
        self._chat_stream = LangChainChatWithIdeaStream(service=self)

    @property
    def s3_service(self) -> S3Service:
        return self._s3_service

    @property
    def pdf_service(self) -> PDFService:
        return self._pdf_service

    def get_context_window_tokens(self, llm_model: str) -> int:
        for model in self._supported_models:
            if model.id == llm_model:
                return model.context_window_tokens
        raise ValueError(f"Unknown model '{llm_model}' for provider {self.provider_name}")

    def get_or_create_model(self, llm_model: str) -> BaseChatModel:
        if llm_model not in self._model_cache:
            self._model_cache[llm_model] = self._build_chat_model(model_id=llm_model)
        return self._model_cache[llm_model]

    def strip_reasoning_tags(self, *, text: str) -> str:
        """Remove provider-specific reasoning markers such as <thinking> blocks."""
        if not text:
            return ""
        return THINKING_TAG_PATTERN.sub("", text).strip()

    def _model_with_token_limit(
        self, llm_model: str, max_output_tokens: int
    ) -> Runnable[List[BaseMessage], BaseMessage]:
        base_model = self.get_or_create_model(llm_model=llm_model)
        return base_model.bind(max_tokens=max_output_tokens)

    @abstractmethod
    def _build_chat_model(self, *, model_id: str) -> BaseChatModel:
        """Return a LangChain chat model for the given provider/model id."""

    @abstractmethod
    def render_image_attachments(
        self, *, image_attachments: List[LLMFileAttachmentData]
    ) -> List[Dict[str, Any]]:
        """Provider-specific image payloads for chat attachments."""

    @abstractmethod
    def render_image_url(self, *, image_url: str) -> List[Dict[str, Any]]:
        """Provider-specific image payload for summarize_image."""

    @staticmethod
    def _text_content_block(text: str) -> List[Union[str, Dict[str, Any]]]:
        return [{"type": "text", "text": str(text)}]

    def _message_to_text(self, *, message: AIMessage) -> str:
        content: Any = message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_value = item.get("text", "")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            return "".join(parts).strip()
        return str(content)

    def _format_text_attachments(self, *, text_files: List[LLMFileAttachmentData]) -> str:
        if not text_files:
            return ""
        formatted_content = "\n\n--- Text Files ---\n"
        for file_attachment in text_files:
            formatted_content += f"\n**{file_attachment.filename}:**\n"
            try:
                file_content = self._s3_service.download_file_content(file_attachment.s3_key)
                text_content = file_content.decode("utf-8")
                formatted_content += f"{text_content}\n\n"
            except UnicodeDecodeError as exc:
                logger.warning(
                    "Failed to decode text file %s: %s",
                    file_attachment.filename,
                    exc,
                )
                formatted_content += f"(Unable to decode text file: {exc})\n\n"
            except Exception as exc:
                logger.exception(
                    "Failed to read text file %s: %s",
                    file_attachment.filename,
                    exc,
                )
                formatted_content += f"(Unable to read text file: {exc})\n\n"
        return formatted_content

    def build_current_user_message(
        self,
        *,
        llm_model: LLMModel,
        user_message: str,
        attached_files: List[LLMFileAttachmentData],
    ) -> HumanMessage:
        pdf_attachments = [file for file in attached_files if file.file_type == "application/pdf"]
        text_attachments = [file for file in attached_files if file.file_type == "text/plain"]
        image_attachments = [file for file in attached_files if file.file_type.startswith("image/")]

        user_text = user_message
        if pdf_attachments:
            pdf_context = format_pdf_content_for_context(
                pdf_files=pdf_attachments,
                s3_service=self._s3_service,
                pdf_service=self._pdf_service,
            )
            user_text = f"{user_text}{pdf_context}"
        if text_attachments:
            text_context = self._format_text_attachments(text_files=text_attachments)
            user_text = f"{user_text}{text_context}"

        if image_attachments and llm_model.supports_images:
            content_blocks: List[Union[str, Dict[str, Any]]] = [{"type": "text", "text": user_text}]
            try:
                content_blocks.extend(
                    self.render_image_attachments(image_attachments=image_attachments)
                )
            except Exception as exc:
                logger.exception("Failed to render image attachments: %s", exc)
                content_blocks.append(
                    {
                        "type": "text",
                        "text": f"[Failed to load image attachments: {exc}]",
                    }
                )
            return HumanMessage(content=content_blocks)

        if image_attachments and not llm_model.supports_images:
            placeholders = "\n".join(
                f"[Image attachment omitted: {file.filename} (vision unsupported)]"
                for file in image_attachments
            )
            user_text = f"{user_text}\n\n{placeholders}"

        return HumanMessage(content=self._text_content_block(text=user_text))

    async def generate_text_single_call(
        self,
        llm_model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
    ) -> str:
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        model = self._model_with_token_limit(
            llm_model=llm_model,
            max_output_tokens=max_completion_tokens,
        )
        response = await model.ainvoke(input=messages)
        if not isinstance(response, AIMessage):
            return ""
        return self._message_to_text(message=response)

    async def generate_idea(
        self,
        llm_model: str,
        conversation_text: str,
        _user_id: int,
        conversation_id: int,
    ) -> AsyncGenerator[str, None]:
        db = get_database()
        stored_memories = db.get_memories_block(
            conversation_id=conversation_id, source="imported_chat"
        )
        memories: List[str] = []
        for idx, memory in enumerate(stored_memories.memories, start=1):
            try:
                memories.append(f"{idx}. {memory['memory']}")
            except KeyError:
                continue
        system_prompt = get_idea_generation_prompt(db=db, context="\n".join(memories))
        user_prompt = (
            "Analyze this conversation and generate a research idea based on the discussion below.\n\n"
            f"{conversation_text}"
        )
        messages = [
            SystemMessage(content=self._text_content_block(text=system_prompt)),
            HumanMessage(content=self._text_content_block(text=user_prompt)),
        ]
        async for event_payload in self._stream_structured_schema_response(
            llm_model=llm_model,
            messages=messages,
        ):
            yield event_payload

    def generate_manual_seed_idea_prompt(self, *, idea_title: str, idea_hypothesis: str) -> str:
        """
        Generate a user prompt for a manual seed idea.
        """
        return (
            "Create a structured research idea draft using the provided manual seed.\n\n"
            f"Title: {idea_title}\n"
            f"Hypothesis: {idea_hypothesis}"
        )

    async def generate_manual_seed_idea(
        self, *, llm_model: str, user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate an idea from a manual title and hypothesis seed.
        """
        db = get_database()
        system_prompt = get_manual_seed_prompt(db=db)
        messages = [
            SystemMessage(content=self._text_content_block(text=system_prompt)),
            HumanMessage(content=self._text_content_block(text=user_prompt)),
        ]
        async for event_payload in self._stream_structured_schema_response(
            llm_model=llm_model,
            messages=messages,
        ):
            yield event_payload

    async def _stream_structured_schema_response(
        self,
        *,
        llm_model: str,
        messages: List[BaseMessage],
    ) -> AsyncGenerator[str, None]:
        base_model = self.get_or_create_model(llm_model=llm_model)
        tool_bound_model = base_model.bind_tools(
            [LLMIdeaGeneration],
            tool_choice="any",
            ls_structured_output_format={
                "kwargs": {"method": "function_calling"},
                "schema": LLMIdeaGeneration,
            },
        )
        # Use index as the grouping key for tool call chunks (per LangChain docs)
        # The index field remains consistent across all chunks of a single tool call,
        # while id may be None in subsequent chunks after the first one.
        accumulated_arguments: Dict[int, str] = defaultdict(str)
        latest_emitted_fields: Dict[str, Union[str, List[str]]] = {}
        active_tool_index: int | None = None
        last_chunk_metadata: Dict[str, Any] | None = None

        async for chunk in tool_bound_model.astream(
            input=messages,
            max_tokens=get_idea_max_completion_tokens(base_model),
        ):
            if not isinstance(chunk, AIMessageChunk):
                continue

            last_chunk_metadata = getattr(chunk, "response_metadata", None)

            for tool_chunk in chunk.tool_call_chunks:
                # Use index as grouping key (consistent across chunks)
                # Default to 0 for providers that don't set index
                tool_index = tool_chunk.get("index")
                if tool_index is None:
                    tool_index = 0

                append_value_raw: object = tool_chunk.get("args")
                if isinstance(append_value_raw, dict):
                    append_value = json.dumps(append_value_raw)
                elif isinstance(append_value_raw, str):
                    append_value = append_value_raw
                else:
                    append_value = ""
                if not append_value:
                    continue

                accumulated_arguments[tool_index] += append_value
                active_tool_index = tool_index

                partial_fields = self._parse_partial_idea_fields(
                    payload=accumulated_arguments[tool_index]
                )
                if not partial_fields:
                    continue

                for field_name in IDEA_STREAM_FIELD_ORDER:
                    if field_name not in partial_fields:
                        continue
                    normalized_value = self._normalize_partial_field_value(
                        field=field_name,
                        value=partial_fields[field_name],
                    )
                    if normalized_value is None:
                        continue
                    if latest_emitted_fields.get(field_name) == normalized_value:
                        continue
                    latest_emitted_fields[field_name] = normalized_value
                    yield json.dumps(
                        {
                            "event": "section_delta",
                            "field": field_name,
                            "value": normalized_value,
                        }
                    )

        if active_tool_index is None:
            raise ValueError("LLM did not return structured idea payload.")

        # Check if the response was truncated due to max_tokens limit
        finish_reason = ""
        if last_chunk_metadata:
            finish_reason = last_chunk_metadata.get("finish_reason", "")
            logger.debug("Idea generation finished with reason: %s", finish_reason)
            if finish_reason == "length":
                logger.warning("Idea generation response was truncated due to max_tokens limit")
                raise ValueError(
                    "Idea generation was truncated. The response exceeded the token limit. "
                    "Try a shorter conversation or increase IDEA_MAX_COMPLETION_TOKENS."
                )

        final_payload = accumulated_arguments[active_tool_index]
        if not final_payload.strip():
            raise ValueError("LLM returned empty structured idea payload.")

        # Validate that the payload contains all required fields before yielding
        try:
            partial = parse_partial_json(final_payload)
            if isinstance(partial, dict):
                required_fields = [
                    "title",
                    "short_hypothesis",
                    "related_work",
                    "abstract",
                    "experiments",
                    "expected_outcome",
                    "risk_factors_and_limitations",
                ]
                missing = [f for f in required_fields if f not in partial]
                if missing:
                    logger.warning(
                        "LLM generated incomplete idea. Missing fields: %s, "
                        "finish_reason: %s, payload_length: %d",
                        missing,
                        finish_reason,
                        len(final_payload),
                    )
        except Exception:
            pass  # Let the downstream parser handle invalid JSON

        yield json.dumps({"event": "final_idea_payload", "data": final_payload})

    def _parse_partial_idea_fields(self, *, payload: str) -> Dict[str, Any]:
        try:
            parsed = parse_partial_json(payload)
        except Exception:
            logger.debug("Failed to parse partial idea payload", exc_info=True)
            return {}

        if isinstance(parsed, dict):
            return parsed
        return {}

    def _normalize_partial_field_value(
        self,
        *,
        field: str,
        value: object,
    ) -> Union[str, List[str], None]:
        if field in IDEA_STREAM_LIST_FIELDS:
            if isinstance(value, list):
                normalized = [
                    str(item).strip() for item in value if isinstance(item, str) and item.strip()
                ]
            elif isinstance(value, str):
                normalized = [item.strip() for item in value.split("\n") if item.strip()]
            else:
                return None
            return normalized

        if isinstance(value, str):
            return value
        if value is None:
            return None
        return str(value)

    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        return await self._summarize_document(llm_model=llm_model, content=content)

    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        if not llm_model.supports_images:
            raise ValueError(f"Model {llm_model.id} does not support image inputs")
        system_prompt = (
            "You are an expert image describer. Provide a concise but information-dense description "
            "covering scene, objects, text, layout, and any notable artifacts or anomalies."
        )
        content_blocks = self.render_image_url(image_url=image_url)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=[
                    {"type": "text", "text": "Please describe this image precisely:"},
                    *content_blocks,
                ]
            ),
        ]
        response = await self._model_with_token_limit(
            llm_model=llm_model.id,
            max_output_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
        ).ainvoke(input=messages)
        if not isinstance(response, AIMessage):
            return ""
        return self._message_to_text(message=response)

    async def generate_imported_chat_keywords(
        self, llm_model: str, imported_conversation_text: str
    ) -> str:
        return await self._generate_imported_chat_keywords(
            llm_model=llm_model,
            conversation_text=imported_conversation_text,
        )

    async def chat_with_idea_stream(
        self,
        llm_model: LLMModel,
        conversation_id: int,
        idea_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[LLMFileAttachmentData],
        user_id: int,
    ) -> AsyncGenerator[
        StreamContentEvent
        | StreamStatusEvent
        | StreamIdeaUpdateEvent
        | StreamConversationLockedEvent
        | StreamErrorEvent
        | StreamDoneEvent,
        None,
    ]:
        async for event in self._chat_stream.chat_with_idea_stream(
            llm_model=llm_model,
            conversation_id=conversation_id,
            idea_id=idea_id,
            user_message=user_message,
            chat_history=chat_history,
            attached_files=attached_files,
            user_id=user_id,
        ):
            yield event

    def _extract_json_from_content(self, content: str) -> str:
        """
        Extract JSON object from content that may contain surrounding text.

        Uses json.JSONDecoder.raw_decode() which parses the first valid JSON
        object and ignores any trailing content.
        """
        content = content.strip()

        # Find the start of JSON object
        start_idx = content.find("{")
        if start_idx == -1:
            return content

        try:
            decoder = json.JSONDecoder()
            _, end_idx = decoder.raw_decode(content, start_idx)
            extracted = content[start_idx:end_idx]
            if len(extracted) < len(content):
                logger.debug(
                    "Extracted JSON from content with surrounding text. "
                    "Original length: %d, Extracted length: %d",
                    len(content),
                    len(extracted),
                )
            return extracted
        except json.JSONDecodeError:
            return content

    def _parse_idea_response(self, content: str) -> LLMIdeaGeneration:
        cleaned_content = self.strip_reasoning_tags(text=content)
        extracted_json = self._extract_json_from_content(cleaned_content)

        try:
            return LLMIdeaGeneration.model_validate_json(extracted_json)
        except (ValidationError, ValueError) as exc:
            # Log detailed error info for debugging
            content_len = len(cleaned_content)
            extracted_len = len(extracted_json)
            last_chars = cleaned_content[-200:] if content_len > 200 else cleaned_content

            # Try to parse as dict to see which fields are present/missing
            missing_fields: List[str] = []
            present_fields: List[str] = []
            try:
                parsed_dict = json.loads(extracted_json)
                if isinstance(parsed_dict, dict):
                    required_fields = [
                        "title",
                        "short_hypothesis",
                        "related_work",
                        "abstract",
                        "experiments",
                        "expected_outcome",
                        "risk_factors_and_limitations",
                    ]
                    for field in required_fields:
                        if field in parsed_dict:
                            present_fields.append(field)
                        else:
                            missing_fields.append(field)
            except json.JSONDecodeError:
                pass

            logger.error(
                "Failed to parse idea response for provider %s. "
                "Content length: %d, Extracted JSON length: %d, "
                "Present fields: %s, Missing fields: %s, "
                "Last 200 chars of content: %s",
                self.provider_name,
                content_len,
                extracted_len,
                present_fields or "unknown",
                missing_fields or "JSON parse failed",
                last_chars,
            )
            # Provide actionable error message based on failure type
            if missing_fields:
                error_msg = (
                    f"LLM generated incomplete idea - missing fields: {missing_fields}. "
                    "This may be caused by: (1) model output being cut off, "
                    "(2) conversation context being too long, or "
                    "(3) model generating repetitive content. "
                    "Try using a different model or shortening the input."
                )
            else:
                error_msg = (
                    "Failed to parse LLM response as valid JSON. "
                    "The model may have returned malformed output."
                )
            raise ValueError(error_msg) from exc


class UpdateIdeaInput(BaseModel):
    title: str = Field(..., description="Updated idea title")
    short_hypothesis: str = Field(..., description="Updated short hypothesis")
    related_work: str = Field(..., description="Updated related work section")
    abstract: str = Field(..., description="Updated abstract section")
    experiments: List[str] = Field(..., description="Experiments list")
    expected_outcome: str = Field(..., description="Expected outcome text")
    risk_factors_and_limitations: List[str] = Field(..., description="Risk factors and limitations")


class LangChainChatWithIdeaStream:
    """Shared streaming implementation for LangChain chat models."""

    def __init__(self, *, service: LangChainLLMService) -> None:
        self.service = service

    async def chat_with_idea_stream(
        self,
        *,
        llm_model: LLMModel,
        conversation_id: int,
        idea_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[LLMFileAttachmentData],
        user_id: int,
    ) -> AsyncGenerator[
        Union[
            StreamStatusEvent,
            StreamContentEvent,
            StreamIdeaUpdateEvent,
            StreamErrorEvent,
            StreamDoneEvent,
        ],
        None,
    ]:
        db = get_database()
        messages = await self._build_messages(
            db=db,
            conversation_id=conversation_id,
            user_message=user_message,
            chat_history=chat_history,
            attached_files=attached_files,
            llm_model=llm_model,
        )
        update_tool = self._build_update_idea_tool(
            db=db,
            idea_id=idea_id,
            user_id=user_id,
        )
        base_model = self.service.get_or_create_model(llm_model=llm_model.id)
        tool_bound_model = base_model.bind_tools([update_tool])
        model = tool_bound_model.bind(max_tokens=get_idea_max_completion_tokens(base_model))

        idea_updated = False
        assistant_response = ""

        try:
            yield StreamStatusEvent("status", ChatStatus.ANALYZING_REQUEST.value)
            while True:
                response = await model.ainvoke(input=messages)
                if not isinstance(response, AIMessage):
                    raise TypeError(
                        f"chat model returned unsupported message type: {type(response).__name__}"
                    )
                tool_calls: List[Dict[str, Any]] = self._normalize_tool_calls(response=response)
                if tool_calls:
                    tool_messages: List[ToolMessage] = []
                    async for event in self._process_tool_calls(
                        tool_calls=tool_calls,
                        update_tool=update_tool,
                    ):
                        if isinstance(event, ToolCallResult):
                            if event.idea_updated:
                                idea_updated = True
                            tool_messages = event.tool_results
                        else:
                            yield event
                    messages.append(response)
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                    continue

                final_message = response
                final_text = self.service._message_to_text(message=final_message)
                final_text = self.service.strip_reasoning_tags(text=final_text)
                if final_text:
                    assistant_response = final_text
                    yield StreamStatusEvent("status", ChatStatus.GENERATING_RESPONSE.value)
                    yield StreamContentEvent("content", final_text)
                messages.append(final_message)
                break

            yield StreamStatusEvent("status", ChatStatus.DONE.value)
            yield StreamDoneEvent(
                "done",
                StreamDoneData(
                    idea_updated=idea_updated,
                    assistant_response=assistant_response,
                ),
            )
        except Exception as exc:
            logger.exception("Error in chat_with_idea_stream: %s", exc)
            yield StreamErrorEvent("error", f"An error occurred: {exc}")

    def _normalize_tool_calls(self, response: BaseMessage) -> List[Dict[str, Any]]:
        if not isinstance(response, AIMessage):
            return []

        normalized: List[Dict[str, Any]] = []

        tool_calls_attr = getattr(response, "tool_calls", None) or []
        for call in tool_calls_attr:
            if isinstance(call, dict):
                normalized.append(call)
                continue

            name = getattr(call, "name", None)
            args = getattr(call, "args", None)
            if not name:
                continue

            if isinstance(args, str):
                serialized_args = args
            else:
                try:
                    serialized_args = json.dumps(args or {})
                except TypeError:
                    serialized_args = json.dumps({})

            normalized.append(
                {
                    "id": getattr(call, "id", "") or "",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": serialized_args,
                    },
                }
            )

        return normalized

    async def _build_messages(
        self,
        *,
        db: DatabaseManager,
        conversation_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[LLMFileAttachmentData],
        llm_model: LLMModel,
    ) -> List[BaseMessage]:
        system_prompt = get_chat_system_prompt(db, conversation_id=conversation_id)
        messages: List[BaseMessage] = [
            SystemMessage(content=self.service._text_content_block(text=system_prompt))
        ]
        from app.services.summarizer_service import SummarizerService  # no-inline-import

        summarizer_service = SummarizerService.for_model(
            provider=self.service.provider_name, model_id=llm_model.id
        )
        summary, recent_chat_messages = await summarizer_service.get_chat_summary(
            conversation_id=conversation_id,
            chat_history=chat_history,
        )
        if summary:
            messages.append(
                HumanMessage(
                    content=self.service._text_content_block(text=f"Conversation so far: {summary}")
                )
            )

        all_file_attachments: List[DBFileAttachmentData] = db.get_file_attachments_by_message_ids(
            [msg.id for msg in recent_chat_messages]
        )
        attachment_by_message: Dict[int, List[DBFileAttachmentData]] = {}
        for file in all_file_attachments:
            if file.chat_message_id is None:
                continue
            attachment_by_message.setdefault(file.chat_message_id, []).append(file)

        for chat_msg in recent_chat_messages:
            if chat_msg.role == "user":
                content = chat_msg.content
                for attachment in attachment_by_message.get(chat_msg.id, []):
                    attachment_summary = attachment.summary_text or attachment.extracted_text or ""
                    if attachment_summary:
                        content = f"{content}\n\n[Attachment: {attachment.filename}, {attachment_summary}]"
                messages.append(
                    HumanMessage(content=self.service._text_content_block(text=content))
                )
            elif chat_msg.role == "assistant":
                messages.append(AIMessage(content=chat_msg.content))
            elif chat_msg.role == "tool":
                messages.append(ToolMessage(content=chat_msg.content, tool_call_id=""))

        messages.append(
            self.service.build_current_user_message(
                llm_model=llm_model,
                user_message=user_message,
                attached_files=attached_files,
            )
        )
        return messages

    def _build_update_idea_tool(
        self,
        *,
        db: DatabaseManager,
        idea_id: int,
        user_id: int,
    ) -> BaseTool:
        @tool("update_idea", args_schema=UpdateIdeaInput)
        async def update_idea_tool(
            *,
            title: str,
            short_hypothesis: str,
            related_work: str,
            abstract: str,
            experiments: List[str],
            expected_outcome: str,
            risk_factors_and_limitations: List[str],
        ) -> Dict[str, str]:
            """Persist a new idea version using the provided structured fields."""
            if not title.strip() or not short_hypothesis.strip() or not abstract.strip():
                raise ValueError(
                    "update_idea requires non-empty title, short_hypothesis, and abstract"
                )

            def _persist_update() -> None:
                db.create_idea_version(
                    idea_id=idea_id,
                    title=title,
                    short_hypothesis=short_hypothesis,
                    related_work=related_work,
                    abstract=abstract,
                    experiments=experiments,
                    expected_outcome=expected_outcome,
                    risk_factors_and_limitations=risk_factors_and_limitations,
                    is_manual_edit=False,
                    created_by_user_id=user_id,
                )

            await asyncio.to_thread(_persist_update)
            return {
                "status": "success",
                "message": f"✅ Idea updated successfully: {title}",
                "idea_updated": "true",
            }

        return update_idea_tool

    async def _process_tool_calls(
        self,
        *,
        tool_calls: List[Dict[str, Any]],
        update_tool: BaseTool,
    ) -> AsyncGenerator[Union[StreamStatusEvent, StreamIdeaUpdateEvent, ToolCallResult], None]:
        yield StreamStatusEvent("status", ChatStatus.EXECUTING_TOOLS.value)
        tool_messages: List[ToolMessage] = []
        idea_updated = False

        for call in tool_calls:
            function_info = call.get("function") or {}
            name = function_info.get("name") or call.get("name", "")
            arguments_payload: Any = function_info.get("arguments")
            if arguments_payload is None:
                arguments_payload = call.get("arguments")
            if arguments_payload is None and "args" in call:
                arguments_payload = call.get("args")
            if arguments_payload is None and "input" in call:
                arguments_payload = call.get("input")
            call_id = call.get("id", "")
            if name != "update_idea":
                continue

            if isinstance(arguments_payload, str):
                try:
                    arguments = json.loads(s=arguments_payload)
                except json.JSONDecodeError as exc:
                    error = f"❌ Tool validation failed: invalid JSON ({exc})"
                    tool_messages.append(ToolMessage(content=error, tool_call_id=call_id))
                    continue
            elif isinstance(arguments_payload, dict):
                arguments = arguments_payload
            else:
                error = "❌ Tool validation failed: missing arguments payload"
                tool_messages.append(ToolMessage(content=error, tool_call_id=call_id))
                continue

            yield StreamStatusEvent("status", ChatStatus.UPDATING_IDEA.value)
            try:
                result = await update_tool.ainvoke(input=arguments)
                message_text = result.get("message", "Idea updated.")
                if result.get("idea_updated") == "true":
                    idea_updated = True
                    yield StreamIdeaUpdateEvent("idea_updated", "true")
            except Exception as exc:
                logger.exception("Failed to execute update_idea tool: %s", exc)
                message_text = f"❌ Failed to update idea: {exc}"

            tool_messages.append(ToolMessage(content=message_text, tool_call_id=call_id))

        yield StreamStatusEvent("status", ChatStatus.GENERATING_RESPONSE.value)
        yield ToolCallResult(idea_updated=idea_updated, tool_results=tool_messages)
