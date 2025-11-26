"""
Authentication-related Pydantic models.

This module contains all models related to user authentication,
sessions, and service-to-service authentication.
"""

from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """Represents a user in the system."""

    id: int = Field(..., description="Database user ID")
    google_id: str = Field(..., description="Google OAuth user ID")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether the user account is active")
    created_at: str = Field(..., description="ISO format creation timestamp")
    updated_at: str = Field(..., description="ISO format last update timestamp")


class UserSession(BaseModel):
    """Represents a user session."""

    id: int = Field(..., description="Database session ID")
    user_id: int = Field(..., description="Associated user ID")
    session_token: str = Field(..., description="Session token")
    expires_at: str = Field(..., description="ISO format expiration timestamp")
    created_at: str = Field(..., description="ISO format creation timestamp")


class ServiceKey(BaseModel):
    """Represents a service API key."""

    id: int = Field(..., description="Database service key ID")
    service_name: str = Field(..., description="Name of the service")
    is_active: bool = Field(..., description="Whether the service key is active")
    created_at: str = Field(..., description="ISO format creation timestamp")
    last_used_at: Optional[str] = Field(None, description="ISO format last used timestamp")


class AuthUser(BaseModel):
    """User information returned by authentication endpoints."""

    id: int = Field(..., description="Database user ID")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")


class AuthStatus(BaseModel):
    """Authentication status response."""

    authenticated: bool = Field(..., description="Whether the user is authenticated")
    user: Optional[AuthUser] = Field(None, description="User information if authenticated")


class GoogleOAuthCallbackRequest(BaseModel):
    """Request model for Google OAuth callback."""

    code: str = Field(..., description="Authorization code from Google")
    state: Optional[str] = Field(None, description="State parameter for security")
