"""
Streaming Chat API endpoints.

This module contains FastAPI routes for streaming chat functionality with SSE.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, List, Optional, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.llm_providers import LLM_PROVIDER_REGISTRY
from app.config import settings
from app.middleware.auth import get_current_user
from app.models import ChatMessageData, ChatRequest
from app.models.sse import ChatStreamEvent
from app.services import SummarizerService, get_database
from app.services.base_llm_service import FileAttachmentData
from app.services.billing_guard import enforce_minimum_balance
from app.services.chat_models import StreamDoneEvent
from app.services.database import DatabaseManager

router = APIRouter(prefix="/conversations")

# Initialize services

logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


def create_error_stream_response(error_message: str, status_code: int = 500) -> StreamingResponse:
    """Create a StreamingResponse that sends a single error event in SSE format."""

    async def error_stream() -> AsyncGenerator[str, None]:
        yield json.dumps({"type": "error", "data": error_message}) + "\n"

    return StreamingResponse(
        error_stream(),
        status_code=status_code,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


async def _run_chat_generation_to_queue(
    queue: "asyncio.Queue[Optional[str]]",
    db: DatabaseManager,
    conversation_id: int,
    idea_id: int,
    assistant_msg_id: int,
    llm_provider: str,
    llm_model: str,
    actual_user_message: str,
    chat_history_payload: List[ChatMessageData],
    llm_attachment_payload: List[FileAttachmentData],
    user_id: int,
    summarizer_service: SummarizerService,
) -> None:
    """Background task to generate chat response and write chunks to queue.

    Runs independently of client connection. Writes chunks to queue for
    streaming to client. When done, writes None to signal completion.
    The message is saved when generation completes.
    """
    stream_completed_successfully = False

    try:
        logger.info(f"Starting background chat generation for conversation {conversation_id}")

        provider_config = LLM_PROVIDER_REGISTRY.get(llm_provider)
        if not provider_config:
            error_msg = f"Unsupported LLM provider: {llm_provider}"
            logger.error(error_msg)
            await db.delete_chat_message(assistant_msg_id)
            await queue.put(json.dumps({"type": "error", "data": error_msg}) + "\n")
            return

        target_model = provider_config.models_by_id.get(llm_model)
        if not target_model:
            error_msg = f"Unsupported model '{llm_model}' for provider '{llm_provider}'"
            logger.error(error_msg)
            await db.delete_chat_message(assistant_msg_id)
            await queue.put(json.dumps({"type": "error", "data": error_msg}) + "\n")
            return

        async for event_data in provider_config.service.chat_with_idea_stream(
            llm_model=target_model,
            conversation_id=conversation_id,
            idea_id=idea_id,
            user_message=actual_user_message,
            chat_history=chat_history_payload,
            attached_files=llm_attachment_payload,
            user_id=user_id,
        ):
            logger.debug(f"LLM SSE Event ({llm_provider}): {event_data}")

            if isinstance(event_data, StreamDoneEvent):
                data = event_data._asdict()
                logger.debug(f"Done event: {data}")
                final_content = event_data.data.assistant_response

                # Treat empty assistant response as an error and do not persist
                if not (final_content and final_content.strip()):
                    error_json = json.dumps({"type": "error", "data": "Empty model output"}) + "\n"
                    logger.warning(
                        f"Empty assistant response for conversation {conversation_id}; "
                        "emitting error instead of persisting"
                    )
                    try:
                        await db.delete_chat_message(assistant_msg_id)
                        logger.debug(
                            f"Deleted placeholder assistant message {assistant_msg_id} "
                            "due to empty response"
                        )
                    except Exception as delete_error:
                        logger.error(
                            f"Failed to delete placeholder message after empty response: "
                            f"{delete_error}"
                        )
                    await queue.put(error_json)
                    return

                # Update the placeholder assistant message with the final content
                await db.update_chat_message_content(
                    message_id=assistant_msg_id,
                    content=final_content,
                )
                stream_completed_successfully = True
                logger.debug(
                    f"Updated assistant message {assistant_msg_id} with final content "
                    f"for conversation {conversation_id}"
                )

            # Write event to queue for client
            json_data = json.dumps(event_data._asdict()) + "\n"
            await queue.put(json_data)

        logger.info(f"Background chat generation completed for conversation {conversation_id}")

    except Exception as exc:
        logger.exception(
            f"Background chat generation failed for conversation {conversation_id}: {exc}"
        )
        # Delete placeholder on error if not completed
        if not stream_completed_successfully:
            try:
                await db.delete_chat_message(assistant_msg_id)
                logger.debug(
                    f"Deleted placeholder assistant message {assistant_msg_id} after error"
                )
            except Exception as delete_error:
                logger.error(f"Failed to delete placeholder message: {delete_error}")
        # Write error to queue so client sees it (if still connected)
        try:
            await queue.put(
                json.dumps({"type": "error", "data": f"Stream error: {str(exc)}"}) + "\n"
            )
        except Exception:
            pass

    finally:
        # Add messages to chat summary
        logger.debug(f"Adding messages to chat summary for conversation {conversation_id}")
        try:
            await summarizer_service.add_messages_to_chat_summary(
                conversation_id=conversation_id,
                user_id=user_id,
                idea_id=idea_id,
            )
        except Exception as summarizer_error:
            logger.exception(
                f"Error in add_messages_to_chat_summary for conversation {conversation_id}: "
                f"{summarizer_error}"
            )

        # Signal completion to the streaming consumer
        try:
            await queue.put(None)
        except Exception:
            pass


@router.post(
    "/{conversation_id}/idea/chat/stream",
    response_model=ChatStreamEvent,
    responses={
        200: {
            "description": "Server-sent events emitted while streaming chat responses",
            "content": {
                "text/event-stream": {"schema": {"$ref": "#/components/schemas/ChatStreamEvent"}}
            },
        },
        402: {
            "description": "Insufficient balance - returned as SSE error event",
            "content": {
                "text/event-stream": {"schema": {"$ref": "#/components/schemas/ChatStreamEvent"}}
            },
        },
    },
)
async def stream_chat_with_idea(
    conversation_id: int, request_data: ChatRequest, request: Request
) -> StreamingResponse:
    """
    Stream chat messages with real-time updates via Server-Sent Events.
    """
    if conversation_id <= 0:
        return create_error_stream_response("Conversation ID must be positive", 400)

    db = get_database()

    summarizer_service = SummarizerService.for_model(
        request_data.llm_provider, request_data.llm_model
    )

    try:
        # Validate conversation exists
        existing_conversation = await db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            return create_error_stream_response("Conversation not found", 404)

        user = get_current_user(request)
        # Get idea
        idea_data = await db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            failure_title = "Failed to Generate Idea"
            failure_markdown = """## Project Summary
Idea generation failed.

## Related Work
N/A

## Abstract
Idea generation failed.

Please try regenerating the idea manually.

## Experiments
- N/A

## Expected Outcome
N/A

## Risk Factors and Limitations
- N/A
"""
            idea_id = await db.create_idea(
                conversation_id=conversation_id,
                title=failure_title,
                idea_markdown=failure_markdown,
                created_by_user_id=user.id,
            )
        else:
            idea_id = idea_data.idea_id

        # Pre-check minimum balance before allowing chat message
        await enforce_minimum_balance(
            user_id=user.id,
            required_cents=settings.min_balance_cents_for_chat_message,
            action="chat_message",
        )

        # Get chat history
        chat_history = await db.get_chat_messages(idea_id)

        # Store user message in database (unless skipping for auto-trigger)
        if request_data.skip_user_message_creation:
            # For auto-trigger of existing messages, use the last user message from history
            if not chat_history or chat_history[-1].role != "user":
                return create_error_stream_response("No user message to respond to", 400)
            user_msg_id = chat_history[-1].id
            # Extract the actual message content from the last user message for LLM
            actual_user_message = chat_history[-1].content
            logger.debug(
                f"Auto-triggering response for existing user message ID: {user_msg_id} "
                f"with content: {actual_user_message[:50]}..."
            )
        else:
            user_msg_id = await db.create_chat_message(
                idea_id=idea_id,
                role="user",
                content=request_data.message,
                sent_by_user_id=user.id,
            )
            actual_user_message = request_data.message
            logger.debug(f"Stored user message with ID: {user_msg_id}")

        # Process file attachments if provided
        attached_files = []
        if request_data.attachment_ids:
            logger.debug(f"Processing {len(request_data.attachment_ids)} file attachments")

            # Get file attachments from database
            file_attachments = await db.get_file_attachments_by_ids(request_data.attachment_ids)

            # Validate that all requested attachments were found
            found_ids = {fa.id for fa in file_attachments}
            missing_ids = set(request_data.attachment_ids) - found_ids
            if missing_ids:
                return create_error_stream_response(
                    f"File attachments not found: {list(missing_ids)}", 404
                )

            # Link file attachments to the user message
            for file_attachment in file_attachments:
                # Update existing file attachment record to link to this message (first-send only)
                success = await db.update_file_attachment_message_id(
                    attachment_id=file_attachment.id,
                    chat_message_id=user_msg_id,
                )
                if success:
                    logger.debug(f"Linked file {file_attachment.filename} to message {user_msg_id}")
                else:
                    logger.warning(
                        f"Failed to link file attachment {file_attachment.id} to message {user_msg_id}"
                    )

            attached_files = file_attachments

            # After linking, upload/link documents to summarizer using extracted_text from DB
            try:
                # Re-read attachments to include latest extracted_text/summary_text
                refreshed = await db.get_file_attachments_by_ids(request_data.attachment_ids)
                attached_files = refreshed
                for fa in attached_files:
                    content = fa.extracted_text or fa.summary_text or ""
                    if not content.strip():
                        continue
                    doc_type = (
                        "pdf"
                        if fa.file_type == "application/pdf"
                        else ("image" if fa.file_type.startswith("image/") else "text")
                    )
                    logger.debug(
                        f"Syncing attachment {fa.id}, name: {fa.filename}, type: {doc_type}, to summarizer: {fa.extracted_text} {fa.summary_text}"
                    )
                    await summarizer_service.add_document_to_chat_summary(
                        conversation_id=conversation_id,
                        user_id=user.id,
                        content=content,
                        description=fa.filename,
                        document_type=doc_type,
                    )
            except Exception as e:
                logger.exception(
                    f"Failed to sync linked attachments to summarizer for conversation {conversation_id}: {e}"
                )

        llm_model = request_data.llm_model
        llm_provider = request_data.llm_provider

        chat_history_payload = [
            ChatMessageData(
                id=msg.id,
                idea_id=idea_id,
                role=msg.role,
                content=msg.content,
                sequence_number=msg.sequence_number,
                created_at=msg.created_at,
            )
            for msg in chat_history
        ]

        llm_attachment_payload = [
            FileAttachmentData(
                id=file.id,
                filename=file.filename,
                file_type=file.file_type,
                file_size=file.file_size,
                created_at=file.created_at,
                chat_message_id=file.chat_message_id or user_msg_id,
                conversation_id=conversation_id,
                s3_key=file.s3_key,
            )
            for file in attached_files
        ]

        # Create async streaming response using queue-based approach
        # This allows the LLM generation to continue even if client disconnects
        async def generate_stream() -> AsyncGenerator[str, None]:
            # Create placeholder assistant message immediately to prevent duplicate executions
            # on page refresh during streaming
            assistant_msg_id = await db.create_chat_message(
                idea_id=idea_id,
                role="assistant",
                content="",  # Empty placeholder, will be updated when done
                sent_by_user_id=user.id,
            )
            logger.debug(
                f"Created placeholder assistant message {assistant_msg_id} for conversation {conversation_id}"
            )

            # Create queue for communication between background task and this stream
            queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

            # Start background task for LLM generation
            # This runs independently - if client disconnects, task continues and saves message
            background_task = asyncio.create_task(
                _run_chat_generation_to_queue(
                    queue=queue,
                    db=db,
                    conversation_id=conversation_id,
                    idea_id=idea_id,
                    assistant_msg_id=assistant_msg_id,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    actual_user_message=actual_user_message,
                    chat_history_payload=chat_history_payload,
                    llm_attachment_payload=llm_attachment_payload,
                    user_id=user.id,
                    summarizer_service=summarizer_service,
                )
            )
            background_task.add_done_callback(
                lambda t: (
                    logger.error(f"Chat background task exception: {t.exception()}")
                    if t.exception()
                    else None
                )
            )

            # Stream chunks from queue to client
            # If client disconnects, GeneratorExit is raised and we exit
            # But the background task continues running and will save the message
            while True:
                queue_chunk = await queue.get()
                if queue_chunk is None:
                    # Background task finished
                    break
                yield queue_chunk

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except HTTPException as e:
        # Handle HTTPException (including 402 insufficient balance) by returning as SSE error
        logger.error(f"HTTPException in stream_chat_with_idea: {e.status_code}: {e.detail}")

        # Format the error message for 402 responses
        # Note: e.detail can be a dict at runtime even though typed as str
        detail_any = cast(Any, e.detail)
        if e.status_code == 402 and isinstance(detail_any, dict):
            if detail_any.get("required_cents") is not None:
                required = detail_any["required_cents"] / 100
                error_msg = f"Insufficient balance. You need ${required:.2f} to continue."
            else:
                error_msg = detail_any.get("message", "Insufficient balance")
        else:
            error_msg = str(e.detail) if e.detail else "Request failed"

        return create_error_stream_response(error_msg, e.status_code)

    except Exception as e:
        logger.exception(f"Error in stream_chat_with_idea: {e}")
        return create_error_stream_response("Stream failed. Please try again.", 500)
