"""
MCP Integration API endpoints for managing API keys.
"""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.services import get_database

router = APIRouter(prefix="/mcp-integration", tags=["mcp-integration"])

logger = logging.getLogger(__name__)


class MCPApiKeyResponse(BaseModel):
    """Response containing the MCP API key status."""

    has_key: bool
    api_key: Optional[str] = None  # Full key only after generation
    masked_key: Optional[str] = None  # Masked version for display


class MCPApiKeyGeneratedResponse(BaseModel):
    """Response after generating a new API key."""

    api_key: str
    masked_key: str


class MCPApiKeyRevokedResponse(BaseModel):
    """Response after revoking an API key."""

    success: bool
    message: str


def _mask_api_key(api_key: str) -> str:
    """Mask an API key for display, showing only first 8 and last 4 chars."""
    if len(api_key) <= 12:
        return "*" * len(api_key)
    return f"{api_key[:8]}...{api_key[-4:]}"


def _generate_mcp_api_key() -> str:
    """Generate a new MCP API key with a recognizable prefix."""
    return f"mcp_{secrets.token_urlsafe(32)}"


@router.get("/key", response_model=MCPApiKeyResponse)
async def get_mcp_api_key(request: Request) -> MCPApiKeyResponse:
    """Get the current user's MCP API key."""
    user = get_current_user(request)
    db = get_database()

    api_key = await db.get_user_mcp_api_key(user.id)

    if api_key:
        return MCPApiKeyResponse(
            has_key=True,
            api_key=api_key,
            masked_key=_mask_api_key(api_key),
        )

    return MCPApiKeyResponse(has_key=False)


@router.post("/generate-key", response_model=MCPApiKeyGeneratedResponse)
async def generate_mcp_api_key(request: Request) -> MCPApiKeyGeneratedResponse:
    """Generate a new MCP API key for the current user (replaces existing)."""
    user = get_current_user(request)
    db = get_database()

    new_key = _generate_mcp_api_key()
    success = await db.set_user_mcp_api_key(user.id, new_key)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key",
        )

    logger.info("Generated new MCP API key for user_id=%s", user.id)

    return MCPApiKeyGeneratedResponse(
        api_key=new_key,
        masked_key=_mask_api_key(new_key),
    )


@router.delete("/key", response_model=MCPApiKeyRevokedResponse)
async def revoke_mcp_api_key(request: Request) -> MCPApiKeyRevokedResponse:
    """Revoke the current user's MCP API key."""
    user = get_current_user(request)
    db = get_database()

    success = await db.set_user_mcp_api_key(user.id, None)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key",
        )

    logger.info("Revoked MCP API key for user_id=%s", user.id)

    return MCPApiKeyRevokedResponse(
        success=True,
        message="API key revoked successfully",
    )
