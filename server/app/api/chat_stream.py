"""
Streaming Chat API endpoints.

This module contains FastAPI routes for streaming chat functionality with SSE.
"""

import json
import logging
from typing import AsyncGenerator, Optional, Union

from fastapi import APIRouter, Request, Response
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

router = APIRouter(prefix="/conversations")

# Initialize services

logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


@router.post(
    "/{conversation_id}/idea/chat/stream",
    response_model=ChatStreamEvent,
    responses={
        200: {
            "description": "Server-sent events emitted while streaming chat responses",
            "content": {
                "text/event-stream": {"schema": {"$ref": "#/components/schemas/ChatStreamEvent"}}
            },
        }
    },
)
async def stream_chat_with_idea(
    conversation_id: int, request_data: ChatRequest, request: Request, response: Response
) -> Union[StreamingResponse, ErrorResponse]:
    """
    Stream chat messages with real-time updates via Server-Sent Events.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    summarizer_service = SummarizerService.for_model(
        request_data.llm_provider, request_data.llm_model
    )

    try:
        # Validate conversation exists
        existing_conversation = await db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            response.status_code = 404
            return ErrorResponse(error="Conversation not found", detail="Conversation not found")

        user = get_current_user(request)
        # Get idea
        idea_data = await db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            failure_title = "Failed to Generate Idea"
            failure_markdown = """## Short Hypothesis
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
            required_cents=settings.billing_limits.min_balance_cents_for_chat_message,
            action="chat_message",
        )

        # Get chat history
        chat_history = await db.get_chat_messages(idea_id)

        # Store user message in database (unless skipping for auto-trigger)
        if request_data.skip_user_message_creation:
            # For auto-trigger of existing messages, use the last user message from history
            if not chat_history or chat_history[-1].role != "user":
                response.status_code = 400
                return ErrorResponse(
                    error="No user message to respond to",
                    detail="skip_user_message_creation requires an existing user message",
                )
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
                response.status_code = 404
                return ErrorResponse(
                    error="File attachments not found",
                    detail=f"File attachments not found: {list(missing_ids)}",
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

        # Create async streaming response
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

            try:
                logger.debug(f"Starting stream for conversation {conversation_id}")

                provider_config = LLM_PROVIDER_REGISTRY.get(llm_provider)
                if not provider_config:
                    error_msg = f"Unsupported LLM provider: {llm_provider}"
                    logger.error(error_msg)
                    # Delete placeholder on error
                    try:
                        await db.delete_chat_message(assistant_msg_id)
                    except Exception:
                        pass
                    yield json.dumps({"type": "error", "data": error_msg}) + "\n"
                    return

                target_model = provider_config.models_by_id.get(llm_model)
                if not target_model:
                    error_msg = f"Unsupported model '{llm_model}' for provider '{llm_provider}'"
                    logger.error(error_msg)
                    # Delete placeholder on error
                    try:
                        await db.delete_chat_message(assistant_msg_id)
                    except Exception:
                        pass
                    yield json.dumps({"type": "error", "data": error_msg}) + "\n"
                    return

                async for event_data in provider_config.service.chat_with_idea_stream(
                    llm_model=target_model,
                    conversation_id=conversation_id,
                    idea_id=idea_id,
                    user_message=actual_user_message,
                    chat_history=chat_history_payload,
                    attached_files=llm_attachment_payload,
                    user_id=user.id,
                ):
                    logger.debug(f"LLM SSE Event ({llm_provider}): {event_data}")
                    if isinstance(event_data, StreamDoneEvent):
                        data = event_data._asdict()
                        logger.debug(f"Done event: {data}")
                        # Treat empty assistant response as an error and do not persist
                        if not (
                            event_data.data.assistant_response
                            and event_data.data.assistant_response.strip()
                        ):
                            error_json = (
                                json.dumps({"type": "error", "data": "Empty model output"}) + "\n"
                            )
                            logger.warning(
                                f"Empty assistant response for conversation {conversation_id}; emitting error instead of persisting"
                            )
                            # Delete the placeholder message since response is empty
                            try:
                                await db.delete_chat_message(assistant_msg_id)
                                logger.debug(
                                    f"Deleted placeholder assistant message {assistant_msg_id} due to empty response"
                                )
                            except Exception as delete_error:
                                logger.error(
                                    f"Failed to delete placeholder message after empty response: {delete_error}"
                                )
                            yield error_json
                            return

                        # Update the placeholder assistant message with the final content
                        await db.update_chat_message_content(
                            message_id=assistant_msg_id,
                            content=event_data.data.assistant_response,
                        )
                        logger.debug(
                            f"Updated assistant message {assistant_msg_id} with final content for conversation {conversation_id}"
                        )

                    json_data = json.dumps(event_data._asdict()) + "\n"
                    logger.debug(f"Yielding: {repr(json_data[:100])}")
                    yield json_data

                logger.debug(f"Stream completed for conversation {conversation_id}")
            except Exception as e:
                logger.exception(f"Error in stream_chat_response: {e}")
                # Delete the placeholder message on error
                try:
                    await db.delete_chat_message(assistant_msg_id)
                    logger.debug(
                        f"Deleted placeholder assistant message {assistant_msg_id} after error"
                    )
                except Exception as delete_error:
                    logger.error(f"Failed to delete placeholder message: {delete_error}")
                yield json.dumps({"type": "error", "data": f"Stream error: {str(e)}"}) + "\n"

            finally:
                logger.debug(f"Adding messages to chat summary for conversation {conversation_id}")
                try:
                    await summarizer_service.add_messages_to_chat_summary(
                        conversation_id=conversation_id,
                        user_id=user.id,
                        idea_id=idea_id,
                    )
                except Exception as summarizer_error:
                    logger.exception(
                        f"Error in add_messages_to_chat_summary for conversation {conversation_id}: {summarizer_error}"
                    )
                # Note: LLM costs are now charged atomically in create_llm_token_usage

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except Exception as e:
        logger.exception(f"Error in stream_chat_with_idea: {e}")
        response.status_code = 500
        return ErrorResponse(error="Stream failed", detail=f"Failed to stream chat: {str(e)}")
