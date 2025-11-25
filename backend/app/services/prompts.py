"""
Centralized prompts for LLM services.

This module contains all default prompts used by LLM services and provides
utilities to retrieve custom prompts from the database when available.
"""

import logging
from typing import List

import requests
from app.config import settings
from app.prompt_types import PromptTypes
from app.services.base_llm_service import FileAttachmentData
from app.services.database import DatabaseManager
from app.services.pdf_service import PDFService
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)


def get_default_project_generation_prompt() -> str:
    """
    Get the default system prompt for project draft generation.

    Returns:
        str: The default system prompt for project generation
    """
    return (
        f"You are an AI project manager specialized in transforming conversational ideas into structured experiment projects for AGI research teams. "
        "Analyze the conversation and extract actionable project concepts that could be experimented by a team of AGI researchers. "
        "Focus on technical experiments, research directions, implementation challenges, or innovative approaches discussed. "
        f"Generate a clear, concise project title (MAXIMUM {settings.MAX_PROJECT_TITLE_LENGTH} characters - this is a hard limit for Linear compatibility) and a detailed description that captures the core experimental value. "
        "The project should be something that can be worked on by a research team, not just a discussion topic. "
        "Keep titles short and punchy while still being descriptive. "
        "\n\nAdditional context from prior conversations (memories):\n"
        "{{context}}\n"
        "\nIMPORTANT: You must respond in this exact format:\n"
        "<title>Your project title here</title>\n"
        "<description>Your detailed project description here. Use markdown formatting for bullet points, lists, and other formatting.</description>"
    )


def get_project_generation_prompt(db: DatabaseManager, context: str) -> str:
    """
    Get the system prompt for project draft generation.

    Checks database for active custom prompt first, falls back to default if none found.

    Args:
        db: Database manager instance
        context: Pre-formatted context string to inject (e.g., memories)

    Returns:
        str: The system prompt to use for project generation
    """
    try:
        prompt_data = db.get_active_prompt(PromptTypes.PROJECT_DRAFT_GENERATION.value)
        if prompt_data:
            base_prompt = prompt_data.system_prompt
        else:
            base_prompt = get_default_project_generation_prompt()
    except Exception as e:
        logger.warning(f"Failed to get custom project generation prompt: {e}")
        base_prompt = get_default_project_generation_prompt()

    return base_prompt.replace("{{context}}", context or "")


def get_default_chat_system_prompt() -> str:
    """
    Get the default system prompt for chat conversations.

    Returns:
        str: The default system prompt to use for chat
    """
    return (
        "You are an AI project manager specialized in helping AGI research teams refine and develop project drafts. "
        "You have access to tools that allow you to update the project draft and create Linear projects when ready. "
        "\n\nAvailable tools:\n"
        "- update_project_draft: Update the title/description with improvements\n"
        "- create_linear_project: Create a Linear project (requires user confirmation)\n"
        "\n\nKey Guidelines:\n"
        "- Be conversational and helpful - ask clarifying questions to understand user needs\n"
        "- Focus on practical improvements - suggest specific, actionable enhancements\n"
        "- Use the tools provided to interact with project drafts and create Linear projects\n"
        "- Wait for user confirmation before creating Linear projects (this action locks the conversation)\n"
        "- Use markdown formatting in project descriptions for better readability\n"
        "- Break down complex projects into manageable components\n"
        "- Consider technical feasibility and resource requirements\n"
        "- Ask clarifying questions when needed to better understand the research goals\n"
        "- When user wants to create a Linear project, always ask for confirmation first"
        "\n\nCurrent project draft you are working on:\n"
        "{{current_project_draft}}"
        "\n\nOriginal imported conversation that inspired this project draft:\n"
        "---\n{{original_conversation_summary}}\n---\n\n"
        "Use this original conversation as context when discussing and improving the project draft."
        "\n\nAdditional context from prior conversations (memories):\n"
        "{{memories_context}}\n"
    )


def format_pdf_content_for_context(
    pdf_files: List[FileAttachmentData], s3_service: S3Service, pdf_service: PDFService
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
            file_url = s3_service.generate_download_url(file_attachment.s3_key)
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


def get_chat_system_prompt(db: DatabaseManager, conversation_id: int) -> str:
    """
    Get the system prompt for project chat.

    Checks database for active custom prompt first, falls back to default if none found.
    Includes the original conversation context and current project draft.

    Args:
        db: Database manager instance
        conversation_id: Conversation ID to include original context and get project draft

    Returns:
        str: The system prompt to use for chat
    """
    try:
        prompt_data = db.get_active_prompt(PromptTypes.PROJECT_DRAFT_CHAT.value)
        if prompt_data and prompt_data.system_prompt:
            base_prompt = prompt_data.system_prompt
        else:
            base_prompt = get_default_chat_system_prompt()
    except Exception as e:
        logger.warning(f"Failed to get custom chat system prompt: {e}")
        base_prompt = get_default_chat_system_prompt()

    # Retrieve the current project draft
    current_project_draft_text = ""
    try:
        project_draft = db.get_project_draft_by_conversation_id(conversation_id)
        if project_draft:
            current_project_draft_text = (
                f"Title: {project_draft.title}\n" f"Description: {project_draft.description}"
            )
        else:
            current_project_draft_text = "No project draft found."
    except Exception as e:
        logger.warning(f"Failed to get project draft for conversation ID {conversation_id}: {e}")
        current_project_draft_text = "Error retrieving project draft."

    # Retrieve memories
    stored_memories = db.get_memories_block(conversation_id=conversation_id, source="imported_chat")
    memories = []
    for idx, m in enumerate(stored_memories.memories, start=1):
        try:
            memories.append(f"{idx}. {m['memory']}")
        except KeyError:
            continue
    memories_context = "\n".join(memories)

    # Retrieve the original conversation summary
    generated_summary = db.get_imported_conversation_summary_by_conversation_id(conversation_id)
    if generated_summary is None:
        # Summary was not generated yet, we need to use the imported chat content
        conversation = db.get_conversation_by_id(conversation_id)
        assert conversation is not None and conversation.imported_chat is not None
        messages = conversation.imported_chat
        summary = "\n\n".join([f"{msg.role}: {msg.content}" for msg in messages])
    else:
        summary = generated_summary.summary

    # Replace placeholders
    result = base_prompt.replace("{{current_project_draft}}", current_project_draft_text)
    result = result.replace("{{original_conversation_summary}}", summary)
    result = result.replace("{{memories_context}}", memories_context)

    return result
