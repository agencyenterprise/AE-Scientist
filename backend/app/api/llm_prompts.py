"""
LLM Prompt API endpoints.

This module contains FastAPI routes for LLM prompt management.
"""

import logging
from typing import Optional, Union

from app.middleware.auth import get_current_user
from app.models import LLMPromptCreateRequest, LLMPromptDeleteResponse, LLMPromptResponse
from app.prompt_types import PromptTypes
from app.services import get_database
from app.services.prompts import get_default_chat_system_prompt, get_default_idea_generation_prompt
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/llm-prompts")
logger = logging.getLogger(__name__)


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


def get_default_prompt(prompt_type: str) -> str:
    """
    Get the default system promptsfor a given prompt type.

    Args:
        prompt_type: The type of prompt (e.g., PromptTypes.IDEA_CHAT)

    Returns:
        str: The system prompt to use for chat
    """
    if prompt_type == PromptTypes.IDEA_CHAT:
        return get_default_chat_system_prompt()
    elif prompt_type == PromptTypes.IDEA_GENERATION:
        return get_default_idea_generation_prompt()
    else:
        return ""


@router.get("/{prompt_type}")
async def get_llm_prompt(
    prompt_type: str, response: Response
) -> Union[LLMPromptResponse, ErrorResponse]:
    """
    Get the active LLM prompt for a given type.
    Returns the prompt from database if available, otherwise indicates default is being used.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    db = get_database()

    try:
        # Try to get active prompt from database
        prompt_data = db.get_active_prompt(prompt_type)

        if prompt_data:
            # Return custom prompt data
            return LLMPromptResponse(
                system_prompt=prompt_data.system_prompt,
                is_default=False,
            )
        else:
            # No custom prompt found, return default from code
            default_prompt = get_default_prompt(prompt_type)

            return LLMPromptResponse(
                system_prompt=default_prompt,
                is_default=True,
            )

    except Exception as e:
        logger.exception(f"Error getting LLM prompt: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Get prompt failed", detail=f"Failed to get LLM prompt: {str(e)}"
        )


@router.get("/{prompt_type}/default")
async def get_default_llm_prompt(
    prompt_type: str, response: Response
) -> Union[LLMPromptResponse, ErrorResponse]:
    """
    Get the default LLM prompt for a given type.
    This always returns the hardcoded default prompt, ignoring any custom prompts.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    try:
        default_prompt = get_default_prompt(prompt_type)

        return LLMPromptResponse(
            system_prompt=default_prompt,
            is_default=True,
        )

    except Exception as e:
        logger.exception(f"Error getting default LLM prompt: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Get default failed", detail=f"Failed to get default LLM prompt: {str(e)}"
        )


@router.post("/{prompt_type}")
async def create_llm_prompt(
    prompt_type: str, request_data: LLMPromptCreateRequest, request: Request, response: Response
) -> Union[LLMPromptResponse, ErrorResponse]:
    """
    Create or update an LLM prompt for a given type.
    This will deactivate any existing active prompt of the same type.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    # Ensure the prompt_type in URL matches the one in request body
    if prompt_type != request_data.prompt_type:
        response.status_code = 400
        return ErrorResponse(
            error="Mismatched prompt type",
            detail="Prompt type in URL must match prompt type in request body",
        )

    # Get authenticated user
    user = get_current_user(request)

    db = get_database()

    try:
        # Create new prompt (this will deactivate any existing active prompt)
        db.create_prompt(
            prompt_type=request_data.prompt_type,
            system_prompt=request_data.system_prompt,
            created_by_user_id=user.id,
        )

        # Get the newly created prompt to return it
        prompt_data = db.get_active_prompt(request_data.prompt_type)
        if not prompt_data:
            response.status_code = 500
            return ErrorResponse(
                error="Retrieval failed", detail="Failed to retrieve created prompt"
            )

        # Return the simplified prompt response
        return LLMPromptResponse(
            system_prompt=prompt_data.system_prompt,
            is_default=False,
        )

    except Exception as e:
        logger.exception(f"Error creating LLM prompt: {e}")
        response.status_code = 500
        return ErrorResponse(error="Create failed", detail=f"Failed to create LLM prompt: {str(e)}")


@router.delete("/{prompt_type}")
async def delete_llm_prompt(
    prompt_type: str, response: Response
) -> Union[LLMPromptDeleteResponse, ErrorResponse]:
    """
    Deactivate the active LLM prompt for a given type.
    This will revert to using the default prompt from code.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    db = get_database()

    try:
        # Deactivate the prompt
        success = db.deactivate_prompt(prompt_type)

        if success:
            return LLMPromptDeleteResponse(
                message=f"Successfully deactivated custom prompt for {prompt_type}. Now using default prompt.",
            )
        else:
            # No active prompt was found to deactivate
            return LLMPromptDeleteResponse(
                message=f"No active custom prompt found for {prompt_type}. Already using default prompt.",
            )

    except Exception as e:
        logger.exception(f"Error deleting LLM prompt: {e}")
        response.status_code = 500
        return ErrorResponse(error="Delete failed", detail=f"Failed to delete LLM prompt: {str(e)}")
