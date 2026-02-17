"""LangChain-powered base service that removes per-provider duplication."""

import json
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Sequence, Union, cast

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
from pydantic import BaseModel, Field

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services.base_llm_service import BaseLLMService
from app.services.base_llm_service import FileAttachmentData as LLMFileAttachmentData
from app.services.billing_guard import charge_for_llm_usage
from app.services.chat_models import (
    ChatStatus,
    StreamContentEvent,
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
from app.services.prompts.render import render_text
from app.services.s3_service import S3Service, get_s3_service

logger = logging.getLogger(__name__)

THINKING_TAG_PATTERN = re.compile(r"<thinking>.*?</thinking>\s*", re.IGNORECASE | re.DOTALL)


class IdeaGenerationOutput(BaseModel):
    """Structured output schema for idea generation."""

    title: str = Field(..., description="The title of the research idea")
    content: str = Field(
        ...,
        description="The research idea content in markdown format with sections: Project Summary, Idea Description, Proposed Experiments, Expected Outcome, Key Considerations",
    )


def get_idea_max_completion_tokens(model: BaseChatModel) -> int:
    model_max_output_tokens = (
        model.profile.get("max_output_tokens", settings.idea_max_completion_tokens)
        if model.profile
        else settings.idea_max_completion_tokens
    )
    return min(settings.idea_max_completion_tokens, model_max_output_tokens)


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
        """Return a LangChain chat model for the given provider:model id."""

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

    def _message_to_text(self, *, message: AIMessage, strip: bool = True) -> str:
        content: Any = message.content
        if isinstance(content, str):
            return content.strip() if strip else content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_value = item.get("text", "")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            joined = "".join(parts)
            return joined.strip() if strip else joined
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
        user_id: int,
        conversation_id: int,
        skip_billing: bool,
    ) -> AsyncGenerator[str, None]:
        db = get_database()
        system_prompt = await get_idea_generation_prompt(db=db)
        user_prompt = render_text(
            template_name="idea_generation_user.txt.j2",
            context={"conversation_text": conversation_text},
        )
        messages = [
            SystemMessage(content=self._text_content_block(text=system_prompt)),
            HumanMessage(content=self._text_content_block(text=user_prompt)),
        ]
        async for event_payload in self._stream_structured_schema_response(
            llm_model=llm_model,
            messages=messages,
            conversation_id=conversation_id,
            user_id=user_id,
            skip_billing=skip_billing,
        ):
            yield event_payload

    def generate_manual_seed_idea_prompt(self, *, idea_title: str, idea_hypothesis: str) -> str:
        """
        Generate a user prompt for a manual seed idea.
        """
        return render_text(
            template_name="manual_seed_user.txt.j2",
            context={"idea_title": idea_title, "idea_hypothesis": idea_hypothesis},
        )

    async def generate_manual_seed_idea(
        self,
        *,
        llm_model: str,
        user_prompt: str,
        conversation_id: int,
        user_id: int,
        skip_billing: bool,
    ) -> AsyncGenerator[str, None]:
        """
        Generate an idea from a manual title and hypothesis seed.
        """
        db = get_database()
        system_prompt = await get_manual_seed_prompt(db=db)
        messages = [
            SystemMessage(content=self._text_content_block(text=system_prompt)),
            HumanMessage(content=self._text_content_block(text=user_prompt)),
        ]
        async for event_payload in self._stream_structured_schema_response(
            llm_model=llm_model,
            messages=messages,
            conversation_id=conversation_id,
            user_id=user_id,
            skip_billing=skip_billing,
        ):
            yield event_payload

    async def _stream_structured_schema_response(
        self,
        *,
        llm_model: str,
        messages: List[BaseMessage],
        conversation_id: int,
        user_id: int,
        skip_billing: bool,
    ) -> AsyncGenerator[str, None]:
        """Generate idea using structured output with real-time streaming via tool calling."""

        base_model = self.get_or_create_model(llm_model=llm_model)
        max_tokens = get_idea_max_completion_tokens(base_model)

        # Use tool calling for streaming structured output
        tool_bound_model = base_model.bind_tools(
            [IdeaGenerationOutput],
            tool_choice="any",
        )

        accumulated_arguments: Dict[int, str] = defaultdict(str)
        latest_emitted_title: str = ""
        latest_emitted_content: str = ""
        active_tool_index: int | None = None
        last_chunk_metadata: Dict[str, Any] | None = None
        db = get_database()

        async for chunk in tool_bound_model.astream(input=messages, max_tokens=max_tokens):
            if not isinstance(chunk, AIMessageChunk):
                continue

            # Track token usage from final chunk
            if isinstance(chunk, AIMessage):
                metadata = chunk.usage_metadata
                if metadata:
                    input_tokens = int(cast(Any, metadata.get("input_tokens", 0)) or 0)
                    cached_input_tokens = int(
                        cast(Any, metadata.get("cached_input_tokens", 0)) or 0
                    )
                    output_tokens = int(cast(Any, metadata.get("output_tokens", 0)) or 0)
                    await db.create_llm_token_usage(
                        conversation_id=conversation_id,
                        provider=self.provider_name,
                        model=llm_model,
                        input_tokens=input_tokens,
                        cached_input_tokens=cached_input_tokens,
                        output_tokens=output_tokens,
                    )
                    if not skip_billing:
                        await charge_for_llm_usage(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            provider=self.provider_name,
                            model=llm_model,
                            input_tokens=input_tokens,
                            cached_input_tokens=cached_input_tokens,
                            output_tokens=output_tokens,
                            description="Idea generation",
                        )

            last_chunk_metadata = getattr(chunk, "response_metadata", None)

            for tool_chunk in chunk.tool_call_chunks:
                # Use index as grouping key (default to 0 if not set)
                tool_index = tool_chunk.get("index")
                if tool_index is None:
                    tool_index = 0

                # Accumulate arguments
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

                # Parse partial JSON to extract title and content
                try:
                    partial = parse_partial_json(accumulated_arguments[tool_index])
                    if not isinstance(partial, dict):
                        continue

                    # Emit title updates
                    if "title" in partial:
                        title_value = partial["title"]
                        if isinstance(title_value, str) and title_value != latest_emitted_title:
                            latest_emitted_title = title_value
                            # Yield markdown delta for title
                            yield json.dumps(
                                {"event": "markdown_delta", "data": f"# {title_value}\n\n"}
                            )

                    # Emit content updates
                    if "content" in partial:
                        content_value = partial["content"]
                        if isinstance(content_value, str):
                            # Only yield the new part of content
                            if content_value.startswith(latest_emitted_content):
                                new_content = content_value[len(latest_emitted_content) :]
                                if new_content:
                                    latest_emitted_content = content_value
                                    yield json.dumps(
                                        {"event": "markdown_delta", "data": new_content}
                                    )
                            elif content_value != latest_emitted_content:
                                # Content changed non-incrementally, emit full content
                                latest_emitted_content = content_value
                                yield json.dumps({"event": "markdown_delta", "data": content_value})
                except Exception:
                    # Ignore parsing errors during streaming
                    pass

        if active_tool_index is None:
            raise ValueError("LLM did not return structured idea payload.")

        # Check for truncation
        finish_reason = ""
        if last_chunk_metadata:
            finish_reason = last_chunk_metadata.get("finish_reason", "")
            if finish_reason == "length":
                logger.warning("Idea generation response was truncated due to max_tokens limit")
                raise ValueError(
                    "Idea generation was truncated. The response exceeded the token limit."
                )

        # Parse final payload
        final_payload = accumulated_arguments[active_tool_index]
        if not final_payload.strip():
            raise ValueError("LLM returned empty structured idea payload.")

        try:
            final_data = json.loads(final_payload)
            title = final_data.get("title", "")
            content = final_data.get("content", "")

            if not title or not content:
                raise ValueError("LLM did not provide valid title and content.")

            # Yield final structured data
            yield json.dumps(
                {"event": "structured_idea_data", "data": {"title": title, "content": content}}
            )
        except json.JSONDecodeError:
            raise ValueError("LLM returned invalid JSON payload.")

    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        return await self._summarize_document(llm_model=llm_model, content=content)

    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        if not llm_model.supports_images:
            raise ValueError(f"Model {llm_model.id} does not support image inputs")
        system_prompt = render_text(template_name="image_description/system.txt.j2")
        user_instruction = render_text(template_name="image_description/user_instruction.txt.j2")
        content_blocks = self.render_image_url(image_url=image_url)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_instruction},
                    *content_blocks,
                ]
            ),
        ]
        response = await self._model_with_token_limit(
            llm_model=llm_model.id,
            max_output_tokens=settings.idea_max_completion_tokens,
        ).ainvoke(input=messages)
        if not isinstance(response, AIMessage):
            return ""
        return self._message_to_text(message=response)

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


class UpdateIdeaInput(BaseModel):
    title: str = Field(
        ...,
        description="The title of the research idea",
    )
    idea_markdown: str = Field(
        ...,
        description="Complete idea content in markdown format with sections: Project Summary, Related Work, Abstract, Experiments, Expected Outcome, Risk Factors and Limitations. Do NOT include the title as a header.",
    )


class LangChainChatWithIdeaStream:
    """Shared streaming implementation for LangChain chat models."""

    def __init__(self, *, service: LangChainLLMService) -> None:
        self.service = service
        self.db = get_database()

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
                # Accumulate chunks to build complete response and check for tool calls
                accumulated_message: BaseMessage | None = None
                streamed_content_chunks: List[str] = []
                has_started_streaming = False

                async for chunk in model.astream(input=messages):
                    if not isinstance(chunk, AIMessageChunk):
                        continue

                    # Accumulate the message
                    if accumulated_message is None:
                        accumulated_message = chunk
                    else:
                        accumulated_message = cast(BaseMessage, accumulated_message + chunk)

                    # Track token usage from chunks with metadata
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        metadata = chunk.usage_metadata
                        input_tokens = int(cast(Any, metadata.get("input_tokens", 0)) or 0)
                        cached_input_tokens = int(
                            cast(Any, metadata.get("cached_input_tokens", 0)) or 0
                        )
                        output_tokens = int(cast(Any, metadata.get("output_tokens", 0)) or 0)
                        if input_tokens > 0 or output_tokens > 0:
                            await self.db.create_llm_token_usage(
                                conversation_id=conversation_id,
                                provider=llm_model.provider,
                                model=llm_model.id,
                                input_tokens=input_tokens,
                                cached_input_tokens=cached_input_tokens,
                                output_tokens=output_tokens,
                            )

                            await charge_for_llm_usage(
                                conversation_id=conversation_id,
                                provider=llm_model.provider,
                                model=llm_model.id,
                                input_tokens=input_tokens,
                                cached_input_tokens=cached_input_tokens,
                                output_tokens=output_tokens,
                                user_id=user_id,
                                description="Idea chat",
                            )

                    # Check if we have tool calls - if so, don't stream content
                    tool_calls: List[Dict[str, Any]] = self._normalize_tool_calls(
                        response=accumulated_message
                    )
                    if tool_calls:
                        # Tool calls detected, wait for full response and process tools
                        continue

                    # No tool calls - stream content as it arrives
                    if chunk.content:
                        # Don't strip individual chunks to preserve spaces between words
                        content_text = self.service._message_to_text(message=chunk, strip=False)
                        # Remove thinking tags but preserve whitespace
                        content_text = THINKING_TAG_PATTERN.sub("", content_text)
                        if content_text:
                            if not has_started_streaming:
                                yield StreamStatusEvent(
                                    "status", ChatStatus.GENERATING_RESPONSE.value
                                )
                                has_started_streaming = True
                            streamed_content_chunks.append(content_text)
                            yield StreamContentEvent("content", content_text)

                # Stream completed, check accumulated message
                if accumulated_message is None:
                    break

                # Check for tool calls in final accumulated message
                tool_calls = self._normalize_tool_calls(response=accumulated_message)
                if tool_calls:
                    # Process tool calls and continue loop
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
                    messages.append(accumulated_message)
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                    continue

                # No tool calls - final text response
                final_text = "".join(streamed_content_chunks).strip()
                if final_text:
                    assistant_response = final_text
                messages.append(accumulated_message)
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
        system_prompt = await get_chat_system_prompt(db, conversation_id=conversation_id)
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

        all_file_attachments: List[DBFileAttachmentData] = (
            await db.get_file_attachments_by_message_ids([msg.id for msg in recent_chat_messages])
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
            idea_markdown: str,
        ) -> Dict[str, str]:
            """Persist a new idea version using the provided title and markdown content."""
            if not title.strip():
                raise ValueError("update_idea requires a non-empty title")
            if not idea_markdown.strip() or len(idea_markdown.strip()) < 50:
                raise ValueError(
                    "update_idea requires non-empty markdown content with at least 50 characters"
                )

            await db.create_idea_version(
                idea_id=idea_id,
                title=title,
                idea_markdown=idea_markdown,
                is_manual_edit=False,
                created_by_user_id=user_id,
            )
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
