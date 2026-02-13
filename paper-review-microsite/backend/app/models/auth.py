"""
Authentication-related Pydantic models.

Simplified version for AE Paper Review (no admin, no service keys).
"""

from typing import Optional

from pydantic import BaseModel, Field


class AuthUser(BaseModel):
    """User information returned by authentication endpoints."""

    id: int = Field(..., description="Database user ID")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")


class AuthStatus(BaseModel):
    """Authentication status response."""

    authenticated: bool = Field(..., description="Whether the user is authenticated")
    user: Optional[AuthUser] = Field(None, description="User information if authenticated")


class ClerkSessionResponse(BaseModel):
    """Response from Clerk session exchange."""

    session_token: str = Field(..., description="Internal session token for API calls")
    user: AuthUser = Field(..., description="Authenticated user information")
