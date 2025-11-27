"""LangChain-powered base service that removes per-provider duplication."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
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
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services import SummarizerService
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
)
from app.services.s3_service import S3Service, get_s3_service

logger = logging.getLogger(__name__)


class LangChainLLMService(BaseLLMService, ABC):
    """Shared LangChain implementation that works across providers."""

    def __init__(
        self,
        *,
        summarizer_service: SummarizerService,
        supported_models: Sequence[LLMModel],
        provider_name: str,
    ) -> None:
        if not supported_models:
            raise ValueError("supported_models cannot be empty")

        self.summarizer_service = summarizer_service
        self._supported_models = list(supported_models)
        self.provider_name = provider_name
        self._model_cache: Dict[str, BaseChatModel] = {}
        self._s3_service = get_s3_service()
        self._pdf_service = PDFService()
        self._chat_stream = LangChainChatWithIdeaStream(
            service=self,
            summarizer_service=summarizer_service,
        )

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

    def _message_to_text(self, *, message: AIMessage) -> str:
        content: Any = message.content
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_value = item.get("text", "")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            return "".join(parts).strip()
        return str(content)

    def _extract_text_from_chunk(
        self,
        *,
        chunk: Union[ChatGenerationChunk, AIMessage, AIMessageChunk, BaseMessage],
    ) -> str:
        if isinstance(chunk, ChatGenerationChunk):
            message = chunk.message
            message_content: Any = getattr(message, "content", "")
        else:
            message_content = getattr(chunk, "content", "")
        if isinstance(message_content, str):
            return message_content
        elif isinstance(message_content, list):
            deltas: List[str] = []
            for item in message_content:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text":
                        text_value = item.get("text", "")
                        if isinstance(text_value, str):
                            deltas.append(text_value)
                    elif item_type == "reasoning":
                        reasoning_text = item.get("text", "")
                        if isinstance(reasoning_text, str):
                            deltas.append(reasoning_text)
            return "".join(deltas)
        return str(message_content)

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

        return HumanMessage(content=user_text)

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

    async def _stream_text(
        self,
        *,
        llm_model: str,
        messages: List[BaseMessage],
        max_completion_tokens: int,
    ) -> AsyncGenerator[str, None]:
        model = self._model_with_token_limit(
            llm_model=llm_model,
            max_output_tokens=max_completion_tokens,
        )
        async for chunk in model.astream(input=messages):
            delta = self._extract_text_from_chunk(chunk=cast(ChatGenerationChunk, chunk))
            if delta:
                yield delta

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
            "Analyze this conversation and generate a research idea:\n\n" f"{conversation_text}"
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        async for chunk in self._stream_text(
            llm_model=llm_model,
            messages=messages,
            max_completion_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
        ):
            yield chunk

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

    def _parse_idea_response(self, content: str) -> LLMIdeaGeneration:
        title_match = re.search(r"<title>(.*?)</title>", content, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        short_hypothesis_match = re.search(
            r"<short_hypothesis>(.*?)</short_hypothesis>",
            content,
            re.DOTALL,
        )
        short_hypothesis = short_hypothesis_match.group(1).strip() if short_hypothesis_match else ""

        related_work_match = re.search(r"<related_work>(.*?)</related_work>", content, re.DOTALL)
        related_work = related_work_match.group(1).strip() if related_work_match else ""

        abstract_match = re.search(r"<abstract>(.*?)</abstract>", content, re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else ""

        experiments_match = re.search(r"<experiments>(.*?)</experiments>", content, re.DOTALL)
        experiments_raw = experiments_match.group(1).strip() if experiments_match else "[]"
        experiments: List[str]
        try:
            parsed_experiments = json.loads(experiments_raw)
            if isinstance(parsed_experiments, list):
                experiments = [str(item) for item in parsed_experiments]
            else:
                experiments = [str(parsed_experiments)]
        except json.JSONDecodeError:
            experiments = [experiments_raw]

        expected_outcome_match = re.search(
            r"<expected_outcome>(.*?)</expected_outcome>",
            content,
            re.DOTALL,
        )
        expected_outcome = expected_outcome_match.group(1).strip() if expected_outcome_match else ""

        risk_match = re.search(
            r"<risk_factors_and_limitations>(.*?)</risk_factors_and_limitations>",
            content,
            re.DOTALL,
        )
        risk_raw = risk_match.group(1).strip() if risk_match else "[]"
        risk_factors_and_limitations: List[str]
        try:
            parsed_risk = json.loads(risk_raw)
            if isinstance(parsed_risk, list):
                risk_factors_and_limitations = [str(item) for item in parsed_risk]
            else:
                risk_factors_and_limitations = [str(parsed_risk)]
        except json.JSONDecodeError:
            risk_factors_and_limitations = [risk_raw]

        if not title or not short_hypothesis or not abstract:
            raise ValueError("Failed to parse required fields from response.")

        return LLMIdeaGeneration(
            title=title,
            short_hypothesis=short_hypothesis,
            related_work=related_work,
            abstract=abstract,
            experiments=experiments,
            expected_outcome=expected_outcome,
            risk_factors_and_limitations=risk_factors_and_limitations,
        )


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

    def __init__(
        self, *, service: LangChainLLMService, summarizer_service: SummarizerService
    ) -> None:
        self.service = service
        self.summarizer_service = summarizer_service

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
        model = tool_bound_model.bind(max_tokens=settings.IDEA_MAX_COMPLETION_TOKENS)

        idea_updated = False
        assistant_response = ""

        try:
            yield StreamStatusEvent("status", ChatStatus.ANALYZING_REQUEST.value)
            while True:
                response = await model.ainvoke(input=messages)
                tool_calls = getattr(response, "additional_kwargs", {}).get("tool_calls") or []
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
                    messages.append(
                        AIMessage(
                            content=response.content,
                            additional_kwargs={"tool_calls": tool_calls},
                        )
                    )
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                    continue

                final_message = cast(AIMessage, response)
                final_text = self.service._message_to_text(message=final_message)
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
        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        summary, recent_chat_messages = await self.summarizer_service.get_chat_summary(
            conversation_id=conversation_id,
            chat_history=chat_history,
        )
        if summary:
            messages.append(HumanMessage(content=f"Conversation so far: {summary}"))

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
                messages.append(HumanMessage(content=content))
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
        def update_idea_tool(
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
            name = function_info.get("name", "")
            arguments_str = function_info.get("arguments", "")
            call_id = call.get("id", "")
            if name != "update_idea":
                continue

            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError as exc:
                error = f"❌ Tool validation failed: invalid JSON ({exc})"
                tool_messages.append(ToolMessage(content=error, tool_call_id=call_id))
                continue

            yield StreamStatusEvent("status", ChatStatus.UPDATING_IDEA.value)
            try:
                result = update_tool.invoke(arguments)
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
