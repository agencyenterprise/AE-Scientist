"""
Centralized prompts for LLM services.

This module contains all default prompts used by LLM services and provides
utilities to retrieve custom prompts from the database when available.
"""

import logging
from typing import List

import requests

from app.prompt_types import PromptTypes
from app.services.base_llm_service import FileAttachmentData
from app.services.database import DatabaseManager
from app.services.pdf_service import PDFService
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)


def get_default_idea_generation_prompt() -> str:
    """
    Get the default system prompt for research idea generation.

    Returns:
        str: The default system prompt for idea generation
    """
    return (
        "You are an AI research assistant specialized in transforming conversational ideas into structured research proposals for AGI research teams. "
        "Analyze the conversation and extract actionable research ideas that could be investigated by AGI researchers. "
        "Focus on novel hypotheses, experimental designs, theoretical frameworks, or innovative approaches discussed. "
        "Always return a single JSON object that captures the complete research idea. "
        "Do not include XML tags, Markdown, or commentary outside the JSON object. "
        "Every string must use double quotes and arrays must be valid JSON arrays."
    )


def get_idea_generation_prompt(db: DatabaseManager) -> str:
    """
    Get the system prompt for research idea generation.

    Checks database for active custom prompt first, falls back to default if none found.

    Args:
        db: Database manager instance

    Returns:
        str: The system prompt to use for idea generation
    """
    try:
        prompt_data = db.get_active_prompt(PromptTypes.IDEA_GENERATION.value)
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
    return (
        "You are the AE Scientist assistant. Given a user-provided idea title and hypothesis, "
        "craft a detailed draft idea ready for evaluation. Maintain a professional but concise tone.\n\n"
        "Follow these steps:\n"
        "1. Restate the title in a compelling single sentence.\n"
        "2. Expand the hypothesis into 2-3 short paragraphs that describe the opportunity, target users, and expected impact.\n"
        "3. List exactly three concrete next steps to validate or advance the idea.\n"
        "4. Highlight any key assumptions or risks as bullet points.\n\n"
        "Always return a single JSON object that fits the LLMIdeaGeneration schema."
    )


def get_manual_seed_prompt(db: DatabaseManager) -> str:
    """
    Retrieve the system prompt for manual idea seed generation, falling back to defaults.

    Args:
        db: Database manager instance

    Returns:
        str: The system prompt to use for manual seed idea generation.
    """
    try:
        prompt_data = db.get_active_prompt(PromptTypes.MANUAL_IDEA_GENERATION.value)
        if prompt_data and prompt_data.system_prompt:
            return prompt_data.system_prompt
    except Exception as exc:
        logger.warning("Failed to get manual seed prompt: %s", exc)
    return get_default_manual_seed_prompt()


def get_default_chat_system_prompt() -> str:
    """
    Get the default system prompt for chat conversations.

    Returns:
        str: The default system prompt to use for chat
    """
    return (
        "You are an AI research assistant specialized in helping AGI research teams refine and develop research ideas. "
        "You have access to tools that allow you to update the research idea with improvements. "
        "\n\nAvailable tools:\n"
        "- update_idea: Update all fields of the research idea with improvements\n"
        "\n\nKey Guidelines:\n"
        "- Be conversational and helpful - ask clarifying questions to understand user needs\n"
        "- Focus on practical improvements - suggest specific, actionable enhancements\n"
        "- Use the tools provided to update research ideas\n"
        "- Help refine experiments, hypotheses, and identify potential limitations\n"
        "- Break down complex research questions into manageable experiments\n"
        "- Consider technical feasibility and resource requirements\n"
        "- Ask clarifying questions when needed to better understand the research goals\n"
        "- When updating experiments or risk factors, provide them as complete JSON arrays"
        "\n\nCurrent research idea you are working on:\n"
        "{{current_idea}}"
        "\n\nOriginal imported conversation that inspired this idea:\n"
        "---\n{{original_conversation_summary}}\n---\n\n"
        "Use this original conversation as context when discussing and improving the research idea."
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
    Get the system prompt for idea chat.

    Checks database for active custom prompt first, falls back to default if none found.
    Includes the original conversation context and current research idea.

    Args:
        db: Database manager instance
        conversation_id: Conversation ID to include original context and get idea

    Returns:
        str: The system prompt to use for chat
    """
    try:
        prompt_data = db.get_active_prompt(PromptTypes.IDEA_CHAT.value)
        if prompt_data and prompt_data.system_prompt:
            base_prompt = prompt_data.system_prompt
        else:
            base_prompt = get_default_chat_system_prompt()
    except Exception as e:
        logger.warning(f"Failed to get custom chat system prompt: {e}")
        base_prompt = get_default_chat_system_prompt()

    # Retrieve the current research idea
    current_idea_text = ""
    try:
        idea = db.get_idea_by_conversation_id(conversation_id)
        if idea:
            experiments_formatted = "\n".join([f"  - {exp}" for exp in idea.experiments])
            risks_formatted = "\n".join(
                [f"  - {risk}" for risk in idea.risk_factors_and_limitations]
            )
            current_idea_text = (
                f"Title: {idea.title}\n\n"
                f"Short Hypothesis: {idea.short_hypothesis}\n\n"
                f"Related Work: {idea.related_work}\n\n"
                f"Abstract: {idea.abstract}\n\n"
                f"Experiments:\n{experiments_formatted}\n\n"
                f"Expected Outcome: {idea.expected_outcome}\n\n"
                f"Risk Factors and Limitations:\n{risks_formatted}"
            )
        else:
            current_idea_text = "No research idea found."
    except Exception as e:
        logger.warning(f"Failed to get idea for conversation ID {conversation_id}: {e}")
        current_idea_text = "Error retrieving research idea."

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
    result = base_prompt.replace("{{current_idea}}", current_idea_text)
    result = result.replace("{{original_conversation_summary}}", summary)
    result = result.replace("{{memories_context}}", "")

    return result
