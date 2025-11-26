"""
LLM Defaults API endpoints.

This module contains FastAPI routes for managing default LLM model and provider settings.
"""

import logging
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.models import (
    LLMDefault,
    LLMDefaultsResponse,
    LLMDefaultsUpdateRequest,
    LLMDefaultsUpdateResponse,
    LLMProvidersResponse,
)
from app.prompt_types import PromptTypes
from app.services import get_database
from app.services.anthropic_service import SUPPORTED_MODELS as ANTHROPIC_MODELS
from app.services.grok_service import SUPPORTED_MODELS as GROK_MODELS
from app.services.openai_service import SUPPORTED_MODELS as OPENAI_MODELS

router = APIRouter(prefix="/llm-defaults")
logger = logging.getLogger(__name__)

# Provider constants
SUPPORTED_PROVIDERS = {
    "anthropic": ANTHROPIC_MODELS,
    "grok": GROK_MODELS,
    "openai": OPENAI_MODELS,
}


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


@router.get("/providers")
async def get_llm_providers(response: Response) -> Union[LLMProvidersResponse, ErrorResponse]:
    """
    Get all available LLM providers and their supported models.
    """
    try:
        return LLMProvidersResponse(
            providers=SUPPORTED_PROVIDERS,
        )
    except Exception as e:
        logger.exception(f"Error getting LLM providers: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Providers failed", detail=f"Failed to get LLM providers: {str(e)}"
        )


@router.get("/{prompt_type}")
async def get_llm_defaults(
    prompt_type: str, response: Response
) -> Union[LLMDefaultsResponse, ErrorResponse]:
    """
    Get the current default LLM settings for a specific prompt type.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    # Validate prompt type
    valid_prompt_types = [pt.value for pt in PromptTypes]
    if prompt_type not in valid_prompt_types:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid prompt type",
            detail=f"Invalid prompt type. Must be one of: {', '.join(valid_prompt_types)}",
        )

    db = get_database()

    try:
        # Get current default from database
        prompt_type_enum = PromptTypes(prompt_type)
        llm_params = db.get_default_llm_parameters(prompt_type_enum)

        current_default = LLMDefault(
            llm_provider=llm_params.llm_provider,
            llm_model=llm_params.llm_model,
        )

        return LLMDefaultsResponse(
            current_default=current_default,
        )

    except Exception as e:
        logger.exception(f"Error getting LLM defaults for {prompt_type}: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Defaults failed", detail=f"Failed to get LLM defaults: {str(e)}"
        )


@router.put("/{prompt_type}")
async def update_llm_defaults(
    prompt_type: str, request_data: LLMDefaultsUpdateRequest, request: Request, response: Response
) -> Union[LLMDefaultsUpdateResponse, ErrorResponse]:
    """
    Update the default LLM settings for a specific prompt type.
    """
    if not prompt_type.strip():
        response.status_code = 400
        return ErrorResponse(error="Empty prompt type", detail="Prompt type cannot be empty")

    # Validate prompt type
    valid_prompt_types = [pt.value for pt in PromptTypes]
    if prompt_type not in valid_prompt_types:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid prompt type",
            detail=f"Invalid prompt type. Must be one of: {', '.join(valid_prompt_types)}",
        )

    # Validate provider exists
    if request_data.llm_provider not in SUPPORTED_PROVIDERS:
        response.status_code = 400
        return ErrorResponse(
            error="Unsupported provider",
            detail=f"Unsupported provider: {request_data.llm_provider}. Must be one of: {', '.join(SUPPORTED_PROVIDERS.keys())}",
        )

    # Validate model exists for provider
    provider_models = SUPPORTED_PROVIDERS[request_data.llm_provider]
    model_ids = [model.id for model in provider_models]
    if request_data.llm_model not in model_ids:
        response.status_code = 400
        return ErrorResponse(
            error="Unsupported model",
            detail=f"Unsupported model {request_data.llm_model} for provider {request_data.llm_provider}",
        )

    # Get authenticated user
    user = get_current_user(request)

    db = get_database()

    try:
        # Update default in database
        success = db.set_default_llm_parameters(
            prompt_type=prompt_type,
            llm_model=request_data.llm_model,
            llm_provider=request_data.llm_provider,
            created_by_user_id=user.id,
        )

        if not success:
            response.status_code = 500
            return ErrorResponse(error="Update failed", detail="Failed to update LLM defaults")

        updated_default = LLMDefault(
            llm_provider=request_data.llm_provider,
            llm_model=request_data.llm_model,
        )

        return LLMDefaultsUpdateResponse(
            message=f"Successfully updated LLM defaults for {prompt_type}",
            updated_default=updated_default,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error updating LLM defaults for {prompt_type}: {e}")
        response.status_code = 500
        return ErrorResponse(
            error="Update failed", detail=f"Failed to update LLM defaults: {str(e)}"
        )
