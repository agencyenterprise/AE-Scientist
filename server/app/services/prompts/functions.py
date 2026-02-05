"""
Centralized prompts for LLM services.

This module contains all default prompts used by LLM services and provides
utilities to retrieve custom prompts from the database when available.
"""

import logging
from typing import TYPE_CHECKING, List

import requests

from app.prompt_types import PromptTypes
from app.services.database import DatabaseManager
from app.services.database.rp_llm_reviews import LlmReview
from app.services.pdf_service import PDFService
from app.services.prompts.render import render_text
from app.services.s3_service import S3Service

if TYPE_CHECKING:
    from app.services.base_llm_service import FileAttachmentData

logger = logging.getLogger(__name__)


def get_default_idea_generation_prompt() -> str:
    """
    Get the default system prompt for research idea generation.

    Returns:
        str: The default system prompt for idea generation
    """
    return render_text(template_name="idea_generation.txt.j2")


async def get_idea_generation_prompt(db: DatabaseManager) -> str:
    """
    Get the system prompt for research idea generation.

    Checks database for active custom prompt first, falls back to default if none found.

    Args:
        db: Database manager instance

    Returns:
        str: The system prompt to use for idea generation
    """
    try:
        prompt_data = await db.get_active_prompt(PromptTypes.IDEA_GENERATION.value)
        if prompt_data:
            base_prompt = prompt_data.system_prompt
        else:
            base_prompt = get_default_idea_generation_prompt()
    except Exception as e:
        logger.warning(f"Failed to get custom idea generation prompt: {e}")
        base_prompt = get_default_idea_generation_prompt()

    base_prompt = base_prompt.replace("{{context}}", "")
    return base_prompt


def get_default_manual_seed_prompt() -> str:
    """
    Default system prompt for manual idea seeds.

    Returns:
        str: The default system prompt for manual idea creation.
    """
    return render_text(template_name="manual_seed.txt.j2")


async def get_manual_seed_prompt(db: DatabaseManager) -> str:
    """
    Retrieve the system prompt for manual idea seed generation, falling back to defaults.

    Args:
        db: Database manager instance

    Returns:
        str: The system prompt to use for manual seed idea generation.
    """
    try:
        prompt_data = await db.get_active_prompt(PromptTypes.MANUAL_IDEA_GENERATION.value)
        if prompt_data and prompt_data.system_prompt:
            return prompt_data.system_prompt
    except Exception as exc:
        logger.warning("Failed to get manual seed prompt: %s", exc)
    return get_default_manual_seed_prompt()


def get_default_chat_system_prompt(current_idea: str, original_conversation_summary: str) -> str:
    """
    Get the default system prompt for chat conversations.

    Args:
        current_idea: The current research idea text
        original_conversation_summary: Summary of the original conversation

    Returns:
        str: The default system prompt to use for chat
    """
    return render_text(
        template_name="chat_system.txt.j2",
        context={
            "current_idea": current_idea,
            "original_conversation_summary": original_conversation_summary,
        },
    )


def format_pdf_content_for_context(
    pdf_files: "List[FileAttachmentData]", s3_service: S3Service, pdf_service: PDFService
) -> str:
    """
    Extract text content from PDF files for LLM context.

    Note: This only handles PDFs. Images should be passed directly to vision models
    using their native image content formats, not as text descriptions.

    Args:
        pdf_files: List of FileAttachmentData objects (PDFs only)
        s3_service: S3Service instance for downloading files
        pdf_service: PDFService instance for text extraction

    Returns:
        Formatted string with extracted PDF text content
    """
    if not pdf_files:
        return ""

    formatted_content = "\n\n--- PDF Documents ---\n"

    for file_attachment in pdf_files:
        formatted_content += f"\n**{file_attachment.filename}:**\n"

        try:
            # Generate temporary download URL from S3
            file_url = s3_service.generate_download_url(file_attachment.s3_key, expires_in=3600)
            # Download file content
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            file_content = response.content

            # Extract text from PDF
            pdf_text = pdf_service.extract_text_from_pdf(file_content)
            formatted_content += f"{pdf_text}\n\n"
        except Exception as e:
            logger.exception(f"Failed to extract PDF text for {file_attachment.filename}: {e}")
            formatted_content += f"(Unable to extract text: {str(e)})\n\n"

    return formatted_content


async def get_chat_system_prompt(db: DatabaseManager, conversation_id: int) -> str:
    """
    Get the system prompt for idea chat.

    Checks database for active custom prompt first, falls back to default if none found.
    Includes the original conversation context and current research idea.

    Args:
        db: Database manager instance
        conversation_id: Conversation ID to include original context and get idea

    Returns:
        str: The system prompt to use for chat
    """
    # Retrieve the current research idea
    current_idea_text = ""
    try:
        idea = await db.get_idea_by_conversation_id(conversation_id)
        if idea:
            # Include both title and markdown content so LLM knows the current title
            current_idea_text = f"# {idea.title}\n\n{idea.idea_markdown}"
        else:
            current_idea_text = "No research idea found."
    except Exception as e:
        logger.warning(f"Failed to get idea for conversation ID {conversation_id}: {e}")
        current_idea_text = "Error retrieving research idea."

    # Retrieve the original conversation summary
    generated_summary = await db.get_imported_conversation_summary_by_conversation_id(
        conversation_id
    )
    if generated_summary is None:
        # Summary was not generated yet, we need to use the imported chat content
        conversation = await db.get_conversation_by_id(conversation_id)
        assert conversation is not None and conversation.imported_chat is not None
        messages = conversation.imported_chat
        summary = "\n\n".join([f"{msg.role}: {msg.content}" for msg in messages])
    else:
        summary = generated_summary.summary

    # Check for custom prompt from database
    try:
        prompt_data = await db.get_active_prompt(PromptTypes.IDEA_CHAT.value)
        if prompt_data and prompt_data.system_prompt:
            # Custom prompt from DB - use simple string replacement
            result = prompt_data.system_prompt.replace("{{current_idea}}", current_idea_text)
            result = result.replace("{{original_conversation_summary}}", summary)
            result = result.replace("{{memories_context}}", "")
            return result
    except Exception as e:
        logger.warning(f"Failed to get custom chat system prompt: {e}")

    # Use default template with Jinja rendering
    return get_default_chat_system_prompt(
        current_idea=current_idea_text,
        original_conversation_summary=summary,
    )


def format_review_feedback_message(review: LlmReview) -> str:
    """
    Format LLM review data into a user message for idea improvement.

    Args:
        review: LlmReview containing review fields from rp_llm_reviews table

    Returns:
        Formatted message asking the LLM to improve the idea based on review feedback
    """
    return render_text(
        template_name="review_feedback.txt.j2",
        context={
            "summary": review.summary,
            "strengths": review.strengths or [],
            "weaknesses": review.weaknesses or [],
            "decision": review.decision,
            "overall": review.overall,
        },
    )
