"""
Anthropic (Claude) service for generating conversation summaries and project drafts.

This module handles communication with Anthropic API to generate summaries
of conversations and transform them into structured project proposals.
"""

import base64
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, NamedTuple, Union

import anthropic
from anthropic.types import MessageParam
from app.config import settings
from app.models import ChatMessageData, LLMModel
from app.services import SummarizerService
from app.services.base_llm_service import BaseLLMService, FileAttachmentData, LLMProjectGeneration
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneData,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamProjectUpdateEvent,
    StreamStatusEvent,
    ToolCallResult,
)
from app.services.database import DatabaseManager, get_database
from app.services.linear_service import LinearService
from app.services.mem0_service import Mem0Service
from app.services.prompts import get_chat_system_prompt, get_project_generation_prompt
from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)
mem0 = Mem0Service()


class ClaudeToolCall(NamedTuple):
    """Represents a tool call from Claude's streaming API."""

    id: str
    name: str
    input: dict


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


class AnthropicService(BaseLLMService):
    """Service for interacting with Anthropic (Claude) API."""

    def __init__(self, summarizer_service: SummarizerService) -> None:
        """Initialize the Anthropic service."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        # Initialize async Anthropic client
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.summarizer_service = summarizer_service

    async def generate_imported_chat_keywords(
        self, llm_model: str, imported_conversation_text: str
    ) -> str:
        return await self._generate_imported_chat_keywords(
            llm_model=llm_model, conversation_text=imported_conversation_text
        )

    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        return await self._summarize_document(llm_model=llm_model, content=content)

    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        """Generate a concise, information-dense caption for an image via Anthropic."""
        # Construct multi-modal content with an image URL block
        system_prompt = (
            "You are an expert image describer. Provide a concise but information-dense description "
            "covering scene, key objects, visible text, layout, and any notable anomalies."
        )
        api_messages: List[MessageParam] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please describe this image precisely:"},
                    {
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": image_url,
                        },
                    },
                ],
            }
        ]

        response = await self.client.messages.create(
            model=llm_model.id,
            max_tokens=3000,
            system=system_prompt,
            messages=api_messages,
        )

        caption = ""
        if response.content:
            for block in response.content:
                if block.type == "text":
                    caption += block.text
        return caption.strip()

    def get_context_window_tokens(self, llm_model: str) -> int:
        for model in SUPPORTED_MODELS:
            if model.id == llm_model:
                return model.context_window_tokens
        raise ValueError(f"Unknown Anthropic model for context window: {llm_model}")

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
        """Single non-streaming text generation via Anthropic Messages API."""
        api_messages: List[MessageParam] = [
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ]
        response = await self.client.messages.create(
            model=llm_model,
            max_tokens=max_completion_tokens,
            system=system_prompt,
            messages=api_messages,
        )
        out = ""
        if response.content:
            for block in response.content:
                if block.type == "text":
                    out += block.text
        return out.strip()

    async def generate_project_draft(
        self, llm_model: str, conversation_text: str, _user_id: int, conversation_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Generate a project draft using Claude with streaming.

        Args:
            llm_model: Claude model to use
            messages: List of conversation messages
            user_id: the user id
            conversation_id: the conversation id

        Yields:
            Chunks of generated project draft content

        Raises:
            Exception: If Claude API call fails
        """
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

        # Claude API format
        api_messages: List[MessageParam] = [
            {
                "role": "user",
                "content": f"Please analyze this conversation and create a project proposal:\n\n{conversation_text}",
            }
        ]

        logger.info("Starting project draft generation with Claude")
        logger.debug(f"Model: {llm_model}")
        logger.debug(f"System prompt length: {len(system_prompt)}")
        logger.debug(f"Conversation length: {len(conversation_text)}")

        # Use streaming with Claude
        async with self.client.messages.stream(
            model=llm_model,
            max_tokens=settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS,
            system=system_prompt,
            messages=api_messages,
        ) as stream:
            async for chunk in stream:
                if chunk.type == "content_block_delta":
                    if chunk.delta.type == "text_delta":
                        yield chunk.delta.text

    async def chat_with_project_draft_stream(
        self,
        llm_model: LLMModel,
        conversation_id: int,
        project_draft_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List,
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
        """
        Stream chat responses using Claude with full tool calling support.

        Args:
            llm_model: Claude model to use
            conversation_id: ID of the conversation
            project_draft_id: ID of the project draft
            user_message: User's message
            chat_history: Previous chat messages
            attached_files: List of FileAttachmentData objects
            user_id: ID of the user

        Yields:
            Stream events for the chat response
        """

        project_draft_updated = False
        full_assistant_response = ""
        just_executed_tools = False  # Track if we just finished executing tools

        # Build messages in Claude format
        db = get_database()
        system_prompt, claude_messages = await self._build_claude_messages(
            db=db,
            conversation_id=conversation_id,
            user_message=user_message,
            chat_history=chat_history,
            attached_files=attached_files or [],
        )
        claude_tools = self._get_claude_tools()

        try:
            yield StreamStatusEvent("status", "analyzing_request")

            # Single streaming loop - continue until no more tool calls
            while True:
                logger.info(f"Making Claude streaming call with {len(claude_messages)} messages")
                logger.debug(f"Model: {llm_model.id}, tools: {len(claude_tools)}, stream: True")

                # Stream response from Claude with tools
                collected_content = ""
                tool_calls = []
                current_tool_calls: Dict[int, Dict[str, str]] = {}  # Track tool calls being built
                first_content_chunk = (
                    True  # Track if this is the first content chunk in this iteration
                )

                async with self.client.messages.stream(
                    model=llm_model.id,
                    max_tokens=settings.PROJECT_DRAFT_MAX_COMPLETION_TOKENS,
                    system=system_prompt,
                    messages=claude_messages,
                    tools=claude_tools,  # type: ignore
                ) as stream:
                    async for chunk in stream:
                        if chunk.type == "content_block_delta":
                            if chunk.delta.type == "text_delta":
                                content = chunk.delta.text

                                # Add line break before first content chunk if we just executed tools
                                if just_executed_tools and first_content_chunk:
                                    content = "\n\n" + content
                                    just_executed_tools = False  # Reset the flag

                                first_content_chunk = False
                                collected_content += content
                                full_assistant_response += content
                                yield StreamContentEvent("content", content)
                            elif chunk.delta.type == "input_json_delta":
                                # Tool call input being streamed
                                block_index = chunk.index
                                if block_index in current_tool_calls:
                                    current_tool_calls[block_index][
                                        "partial_input"
                                    ] += chunk.delta.partial_json
                        elif chunk.type == "content_block_start":
                            if chunk.content_block.type == "tool_use":
                                # Start tracking this tool call
                                current_tool_calls[chunk.index] = {
                                    "id": chunk.content_block.id,
                                    "name": chunk.content_block.name,
                                    "partial_input": "",
                                }
                        elif chunk.type == "content_block_stop":
                            # Complete tool call
                            block_index = chunk.index
                            if block_index in current_tool_calls:
                                tool_data = current_tool_calls[block_index]
                                try:
                                    # Parse the complete JSON input
                                    parsed_input = (
                                        json.loads(tool_data["partial_input"])
                                        if tool_data["partial_input"]
                                        else {}
                                    )

                                    # Create a tool call object
                                    tool_calls.append(
                                        ClaudeToolCall(
                                            tool_data["id"], tool_data["name"], parsed_input
                                        )
                                    )
                                except json.JSONDecodeError as e:
                                    logger.error(
                                        f"Failed to parse tool input JSON: {tool_data['partial_input']}, error: {e}"
                                    )
                                    # Create tool call with empty input to trigger validation error
                                    tool_calls.append(
                                        ClaudeToolCall(tool_data["id"], tool_data["name"], {})
                                    )

                                del current_tool_calls[block_index]

                logger.debug(f"Collected content length: {len(collected_content)}")
                logger.debug(f"Claude tool calls: {len(tool_calls)}")

                # Add assistant response to message history
                if collected_content or tool_calls:
                    # Build assistant message content for Claude
                    assistant_content = []

                    # Add text content if any
                    if collected_content:
                        assistant_content.append({"type": "text", "text": collected_content})

                    # Add tool use blocks if any
                    if tool_calls:
                        for tool_call in tool_calls:
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": tool_call.id,
                                    "name": tool_call.name,
                                    "input": tool_call.input,  # type: ignore
                                }
                            )

                    claude_messages.append({"role": "assistant", "content": assistant_content})  # type: ignore

                # Process tool calls if any
                if tool_calls:
                    # Collect all tool results in a single user message
                    tool_results = []
                    conversation_locked = False

                    async for tool_item in self._process_claude_tool_calls(
                        db=db,
                        tool_calls=tool_calls,
                        conversation_id=conversation_id,
                        project_draft_id=project_draft_id,
                        user_id=user_id,
                    ):
                        if isinstance(tool_item, ToolCallResult):
                            # This is the final result with project update status
                            if tool_item.project_updated:
                                project_draft_updated = True
                            # tool_results are collected in _process_claude_tool_calls
                            tool_results = tool_item.tool_results
                        elif isinstance(tool_item, StreamConversationLockedEvent):
                            # Forward conversation locked event and stop processing
                            yield tool_item
                            conversation_locked = True
                        else:
                            # Forward status and project update events
                            yield tool_item

                    # Add all tool results as a single user message
                    if tool_results:
                        claude_messages.append({"role": "user", "content": tool_results})

                    # If conversation was locked, end the stream
                    if conversation_locked:
                        yield StreamDoneEvent(
                            "done",
                            StreamDoneData(
                                project_updated=project_draft_updated,
                                assistant_response=full_assistant_response,
                            ),
                        )
                        return

                    # Clear status message after tool execution
                    yield StreamStatusEvent("status", "generating_response")

                    # Set flag to add line break before next content
                    just_executed_tools = True

                    # Continue the loop to make another call with tool results
                    continue
                else:
                    logger.debug(
                        f"No tool calls found, finishing with content: '{collected_content}'"
                    )
                    # No tool calls, we're done
                    break

            logger.info(f"Claude chat completed for conversation {conversation_id}")

            # Yield completion event
            yield StreamDoneEvent(
                "done",
                StreamDoneData(
                    project_updated=project_draft_updated,
                    assistant_response=full_assistant_response,
                ),
            )

        except Exception as e:
            logger.exception("Claude chat stream error")
            yield StreamErrorEvent("error", f"Chat error: {str(e)}")

    async def _build_claude_messages(
        self,
        db: DatabaseManager,
        conversation_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
    ) -> tuple[str, List[MessageParam]]:
        """
        Build messages in Claude format for chat completion.

        Args:
            db: Database manager instance
            conversation_id: ID of the conversation to get original context and project draft
            user_message: Current user message
            chat_history: Previous chat messages
            attached_files: list of FileAttachmentData objects

        Returns:
            Tuple of (system_prompt, claude_messages)
        """
        system_prompt = get_chat_system_prompt(db, conversation_id)
        claude_messages: List[MessageParam] = []

        summary, recent_chat_messages = await self.summarizer_service.get_chat_summary(
            conversation_id=conversation_id,
            chat_history=chat_history,
        )
        if summary:
            claude_messages.append({"role": "user", "content": f"Conversation so far: {summary}"})
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
                claude_messages.append({"role": "user", "content": user_chat_msg_content})
            elif chat_msg.role == "assistant":
                claude_messages.append({"role": "assistant", "content": chat_msg.content})
            elif chat_msg.role == "tool":
                # Convert tool messages to Claude format
                # TODO: ChatMessageData doesn't store tool_call_id - this is a database schema limitation
                # Tool messages from chat history will have empty tool_use_id, which may cause Claude API errors
                tool_content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": "",  # ChatMessageData doesn't have tool_call_id field
                        "content": chat_msg.content,
                    }
                ]
                claude_messages.append({"role": "user", "content": tool_content})  # type: ignore

        # Add current user message with proper handling for images, PDFs, and text files
        image_attachments = [f for f in attached_files if f.file_type.startswith("image/")]
        pdf_attachments = [f for f in attached_files if f.file_type == "application/pdf"]
        text_attachments = [f for f in attached_files if f.file_type == "text/plain"]

        user_text = user_message
        if text_attachments:
            user_text += self._format_text_content_for_claude(text_attachments)

        if not image_attachments and not pdf_attachments:
            claude_messages.append({"role": "user", "content": user_text})
        else:
            # We have pdf or image attachments
            s3_service = get_s3_service()
            # Claude expects content as an array with text, image, and document blocks
            content: List[Dict[str, Any]] = [{"type": "text", "text": user_text}]

            # Handle PDF attachments using document blocks
            for pdf_attachment in pdf_attachments:
                try:
                    pdf_content = s3_service.download_file_content(pdf_attachment.s3_key)
                    pdf_data = base64.b64encode(pdf_content).decode("utf-8")
                    content.append(
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": pdf_attachment.file_type,
                                "data": pdf_data,
                            },
                        }
                    )

                except Exception:
                    logger.exception(f"Failed to load PDF {pdf_attachment.filename}")
                    # Fall back to text description
                    content[0][
                        "text"
                    ] += f"\n\n[PDF Document: {pdf_attachment.filename} - failed to load]"

            # Handle image attachments using image blocks
            for image_attachment in image_attachments:
                try:
                    image_content = s3_service.download_file_content(image_attachment.s3_key)
                    image_data = base64.b64encode(image_content).decode("utf-8")
                    content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_attachment.file_type,
                                "data": image_data,
                            },
                        }
                    )
                except Exception:
                    logger.exception(f"Failed to load image {image_attachment.filename}")
                    # Fall back to text description
                    content[0][
                        "text"
                    ] += f"\n\n[Image: {image_attachment.filename} - failed to load]"

            claude_messages.append({"role": "user", "content": content})  # type: ignore[typeddict-item]
        return system_prompt, claude_messages

    def _format_text_content_for_claude(self, text_files: List[FileAttachmentData]) -> str:
        """
        Extract text content from text files for Claude context.

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

    def _get_claude_tools(self) -> List[dict]:
        """
        Get tools formatted for Claude API.

        Returns:
            List of tool definitions in Claude format
        """
        return [
            {
                "name": "update_project_draft",
                "description": "Update the project draft with improved title and description. This is the primary deliverable - use when concrete improvements are ready or when the user requests updates. Use markdown formatting for bullet points, lists, and other formatting.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "The updated project title"},
                        "description": {
                            "type": "string",
                            "description": "The updated project description. Use markdown formatting for bullet points, lists, and other formatting.",
                        },
                    },
                    "required": ["title", "description"],
                },
            },
            {
                "name": "create_linear_project",
                "description": "Create a Linear project using the current project draft. IMPORTANT: Only use this tool after explicitly asking the user for confirmation, as this action cannot be undone and will lock the conversation.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    async def _process_claude_tool_calls(
        self,
        db: DatabaseManager,
        tool_calls: List,
        conversation_id: int,
        project_draft_id: int,
        user_id: int,
    ) -> AsyncGenerator[
        Union[
            StreamStatusEvent,
            StreamProjectUpdateEvent,
            StreamConversationLockedEvent,
            ToolCallResult,
        ],
        None,
    ]:
        """
        Process tool calls in Claude format.

        Args:
            db: Database manager instance
            tool_calls: List of Claude tool calls to process
            conversation_id: ID of the conversation
            project_draft_id: ID of the project draft

        Yields:
            Status and project update events, then ToolCallResult with collected tool results
        """
        project_draft_updated = False
        tool_results = []

        yield StreamStatusEvent("status", "executing_tools")

        for tool_call in tool_calls:
            function_name = tool_call.name
            function_args = tool_call.input

            logger.info(f"Executing tool: {function_name} with args: {function_args}")

            try:
                if function_name == "update_project_draft":
                    yield StreamStatusEvent("status", "updating_project_draft")

                    # Validate required arguments
                    if "title" not in function_args or "description" not in function_args:
                        error_message = f"❌ Tool validation failed: update_project_draft requires 'title' and 'description' arguments. Received: {list(function_args.keys())}"
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": error_message,
                            }
                        )
                        logger.error(
                            f"Missing required arguments for update_project_draft: {function_args}"
                        )
                        continue

                    title = function_args["title"]
                    description = function_args["description"]

                    # Validate arguments are not empty
                    if not title or not description:
                        error_message = f"❌ Tool validation failed: update_project_draft requires non-empty 'title' and 'description'. Title: '{title}', Description length: {len(description)}"
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": error_message,
                            }
                        )
                        logger.error(
                            f"Empty arguments for update_project_draft: title='{title}', description length={len(description)}"
                        )
                        continue

                    # Validate title length before proceeding
                    if len(title) > settings.MAX_PROJECT_TITLE_LENGTH:
                        error_message = f"❌ Project title validation failed: Title '{title}' is {len(title)} characters long, but maximum allowed is {settings.MAX_PROJECT_TITLE_LENGTH} characters for Linear compatibility. Please create a shorter, more concise title."
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": error_message,
                            }
                        )
                        logger.warning(
                            f"Title validation failed - length: {len(title)}, limit: {settings.MAX_PROJECT_TITLE_LENGTH}"
                        )
                        continue

                    try:
                        db.create_project_draft_version(
                            project_draft_id=project_draft_id,
                            title=title,
                            description=description,
                            is_manual_edit=False,
                            created_by_user_id=user_id,
                        )
                        project_draft_updated = True

                        updated_project_draft = db.get_project_draft_by_conversation_id(
                            conversation_id
                        )
                        if updated_project_draft:
                            yield StreamProjectUpdateEvent("project_updated", "true")

                        success_message = (
                            f"✅ Project draft updated successfully: {title} ({len(title)} chars)"
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": success_message,
                            }
                        )
                    except Exception as e:
                        error_message = f"❌ Failed to update project draft: {str(e)}"
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": error_message,
                            }
                        )

                elif function_name == "create_linear_project":
                    yield StreamStatusEvent("status", "creating_linear_project")
                    try:
                        # Get current project draft
                        current_draft = db.get_project_draft_by_conversation_id(conversation_id)
                        if not current_draft:
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_call.id,
                                    "content": "❌ No project draft found to create Linear project from",
                                }
                            )
                            continue

                        linear_service = LinearService()

                        # Create Linear project
                        linear_project = await linear_service.create_project(
                            title=current_draft.title,
                            description=current_draft.description,
                        )

                        # Save project to database and lock conversation
                        db.create_project(
                            conversation_id=conversation_id,
                            linear_project_id=linear_project.id,
                            title=linear_project.name,
                            description=linear_project.content,
                            linear_url=linear_project.url,
                            created_by_user_id=user_id,
                        )

                        # Notify frontend that conversation is locked
                        yield StreamConversationLockedEvent(
                            "conversation_locked", linear_project.url
                        )

                        success_message = f"✅ Linear project created successfully! The conversation is now locked. View your project: {linear_project.url}"
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": success_message,
                            }
                        )

                    except Exception as e:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": f"❌ Failed to create Linear project: {str(e)}",
                            }
                        )

                else:
                    logger.warning(f"Unknown tool function: {function_name}")
                    content = f"Unknown tool function: {function_name}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": content,
                        }
                    )

            except Exception as e:
                logger.error(f"Error executing tool {function_name}: {e}")
                content = f"Error executing tool {function_name}: {e}"
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": content,
                    }
                )

        logger.info(f"Finished processing all {len(tool_calls)} tool calls")
        yield ToolCallResult(project_updated=project_draft_updated, tool_results=tool_results)
