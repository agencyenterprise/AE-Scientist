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

from app.middleware.auth import get_current_user
from app.models import ChatMessageData, ChatRequest
from app.services import (
    AnthropicService,
    GrokService,
    OpenAIService,
    SummarizerService,
    get_database,
)
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.base_llm_service import FileAttachmentData
from app.services.chat_models import StreamDoneEvent
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS

router = APIRouter(prefix="/conversations")

# Initialize services
summarizer_service = SummarizerService()
openai_service = OpenAIService(summarizer_service)
anthropic_service = AnthropicService(summarizer_service)
grok_service = GrokService(summarizer_service)
logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


@router.post("/{conversation_id}/idea/chat/stream", response_model=None)
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

    try:
        # Validate conversation exists
        existing_conversation = db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            response.status_code = 404
            return ErrorResponse(error="Conversation not found", detail="Conversation not found")

        user = get_current_user(request)
        # Get idea
        idea_data = db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            idea_id = db.create_idea(
                conversation_id=conversation_id,
                title="Failed to Generate Idea",
                short_hypothesis="Idea generation failed.",
                related_work="N/A",
                abstract="Idea generation failed.\n\nPlease try regenerating the idea manually.",
                experiments=["N/A"],
                expected_outcome="N/A",
                risk_factors_and_limitations=["N/A"],
                created_by_user_id=user.id,
            )
        else:
            idea_id = idea_data.idea_id

        # Get chat history
        chat_history = db.get_chat_messages(idea_id)

        # Store user message in database
        user_msg_id = db.create_chat_message(
            idea_id=idea_id,
            role="user",
            content=request_data.message,
            sent_by_user_id=user.id,
        )
        logger.info(f"Stored user message with ID: {user_msg_id}")

        # Process file attachments if provided
        attached_files = []
        if request_data.attachment_ids:
            logger.info(f"Processing {len(request_data.attachment_ids)} file attachments")

            # Get file attachments from database
            file_attachments = db.get_file_attachments_by_ids(request_data.attachment_ids)

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
                success = db.update_file_attachment_message_id(
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
                refreshed = db.get_file_attachments_by_ids(request_data.attachment_ids)
                for fa in refreshed:
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

        # Create async streaming response
        async def generate_stream() -> AsyncGenerator[str, None]:
            try:
                logger.info(f"Starting stream for conversation {conversation_id}")

                # Route to appropriate service based on provider
                if llm_provider == "openai":
                    async for event_data in openai_service.chat_with_idea_stream(
                        llm_model=next(m for m in OPENAI_MODELS if m.id == llm_model),
                        conversation_id=conversation_id,
                        idea_id=idea_id,
                        user_message=request_data.message,
                        chat_history=[
                            ChatMessageData(
                                id=msg.id,
                                idea_id=idea_id,
                                role=msg.role,
                                content=msg.content,
                                sequence_number=msg.sequence_number,
                                created_at=msg.created_at,
                            )
                            for msg in chat_history
                        ],
                        attached_files=[
                            FileAttachmentData(
                                id=file.id,
                                filename=file.filename,
                                file_type=file.file_type,
                                file_size=file.file_size,
                                created_at=file.created_at,
                                chat_message_id=file.chat_message_id,
                                conversation_id=conversation_id,
                                s3_key=file.s3_key,
                            )
                            for file in attached_files
                        ],
                        user_id=user.id,
                    ):
                        logger.debug(f"OpenAI SSE Event: {event_data}")
                        if isinstance(event_data, StreamDoneEvent):
                            data = event_data._asdict()
                            logger.debug(f"Done event: {data}")
                            # Treat empty assistant response as an error and do not persist
                            if not (
                                event_data.data.assistant_response
                                and event_data.data.assistant_response.strip()
                            ):
                                error_json = (
                                    json.dumps({"type": "error", "data": "Empty model output"})
                                    + "\n"
                                )
                                logger.warning(
                                    f"Empty assistant response for conversation {conversation_id}; emitting error instead of persisting"
                                )
                                yield error_json
                                return
                            else:
                                db.create_chat_message(
                                    idea_id=idea_id,
                                    role="assistant",
                                    content=event_data.data.assistant_response,
                                    sent_by_user_id=user.id,
                                )

                        json_data = json.dumps(event_data._asdict()) + "\n"
                        logger.debug(f"Yielding: {repr(json_data[:100])}")
                        yield json_data
                elif llm_provider == "grok":
                    async for event_data in grok_service.chat_with_idea_stream(
                        llm_model=next(m for m in GROK_MODELS if m.id == llm_model),
                        conversation_id=conversation_id,
                        idea_id=idea_id,
                        user_message=request_data.message,
                        chat_history=[
                            ChatMessageData(
                                id=msg.id,
                                idea_id=idea_id,
                                role=msg.role,
                                content=msg.content,
                                sequence_number=msg.sequence_number,
                                created_at=msg.created_at,
                            )
                            for msg in chat_history
                        ],
                        attached_files=[
                            FileAttachmentData(
                                id=file.id,
                                filename=file.filename,
                                file_type=file.file_type,
                                file_size=file.file_size,
                                created_at=file.created_at,
                                chat_message_id=user_msg_id,
                                conversation_id=conversation_id,
                                s3_key=file.s3_key,
                            )
                            for file in attached_files
                        ],
                        user_id=user.id,
                    ):
                        logger.debug(f"Grok SSE Event: {event_data}")
                        if isinstance(event_data, StreamDoneEvent):
                            data = event_data._asdict()
                            logger.debug(f"Done event: {data}")
                            if not (
                                event_data.data.assistant_response
                                and event_data.data.assistant_response.strip()
                            ):
                                error_json = (
                                    json.dumps({"type": "error", "data": "Empty model output"})
                                    + "\n"
                                )
                                logger.warning(
                                    f"Empty assistant response for conversation {conversation_id}; emitting error instead of persisting"
                                )
                                yield error_json
                                return
                            else:
                                db.create_chat_message(
                                    idea_id=idea_id,
                                    role="assistant",
                                    content=event_data.data.assistant_response,
                                    sent_by_user_id=user.id,
                                )

                        json_data = json.dumps(event_data._asdict()) + "\n"
                        logger.debug(f"Yielding: {repr(json_data[:100])}")
                        yield json_data
                elif llm_provider == "anthropic":
                    async for event_data in anthropic_service.chat_with_idea_stream(
                        llm_model=next(m for m in ANTHROPIC_MODELS if m.id == llm_model),
                        conversation_id=conversation_id,
                        idea_id=idea_id,
                        user_message=request_data.message,
                        chat_history=[
                            ChatMessageData(
                                id=msg.id,
                                idea_id=idea_id,
                                role=msg.role,
                                content=msg.content,
                                sequence_number=msg.sequence_number,
                                created_at=msg.created_at,
                            )
                            for msg in chat_history
                        ],
                        attached_files=[
                            FileAttachmentData(
                                id=file.id,
                                filename=file.filename,
                                file_type=file.file_type,
                                file_size=file.file_size,
                                created_at=file.created_at,
                                chat_message_id=user_msg_id,
                                conversation_id=conversation_id,
                                s3_key=file.s3_key,
                            )
                            for file in attached_files
                        ],
                        user_id=user.id,
                    ):
                        if isinstance(event_data, StreamDoneEvent):
                            data = event_data._asdict()
                            logger.debug(f"Done event: {data}")
                            if not (
                                event_data.data.assistant_response
                                and event_data.data.assistant_response.strip()
                            ):
                                error_json = (
                                    json.dumps({"type": "error", "data": "Empty model output"})
                                    + "\n"
                                )
                                logger.warning(
                                    f"Empty assistant response for conversation {conversation_id}; emitting error instead of persisting"
                                )
                                yield error_json
                                return
                            else:
                                db.create_chat_message(
                                    idea_id=idea_id,
                                    role="assistant",
                                    content=event_data.data.assistant_response,
                                    sent_by_user_id=user.id,
                                )

                        json_data = json.dumps(event_data._asdict()) + "\n"
                        logger.debug(f"Yielding: {repr(json_data[:100])}")
                        yield json_data
                else:
                    error_msg = f"Unsupported LLM provider: {llm_provider}"
                    logger.error(error_msg)
                    yield json.dumps({"type": "error", "data": error_msg}) + "\n"
                    return

                logger.info(f"Stream completed for conversation {conversation_id}")
            except Exception as e:
                logger.exception(f"Error in stream_chat_response: {e}")
                yield json.dumps({"type": "error", "data": f"Stream error: {str(e)}"}) + "\n"

            finally:
                logger.info(f"Adding messages to chat summary for conversation {conversation_id}")
                await summarizer_service.add_messages_to_chat_summary(
                    idea_id=idea_id,
                    conversation_id=conversation_id,
                )

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
