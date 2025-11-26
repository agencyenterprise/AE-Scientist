import json
import logging
import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, cast

from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_tool_call_param import (
    ChatCompletionMessageToolCallParam,
)
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from openai.types.responses import (
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemAddedEvent,
    ResponseTextDeltaEvent,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from openai.types.shared_params.function_parameters import FunctionParameters

from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services import SummarizerService
from app.services.base_llm_service import BaseLLMService, FileAttachmentData
from app.services.chat_models import (
    ChatStatus,
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneData,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamIdeaUpdateEvent,
    StreamingResult,
    StreamStatusEvent,
    ToolCallResult,
)
from app.services.database import DatabaseManager, get_database
from app.services.pdf_service import PDFService
from app.services.prompts import format_pdf_content_for_context, get_chat_system_prompt
from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)

# Models that use OpenAI's Responses API instead of Chat Completions API
RESPONSES_API_MODELS = ["o1-pro", "o3-pro", "o3-mini"]


def _format_text_content_for_context(text_files: List[FileAttachmentData]) -> str:
    """
    Extract text content from text files for LLM context.

    Args:
        text_files: List of FileAttachmentData objects (text files only)

    Returns:
        Formatted string with text file content
    """
    if not text_files:
        return ""

    s3_service = get_s3_service()
    formatted_content = "\n\n--- Text Files ---\n"

    for file_attachment in text_files:
        formatted_content += f"\n**{file_attachment.filename}:**\n"

        try:
            # Download file content using S3 service
            file_content = s3_service.download_file_content(file_attachment.s3_key)

            # Decode text content (assuming UTF-8)
            text_content = file_content.decode("utf-8")
            formatted_content += f"{text_content}\n\n"
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to decode text file {file_attachment.filename}: {e}")
            formatted_content += f"(Unable to decode text file: {str(e)})\n\n"
        except Exception as e:
            logger.exception(f"Failed to extract text for {file_attachment.filename}: {e}")
            formatted_content += f"(Unable to read text file: {str(e)})\n\n"

    return formatted_content


def _get_chat_tools() -> List[ChatCompletionToolParam]:
    """
    Get the tools for chat.
    """
    # Define tools for OpenAI
    update_idea_params: FunctionParameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The updated idea title"},
            "short_hypothesis": {"type": "string", "description": "Short hypothesis of the idea"},
            "related_work": {
                "type": "string",
                "description": "Related work or background. Use markdown formatting.",
            },
            "abstract": {
                "type": "string",
                "description": "Abstract of the idea. Use markdown formatting.",
            },
            "experiments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of experiments",
            },
            "expected_outcome": {
                "type": "string",
                "description": "Expected outcome of the experiments",
            },
            "risk_factors_and_limitations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Risk factors and limitations",
            },
        },
        "required": [
            "title",
            "short_hypothesis",
            "related_work",
            "abstract",
            "experiments",
            "expected_outcome",
            "risk_factors_and_limitations",
        ],
    }

    tools: List[ChatCompletionToolParam] = [
        ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name="update_idea",
                description="Update the research idea with improved content. This is the primary deliverable - use when concrete improvements are ready or when the user requests updates. Use markdown formatting for bullet points, lists, and other formatting.",
                parameters=update_idea_params,
            ),
        ),
    ]
    return tools


async def _process_tool_calls(
    db: DatabaseManager,
    valid_tool_calls: List[ChoiceDeltaToolCall],
    collected_content: str,
    conversation_id: int,
    idea_id: int,
    user_id: int,
    messages: List[ChatCompletionMessageParam],
) -> AsyncGenerator[
    Union[StreamStatusEvent, StreamIdeaUpdateEvent, StreamConversationLockedEvent, ToolCallResult],
    None,
]:
    """
    Process tool calls and update messages list with tool responses.

    Args:
        db: Database manager instance
        valid_tool_calls: List of valid tool calls to process
        collected_content: Content collected from streaming response
        conversation_id: ID of the conversation
        idea_id: ID of the idea
        user_id: ID of the user
        messages: Messages list to append tool responses to

    Yields:
        Status and project update events, then boolean indicating if project was updated
    """
    idea_updated = False

    yield StreamStatusEvent("status", ChatStatus.EXECUTING_TOOLS.value)

    # Add assistant message with tool calls
    tool_calls_params = []
    for tc in valid_tool_calls:
        if tc.id and tc.function and tc.function.name and tc.function.arguments:
            tool_calls_params.append(
                ChatCompletionMessageToolCallParam(
                    id=tc.id,
                    type="function",
                    function={
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                )
            )

    messages.append(
        ChatCompletionAssistantMessageParam(
            role="assistant",
            content=collected_content,
            tool_calls=tool_calls_params,
        )
    )

    # Execute each tool call
    for i, tool_call in enumerate(valid_tool_calls):
        if not tool_call.function or not tool_call.function.arguments:
            logger.warning(f"Skipping tool call {i + 1} - missing function or arguments")
            continue

        function_name = tool_call.function.name
        logger.info(f"Processing tool call {i + 1}: {function_name}")

        try:
            function_args = json.loads(tool_call.function.arguments)
            logger.debug(f"Tool call {i + 1} arguments: {function_args}")
        except json.JSONDecodeError as e:
            logger.error(f"Tool call {i + 1} JSON decode error: {e}")
            traceback.print_exc()
            messages.append(
                ChatCompletionToolMessageParam(
                    role="tool",
                    content=f"Error: Invalid JSON arguments: {str(e)}",
                    tool_call_id=tool_call.id or "",
                )
            )
            continue

        # Execute tool functions
        if function_name == "update_idea":
            yield StreamStatusEvent("status", ChatStatus.UPDATING_IDEA.value)

            # Get all required fields
            title = function_args.get("title", "")
            short_hypothesis = function_args.get("short_hypothesis", "")
            related_work = function_args.get("related_work", "")
            abstract = function_args.get("abstract", "")
            experiments = function_args.get("experiments", [])
            expected_outcome = function_args.get("expected_outcome", "")
            risk_factors_and_limitations = function_args.get("risk_factors_and_limitations", [])

            # Validate required fields
            if not title or not short_hypothesis or not abstract:
                error_message = "❌ Tool validation failed: update_idea requires non-empty 'title', 'short_hypothesis', and 'abstract'"
                messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        content=error_message,
                        tool_call_id=tool_call.id or "",
                    )
                )
                logger.error(
                    f"Empty required arguments for update_idea: title='{title}', short_hypothesis='{short_hypothesis}', abstract length={len(abstract)}"
                )
                continue

            # Validate experiments and risks are lists
            if not isinstance(experiments, list) or not isinstance(
                risk_factors_and_limitations, list
            ):
                error_message = "❌ Tool validation failed: experiments and risk_factors_and_limitations must be arrays"
                messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        content=error_message,
                        tool_call_id=tool_call.id or "",
                    )
                )
                logger.error(
                    f"Type validation failed for update_idea: experiments={type(experiments)}, risks={type(risk_factors_and_limitations)}"
                )
                continue

            try:
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
                idea_updated = True

                updated_idea = db.get_idea_by_conversation_id(conversation_id)
                if updated_idea:
                    yield StreamIdeaUpdateEvent("idea_updated", "true")

                success_message = f"✅ Idea updated successfully: {title}"
                messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        content=success_message,
                        tool_call_id=tool_call.id or "",
                    )
                )
            except Exception as e:
                error_message = f"❌ Failed to update idea: {str(e)}"
                messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        content=error_message,
                        tool_call_id=tool_call.id or "",
                    )
                )

    logger.info(f"Finished processing all {len(valid_tool_calls)} tool calls")
    logger.debug(f"Messages now: {len(messages)} total")

    yield ToolCallResult(idea_updated=idea_updated, tool_results=[])


async def _collect_streaming_response(
    response: AsyncStream[ChatCompletionChunk],
) -> AsyncGenerator[Union[StreamContentEvent, StreamingResult], None]:
    """
    Collect content and tool calls from streaming response.

    Args:
        response: Streaming response from OpenAI

    Yields:
        Content events as they arrive, and finally a tuple of (collected_content, valid_tool_calls)
    """
    collected_content = ""
    collected_tool_calls: List[Optional[ChoiceDeltaToolCall]] = []
    chunk_count = 0

    logger.debug("Starting to iterate over async streaming response chunks...")
    async for chunk in response:
        chunk_count += 1
        logger.debug(f"Processing chunk #{chunk_count}: {chunk}")

        if chunk.choices:
            if chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                logger.debug(f"Chunk #{chunk_count} has delta: {delta}")

                # Stream content as it comes
                if delta.content:
                    collected_content += delta.content
                    logger.debug(f"Streaming content chunk #{chunk_count}: '{delta.content}'")
                    yield StreamContentEvent("content", delta.content)
                elif getattr(delta, "reasoning_content", None):
                    # Grok-specific reasoning output
                    collected_content += delta.reasoning_content  # type: ignore
                    yield StreamContentEvent("content", delta.reasoning_content)  # type: ignore
                else:
                    logger.debug(f"Chunk #{chunk_count} has no content")

                # Collect tool calls
                if delta.tool_calls:
                    logger.debug(f"Received tool call delta: {len(delta.tool_calls)} calls")
                    for i, tc in enumerate(delta.tool_calls):
                        # Extend list if needed
                        while len(collected_tool_calls) <= i:
                            collected_tool_calls.append(None)

                        if collected_tool_calls[i] is None:
                            collected_tool_calls[i] = tc
                        else:
                            # Merge tool call arguments
                            existing_tc = collected_tool_calls[i]
                            if existing_tc and tc.function and tc.function.arguments:
                                if existing_tc.function and existing_tc.function.arguments:
                                    existing_tc.function.arguments += tc.function.arguments
                                elif existing_tc.function:
                                    existing_tc.function.arguments = tc.function.arguments
            else:
                logger.debug(f"Chunk #{chunk_count} has no delta: {chunk.choices[0]}")
        else:
            logger.debug(f"Chunk #{chunk_count} has no choices")

        # Check if streaming is complete
        if chunk.choices and chunk.choices[0].finish_reason:
            logger.debug(
                f"Chunk #{chunk_count} has finish_reason: {chunk.choices[0].finish_reason}"
            )
            break
        else:
            logger.debug(f"Chunk #{chunk_count} has no finish_reason, continuing...")

    logger.info(f"Streaming response complete! Total chunks processed: {chunk_count}")
    logger.debug(
        f"Collected raw tool calls: {len([tc for tc in collected_tool_calls if tc is not None])}"
    )

    # Filter valid tool calls
    valid_tool_calls = [
        tc for tc in collected_tool_calls if tc is not None and tc.function is not None
    ]

    logger.debug(f"Collected content length: {len(collected_content)}")
    logger.info(f"Valid tool calls: {len(valid_tool_calls)}")
    if valid_tool_calls:
        for i, tc in enumerate(valid_tool_calls):
            logger.debug(f"Tool call {i + 1}: {tc.function.name if tc.function else 'None'}")

    yield StreamingResult(collected_content=collected_content, valid_tool_calls=valid_tool_calls)


class ChatWithIdeaStream:
    def __init__(self, service: BaseLLMService, summarizer_service: SummarizerService):
        self.service = service
        self.summarizer_service = summarizer_service

    async def _build_chat_completions_messages(
        self,
        db: DatabaseManager,
        conversation_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
    ) -> List[ChatCompletionMessageParam]:
        """
        Build messages for the Chat Completions API using OpenAI chat types.

        Args:
            db: Database manager instance
            conversation_id: ID of the conversation to get original context and idea
            user_message: Current user message
            chat_history: Previous chat messages
            attached_files: List of FileAttachmentData objects
            model: LLMModel
        Returns:
            List of ChatCompletionMessageParam for chat completions.
        """
        system_prompt = get_chat_system_prompt(db, conversation_id=conversation_id)

        logger.debug("Using system prompt with original conversation context")
        messages: List[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ]

        # History compaction: digest + last-N
        summary, recent_chat_messages = await self.summarizer_service.get_chat_summary(
            conversation_id=conversation_id,
            chat_history=chat_history,
        )
        if summary:
            messages.append(
                ChatCompletionUserMessageParam(
                    role="user", content=f"Conversation so far: {summary}"
                )
            )
        all_file_attachments = db.get_file_attachments_by_message_ids(
            [msg.id for msg in recent_chat_messages]
        )
        # We only want to get the file attachments that were not uploaded in the current message
        old_file_attachments = [
            f for f in all_file_attachments if f.id not in [a.id for a in attached_files]
        ]

        for chat_msg in recent_chat_messages:
            if chat_msg.role == "user":
                user_chat_msg_content = chat_msg.content
                for attachment in [
                    f for f in old_file_attachments if f.chat_message_id == chat_msg.id
                ]:
                    attachment_content = attachment.summary_text or attachment.extracted_text
                    if attachment_content:
                        user_chat_msg_content += (
                            f"\n\n[Attachment: {attachment.filename}, {attachment_content}]"
                        )
                messages.append(
                    ChatCompletionUserMessageParam(role="user", content=user_chat_msg_content)
                )
            elif chat_msg.role == "assistant":
                messages.append(
                    ChatCompletionAssistantMessageParam(role="assistant", content=chat_msg.content)
                )

        # Add current user message with proper handling for images, PDFs, and text files
        image_attachments = [f for f in attached_files if f.file_type.startswith("image/")]
        pdf_attachments = [f for f in attached_files if f.file_type == "application/pdf"]
        text_attachments = [f for f in attached_files if f.file_type == "text/plain"]

        # Start with the user message text
        user_content = user_message

        # Add PDF text content to the message text (OpenAI doesn't have native PDF support like Anthropic)
        if pdf_attachments:
            s3_service = get_s3_service()
            pdf_service = PDFService()
            user_content = user_content + format_pdf_content_for_context(
                pdf_attachments, s3_service, pdf_service
            )

        # Add text file content to the message text
        if text_attachments:
            user_content += _format_text_content_for_context(text_attachments)

        # For images, create proper vision model content with OpenAI format
        if image_attachments:
            s3_service = get_s3_service()

            # Chat completions API format
            content: List[Dict[str, Any]] = [{"type": "text", "text": user_content}]

            def format_image_for_completions(url: str) -> Dict[str, Any]:
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                    },
                }

            for image_attachment in image_attachments:
                try:
                    image_url = s3_service.generate_download_url(image_attachment.s3_key)
                    content.append(format_image_for_completions(image_url))
                except Exception:
                    logger.exception(
                        f"Failed to generate URL for image {image_attachment.filename}"
                    )

            messages.append(ChatCompletionUserMessageParam(role="user", content=content))  # type: ignore
        else:
            # Text-only message
            messages.append(ChatCompletionUserMessageParam(role="user", content=user_content))

        return messages

    async def _build_chat_responses_messages(
        self,
        db: DatabaseManager,
        conversation_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
    ) -> List[Dict[str, Any]]:
        """
        Build messages for the Responses API input (list of role/content blocks).

        Args:
            db: Database manager instance
            conversation_id: ID of the conversation to get original context and idea
            user_message: Current user message
            chat_history: Previous chat messages
            attached_files: List of FileAttachmentData objects
            model: LLMModel

        Returns:
            List of dicts suitable for the Responses API "input" parameter.
        """
        system_prompt = get_chat_system_prompt(db, conversation_id=conversation_id)

        input_messages: List[Dict[str, Any]] = []

        # System message
        input_messages.append(
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_prompt,
                    }
                ],
            }
        )

        summary, recent_chat_messages = await self.summarizer_service.get_chat_summary(
            conversation_id=conversation_id,
            chat_history=chat_history,
        )
        if summary:
            input_messages.append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": f"Conversation so far: {summary}"}],
                }
            )
        all_file_attachments = db.get_file_attachments_by_message_ids(
            [msg.id for msg in recent_chat_messages]
        )
        # We only want to get the file attachments that were not uploaded in the current message
        old_file_attachments = [
            f for f in all_file_attachments if f.id not in [a.id for a in attached_files]
        ]
        for chat_msg in recent_chat_messages:
            msg_content = chat_msg.content
            if chat_msg.role == "user":
                for attachment in [
                    f for f in old_file_attachments if f.chat_message_id == chat_msg.id
                ]:
                    attachment_content = attachment.summary_text or attachment.extracted_text
                    if attachment_content:
                        msg_content += (
                            f"\n\n[Attachment: {attachment.filename}, {attachment_content}]"
                        )
            input_messages.append(
                {
                    "role": chat_msg.role,
                    "content": [
                        {
                            "type": "input_text",
                            "text": msg_content,
                        }
                    ],
                }
            )

        # Current user message with attachments
        image_attachments = [f for f in attached_files if f.file_type.startswith("image/")]
        pdf_attachments = [f for f in attached_files if f.file_type == "application/pdf"]
        text_attachments = [f for f in attached_files if f.file_type == "text/plain"]

        user_content = user_message

        if pdf_attachments:
            s3_service = get_s3_service()
            pdf_service = PDFService()

            user_content = user_content + format_pdf_content_for_context(
                pdf_attachments, s3_service, pdf_service
            )

        if text_attachments:
            user_content += _format_text_content_for_context(text_attachments)

        # Build content blocks for responses API
        content_blocks: List[Dict[str, Any]] = [{"type": "input_text", "text": user_content}]

        if image_attachments:
            s3_service = get_s3_service()
            for image_attachment in image_attachments:
                try:
                    image_url = s3_service.generate_download_url(image_attachment.s3_key)
                    content_blocks.append({"type": "input_image", "image_url": image_url})
                except Exception:
                    logger.exception(
                        f"Failed to generate URL for image {image_attachment.filename}"
                    )

            # Ensure the final updated user_content (with any image summaries) is reflected
            # in the first text block that was created before processing images.
            try:
                content_blocks[0]["text"] = user_content
            except Exception:
                logger.exception("Failed to update content_blocks text with image summaries")

        input_messages.append({"role": "user", "content": content_blocks})

        return input_messages

    async def chat_with_idea_stream(
        self,
        client: AsyncOpenAI,
        model: LLMModel,
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
        idea_updated = False
        full_assistant_response = ""

        # Build messages using helper function
        db = get_database()
        is_completions_api = model.id not in RESPONSES_API_MODELS
        if is_completions_api:
            messages = await self._build_chat_completions_messages(
                db=db,
                conversation_id=conversation_id,
                user_message=user_message,
                chat_history=chat_history,
                attached_files=attached_files,
            )
        else:
            responses_input = await self._build_chat_responses_messages(
                db=db,
                conversation_id=conversation_id,
                user_message=user_message,
                chat_history=chat_history,
                attached_files=attached_files,
            )
            messages = []  # not used for responses API path
        tools = _get_chat_tools()
        try:
            yield StreamStatusEvent("status", ChatStatus.ANALYZING_REQUEST.value)

            # Single streaming loop - continue until no more tool calls
            while True:
                response: Any = None
                logger.info(f"Making streaming call with {len(messages)} messages")
                logger.debug(f"Model: {model}, tools: {len(tools)}, stream: True")

                # These models use v1/responses instead of v1/chat/completions
                if model.id in RESPONSES_API_MODELS:
                    # Build tools for responses API
                    responses_tools = []
                    for tool in tools:
                        if tool.get("type") == "function" and tool.get("function"):
                            func = tool["function"]
                            # Ensure parameters have additionalProperties: false for responses API
                            parameters = func.get("parameters", {})
                            if (
                                isinstance(parameters, dict)
                                and "additionalProperties" not in parameters
                            ):
                                parameters = parameters.copy()
                                parameters["additionalProperties"] = False

                            responses_tools.append(
                                {
                                    "type": "function",
                                    "name": func.get("name"),
                                    "description": func.get("description"),
                                    "parameters": parameters,
                                    "strict": True,
                                }
                            )

                    if responses_tools:
                        response = await client.responses.create(
                            model=model.id,
                            input=cast(Any, responses_input),
                            stream=True,
                            tools=cast(Any, responses_tools),
                        )
                    else:
                        response = await client.responses.create(
                            model=model.id,
                            input=cast(Any, responses_input),
                            stream=True,
                        )
                else:
                    # Use chat completions for other models
                    if model.id in [
                        "gpt-5",
                        "gpt-5-nano",
                        "gpt-5-mini",
                        "gpt-5.1",
                        "o1",
                        "o3",
                        "o3-mini",
                        "o3-pro",
                    ]:
                        response = await client.chat.completions.create(
                            model=model.id,
                            messages=messages,
                            tools=tools,
                            stream=True,
                            max_completion_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
                        )
                    else:
                        response = await client.chat.completions.create(
                            model=model.id,
                            messages=messages,
                            tools=tools,
                            stream=True,
                            max_tokens=settings.IDEA_MAX_COMPLETION_TOKENS,
                        )

                logger.debug(
                    f"Async streaming response object created successfully: {type(response)}"
                )

                # Handle different response formats
                collected_content = ""
                valid_tool_calls: List[ChoiceDeltaToolCall] = []

                if model.id in RESPONSES_API_MODELS:
                    # Process responses API format: collect content and tool calls using typed events
                    chunk_count = 0
                    # Accumulate tool call state by output_index
                    tool_calls_accum: Dict[int, Dict[str, str]] = {}
                    async for event in cast(AsyncStream[object], response):
                        chunk_count += 1

                        # Text deltas
                        if isinstance(event, ResponseTextDeltaEvent):
                            collected_content += event.delta
                            # Print raw content chunks for Responses API
                            logger.debug(
                                f"📄 RESP content chunk ({len(event.delta)} chars): {event.delta}"
                            )
                            yield StreamContentEvent("content", event.delta)

                        # A function tool call item was added, capture id and name
                        elif isinstance(event, ResponseOutputItemAddedEvent):
                            if isinstance(event.item, ResponseFunctionToolCall):
                                idx = event.output_index
                                tool_id = event.item.id or event.item.call_id
                                logger.debug(
                                    f"🛠️ RESP tool call started (idx {idx}): name={event.item.name}, id={tool_id}"
                                )
                                tool_calls_accum[idx] = {
                                    "id": tool_id or "",
                                    "name": event.item.name or "",
                                    "args": "",
                                }

                        # Streaming function-call args chunks
                        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
                            idx = event.output_index
                            entry = tool_calls_accum.setdefault(
                                idx, {"id": "", "name": "", "args": ""}
                            )
                            entry["args"] += event.delta or ""

                        # Final function-call args
                        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
                            idx = event.output_index
                            entry = tool_calls_accum.setdefault(
                                idx, {"id": "", "name": "", "args": ""}
                            )
                            entry["args"] = event.arguments or entry["args"]
                            logger.debug(f"✅ RESP tool args done (idx {idx}): {entry['args']}")

                else:
                    # Use existing chat completions processing

                    async for item in _collect_streaming_response(
                        cast(AsyncStream[ChatCompletionChunk], response)
                    ):
                        if isinstance(item, StreamContentEvent):
                            # Forward content events to caller
                            full_assistant_response += item.data
                            logger.debug(
                                f"Full response length now: {len(full_assistant_response)}"
                            )
                            yield item
                        elif isinstance(item, StreamingResult):
                            # This is the final result
                            collected_content = item.collected_content
                            valid_tool_calls = item.valid_tool_calls

                logger.debug(f"Collected content length: {len(collected_content)}")
                logger.debug(f"Valid tool calls: {len(valid_tool_calls)}")

                # Convert any responses-API tool calls into ChoiceDeltaToolCall shape
                if model.id in RESPONSES_API_MODELS and tool_calls_accum:
                    try:
                        converted: List[ChoiceDeltaToolCall] = []
                        for idx in sorted(tool_calls_accum.keys()):
                            tc = tool_calls_accum[idx]
                            # Build a minimal ChoiceDeltaToolCall-like object via SimpleNamespace
                            fn_args = tc.get("args", "")
                            converted.append(
                                ChoiceDeltaToolCall(
                                    index=idx,
                                    id=tc.get("id", ""),
                                    type="function",
                                    function=ChoiceDeltaToolCallFunction(
                                        name=tc.get("name", ""), arguments=fn_args
                                    ),
                                )
                            )
                            logger.debug(
                                f"RESP tool call assembled (idx {idx}): name={tc.get('name', '')}, args={fn_args}"
                            )
                        valid_tool_calls = converted
                    except Exception:
                        logger.exception(
                            "Failed to convert responses tool calls; continuing without tools"
                        )

                if valid_tool_calls:
                    # Process tool calls using helper function
                    async for tool_item in _process_tool_calls(
                        db=db,
                        valid_tool_calls=valid_tool_calls,
                        collected_content=collected_content,
                        conversation_id=conversation_id,
                        idea_id=idea_id,
                        user_id=user_id,
                        messages=messages,
                    ):
                        if isinstance(tool_item, ToolCallResult):
                            # This is the final result with idea update status
                            if tool_item.idea_updated:
                                idea_updated = True
                        elif isinstance(tool_item, StreamConversationLockedEvent):
                            # Forward conversation locked event and stop processing
                            yield tool_item
                            # End the stream immediately after locking
                            yield StreamDoneEvent(
                                "done",
                                StreamDoneData(
                                    idea_updated=idea_updated,
                                    assistant_response=full_assistant_response,
                                ),
                            )
                            return
                        else:
                            # Forward status and project update events
                            yield tool_item

                    # Clear status message after tool execution
                    yield StreamStatusEvent("status", ChatStatus.GENERATING_RESPONSE.value)

                    # For Responses API models, end after one tool execution to avoid re-looping
                    if model.id in RESPONSES_API_MODELS:
                        yield StreamStatusEvent("status", ChatStatus.DONE.value)
                        yield StreamDoneEvent(
                            "done",
                            StreamDoneData(
                                idea_updated=idea_updated,
                                assistant_response=full_assistant_response,
                            ),
                        )
                        return

                    # Chat Completions models continue the loop with tool results
                    continue
                else:
                    logger.debug(
                        f"No tool calls found, finishing with content: '{collected_content}'"
                    )
                    # No tool calls, we're done
                    break

            # Clear status before sending done event
            yield StreamStatusEvent("status", ChatStatus.DONE.value)

            logger.info(
                f"Sending done event - idea_updated: {idea_updated}, response length: {len(full_assistant_response)}"
            )
            yield StreamDoneEvent(
                "done",
                StreamDoneData(
                    idea_updated=idea_updated,
                    assistant_response=full_assistant_response,
                ),
            )

        except Exception as e:
            logger.exception(f"Error in chat_with_idea_stream: {str(e)}")
            yield StreamErrorEvent("error", f"An error occurred: {str(e)}")
