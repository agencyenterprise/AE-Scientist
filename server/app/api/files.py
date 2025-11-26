"""
File upload and download API endpoints.

This module handles file attachments for chat messages, including upload to S3,
download via signed URLs, and metadata management.
"""

import asyncio
import logging
from typing import List, Optional, Union

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.models.chat import FileAttachment
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.anthropic_service import AnthropicService
from app.services.base_llm_service import BaseLLMService
from app.services.database import DatabaseManager, get_database
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.grok_service import GrokService
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS
from app.services.openai_service import OpenAIService
from app.services.pdf_service import PDFService
from app.services.s3_service import S3Service
from app.services.summarizer_service import SummarizerService

router = APIRouter(prefix="/conversations")

logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class FileMetadata(BaseModel):
    """File metadata response."""

    id: int = Field(..., description="File attachment ID")
    s3_key: str = Field(..., description="S3 storage key")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    conversation_id: int = Field(..., description="Associated conversation ID")


class FileUploadResponse(BaseModel):
    """File upload response."""

    file: FileMetadata = Field(..., description="Uploaded file metadata")
    message: str = Field(..., description="Success message")


class FileListResponse(BaseModel):
    """File list response."""

    files: List[FileAttachment] = Field(..., description="List of file attachments")
    file_count: int = Field(..., description="Number of files")


summarizer_service = SummarizerService()
anthropic_service = AnthropicService(summarizer_service)
grok_service = GrokService(summarizer_service)
openai_service = OpenAIService(summarizer_service)
pdf_service = PDFService()
s3_service = S3Service()


async def process_attachment_background(
    db: "DatabaseManager",
    attachment_id: int,
    file_type: str,
    file_content: bytes,
    filename: str,
    s3_key: str,
    llm_model: str,
    llm_provider: str,
) -> None:
    try:
        service: BaseLLMService
        if llm_provider == "anthropic":
            service = anthropic_service
        elif llm_provider == "grok":
            service = grok_service
        else:
            service = openai_service

        extracted_text = ""
        if file_type == "application/pdf":
            extracted_text = pdf_service.extract_text_from_pdf(file_content)
        elif file_type.startswith("image/"):
            # Generate a detailed caption using the selected provider's model if it supports images
            image_url = s3_service.generate_download_url(s3_key=s3_key)

            if llm_provider == "openai":
                model_obj = next(m for m in OPENAI_MODELS if m.id == llm_model)
            elif llm_provider == "anthropic":
                model_obj = next(m for m in ANTHROPIC_MODELS if m.id == llm_model)
            elif llm_provider == "grok":
                model_obj = next(m for m in GROK_MODELS if m.id == llm_model)
            else:
                raise ValueError(f"Unknown LLM provider: {llm_provider}")

            try:
                # If the selected model isn't vision, we still attempt; service will fail gracefully if unsupported
                logger.info(
                    f"Summarizing image {filename} with model {llm_model} and provider {llm_provider}"
                )
                detailed = await service.summarize_image(
                    llm_model=model_obj,
                    image_url=image_url,
                )
                extracted_text = detailed or f"Image: {filename}"
                logger.info(f"Summary of image {filename} is {extracted_text}")
            except Exception:
                extracted_text = f"Image: {filename}"
        elif file_type == "text/plain":
            try:
                extracted_text = file_content.decode("utf-8")
            except Exception:
                extracted_text = ""

        # Skip summarization and DB update if nothing was extracted
        if not extracted_text.strip():
            logger.info(
                f"No text extracted for attachment {attachment_id} (type={file_type}); skipping summarization and persistence"
            )
            return

        summary_text = ""
        try:
            logger.info(
                f"Summarizing segment {attachment_id} with model {llm_model} and provider {llm_provider}"
            )
            summary_text = await service.summarize_document(
                llm_model=model_obj,
                content=extracted_text,
            )
        except Exception:
            summary_text = (extracted_text or "")[:1000]

        logger.info(
            f"Storing summary text for attachment {attachment_id}: {summary_text}, {extracted_text}"
        )
        db.update_attachment_texts(
            attachment_id=attachment_id,
            extracted_text=extracted_text,
            summary_text=summary_text,
        )
    except Exception as e:
        logger.exception(f"Attachment background processing failed: {e}")


@router.post("/{conversation_id}/files")
async def upload_file(
    conversation_id: int,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    llm_model: str = Form(...),
    llm_provider: str = Form(...),
) -> Union[FileUploadResponse, ErrorResponse]:
    """
    Upload a file attachment for a conversation.

    Args:
        conversation_id: ID of the conversation
        file: File to upload (multipart/form-data)
        llm_model: LLM model to use for processing
        llm_provider: LLM provider to use for processing

    Returns:
        JSON response with file metadata

    Raises:
        HTTPException: If validation fails or upload fails
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    # Get current authenticated user
    current_user = get_current_user(request)

    db = get_database()

    try:
        # Validate conversation exists
        existing_conversation = db.get_conversation_by_id(conversation_id)
        if not existing_conversation:
            response.status_code = 404
            return ErrorResponse(error="Conversation not found", detail="Conversation not found")

        # Check if conversation is locked
        if db.conversation_is_locked(conversation_id):
            response.status_code = 403
            return ErrorResponse(
                error="Conversation locked", detail="Cannot upload files to a locked conversation"
            )

        # Validate file is provided
        if not file.filename:
            response.status_code = 400
            return ErrorResponse(error="No file provided", detail="No file provided")

        # Read file content
        file_content = await file.read()
        if not file_content:
            response.status_code = 400
            return ErrorResponse(error="Empty file", detail="Empty file provided")

        # Upload file to S3 (this will validate file type and size)
        s3_key = s3_service.upload_file(
            file_content=file_content,
            conversation_id=conversation_id,
            filename=file.filename,
            file_type=file.content_type or "application/octet-stream",
        )

        # Get the validated file type from S3 service
        file_type = s3_service.validate_file_type(file_content)
        file_size = len(file_content)

        # Create file attachment record (without chat_message_id)
        # The file will be linked to a message when the user sends a chat message with attachment_ids
        attachment_id = db.create_file_attachment_upload(
            conversation_id=conversation_id,
            filename=file.filename,
            file_size=file_size,
            file_type=file_type,
            s3_key=s3_key,
            uploaded_by_user_id=current_user.id,
        )

        try:
            asyncio.create_task(
                process_attachment_background(
                    db=db,
                    attachment_id=attachment_id,
                    file_type=file_type,
                    file_content=file_content,
                    filename=file.filename,
                    s3_key=s3_key,
                    llm_model=llm_model,
                    llm_provider=llm_provider,
                )
            )
        except Exception:
            logger.exception("Failed to schedule attachment processing task")

        # Return file metadata for frontend to use
        file_metadata = FileMetadata(
            id=attachment_id,
            s3_key=s3_key,
            filename=file.filename,
            file_size=file_size,
            file_type=file_type,
            conversation_id=conversation_id,
        )

        return FileUploadResponse(
            file=file_metadata,
            message=f"File '{file.filename}' uploaded successfully",
        )

    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        response.status_code = 500
        return ErrorResponse(error="Upload failed", detail=f"File upload failed: {str(e)}")


@router.get("/files/{file_id}/download", response_model=None)
async def download_file(file_id: int, response: Response) -> Union[RedirectResponse, ErrorResponse]:
    """
    Download a file attachment via temporary signed URL.

    Args:
        file_id: ID of the file attachment

    Returns:
        Redirect response to S3 signed URL

    Raises:
        HTTPException: If file not found or download fails
    """
    if file_id <= 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid file ID", detail="File ID must be positive")

    db = get_database()

    try:
        # Get file attachment metadata
        file_attachments = db.get_file_attachments_by_ids([file_id])
        if not file_attachments:
            response.status_code = 404
            return ErrorResponse(error="File not found", detail="File not found")
        file_attachment = file_attachments[0]

        # Initialize S3 service
        s3_service = S3Service()

        # Check if file exists in S3
        if not s3_service.file_exists(file_attachment.s3_key):
            logger.error(f"File not found in S3: {file_attachment.s3_key}")
            response.status_code = 404
            return ErrorResponse(
                error="File not found in storage", detail="File not found in storage"
            )

        # Generate temporary download URL (expires in 1 hour)
        download_url = s3_service.generate_download_url(
            s3_key=file_attachment.s3_key, expires_in=3600
        )

        logger.info(f"Generated download URL for file {file_id}: {file_attachment.filename}")

        # Redirect user to the signed URL
        return RedirectResponse(url=download_url, status_code=302)

    except Exception as e:
        logger.exception(f"File download failed: {e}")
        response.status_code = 500
        return ErrorResponse(error="Download failed", detail=f"File download failed: {str(e)}")


@router.get("/{conversation_id}/files")
async def list_conversation_files(
    conversation_id: int, response: Response
) -> Union[FileListResponse, ErrorResponse]:
    """
    List all file attachments for a conversation.

    Args:
        conversation_id: ID of the conversation

    Returns:
        JSON response with list of file attachments

    Raises:
        HTTPException: If conversation not found
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

        # Get all chat messages for this conversation's idea
        idea_data = db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            return FileListResponse(files=[], file_count=0)

        # Get all file attachments for this conversation
        file_attachments = db.get_conversation_file_attachments(conversation_id=conversation_id)

        # Collect all file attachments from all messages
        all_attachments = []
        for attachment in file_attachments:
            # Convert to FileAttachment Pydantic model
            file_attachment = FileAttachment(
                id=attachment.id,
                filename=attachment.filename,
                file_size=attachment.file_size,
                file_type=attachment.file_type,
                s3_key=attachment.s3_key,
                created_at=attachment.created_at.isoformat(),
            )
            all_attachments.append(file_attachment)

        return FileListResponse(
            files=all_attachments,
            file_count=len(all_attachments),
        )

    except Exception as e:
        logger.exception(f"Failed to list conversation files: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="List failed", detail=f"Failed to list conversation files: {str(e)}"
        )
