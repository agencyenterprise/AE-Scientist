"""
Authentication API endpoints.

Handles user authentication via Google OAuth 2.0.
"""

import logging
import secrets
from typing import Dict
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.auth.tokens import extract_bearer_token
from app.config import settings
from app.middleware.auth import get_current_user
from app.models.auth import AuthStatus, AuthUser
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize auth service
auth_service = AuthService()


@router.get("/login")
async def login(_request: Request) -> RedirectResponse:
    """
    Initiate Google OAuth login flow.

    Returns:
        Redirect response to Google OAuth authorization URL
    """
    try:
        # Generate state parameter for security
        state = secrets.token_urlsafe(32)

        # Store state in session/cache if needed (for now we'll trust Google's flow)
        auth_url = auth_service.get_google_auth_url(state=state)

        logger.info("Redirecting user to Google OAuth")
        return RedirectResponse(url=auth_url, status_code=302)

    except Exception as e:
        logger.exception(f"Error initiating login: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate login") from e


@router.get("/callback")
async def auth_callback(
    code: str = Query(None, description="Authorization code from Google"),
    state: str = Query(None, description="State parameter for security"),
    error: str = Query(None, description="Error from OAuth provider"),
) -> RedirectResponse:
    """
    Handle Google OAuth callback.

    Args:
        response: FastAPI response object
        code: Authorization code from Google
        state: State parameter for verification
        error: Error parameter if OAuth failed

    Returns:
        Redirect response to frontend dashboard or login page
    """
    try:
        # Check for OAuth errors
        if error:
            logger.warning(f"OAuth error: {error}")
            error_url = f"{settings.FRONTEND_URL}/login?error=oauth_cancelled"
            return RedirectResponse(url=error_url, status_code=302)

        # Check if code is missing
        if not code:
            logger.warning("OAuth callback missing authorization code")
            error_url = f"{settings.FRONTEND_URL}/login?error=auth_failed"
            return RedirectResponse(url=error_url, status_code=302)

        # Authenticate with Google
        auth_result = auth_service.authenticate_with_google(code, state)
        if not auth_result:
            logger.warning("Failed to authenticate with Google")
            error_url = f"{settings.FRONTEND_URL}/login?error=auth_failed"
            return RedirectResponse(url=error_url, status_code=302)

        user = auth_result["user"]
        session_token = auth_result["session_token"]

        # Redirect back to the SPA with the bearer token encoded in the hash fragment
        encoded_token = quote(session_token, safe="")
        success_url = f"{settings.FRONTEND_URL}/login#token={encoded_token}"
        logger.info("User authenticated successfully: %s", user.email)
        return RedirectResponse(url=success_url, status_code=302)

    except Exception as e:
        logger.exception(f"Error handling auth callback: {e}")
        error_url = f"{settings.FRONTEND_URL}/login?error=server_error"
        return RedirectResponse(url=error_url, status_code=302)


@router.get("/me", response_model=AuthUser)
async def get_current_user_info(request: Request) -> AuthUser:
    """
    Get current authenticated user information.

    Args:
        request: Current request

    Returns:
        Current user information
    """
    user = get_current_user(request)

    return AuthUser(id=user.id, email=user.email, name=user.name)


@router.get("/status", response_model=AuthStatus)
async def get_auth_status(request: Request) -> AuthStatus:
    """
    Check authentication status.

    Args:
        request: Current request (provides Authorization header)

    Returns:
        Authentication status and user info if authenticated
    """
    authorization_header = request.headers.get("authorization")
    session_token = extract_bearer_token(authorization_header)
    if not session_token:
        session_token = request.cookies.get("session_token")

    if not session_token:
        return AuthStatus(authenticated=False, user=None)

    user = auth_service.get_user_by_session(session_token=session_token)
    if not user:
        return AuthStatus(authenticated=False, user=None)

    return AuthStatus(
        authenticated=True, user=AuthUser(id=user.id, email=user.email, name=user.name)
    )


@router.post("/logout")
async def logout(request: Request) -> Dict[str, str]:
    """
    Log out current user.

    Args:
        request: FastAPI request object
        response: FastAPI response object

    Returns:
        Success message
    """
    try:
        authorization_header = request.headers.get("authorization")
        session_token = extract_bearer_token(authorization_header)

        if session_token:
            success = auth_service.logout_user(session_token=session_token)
            if success:
                logger.info("User logged out successfully")
            else:
                logger.warning("Failed to invalidate session during logout")

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.exception(f"Error during logout: {e}")
        return {"message": "Logged out successfully"}


@router.delete("/cleanup")
async def cleanup_expired_sessions() -> Dict[str, str]:
    """
    Clean up expired sessions (admin endpoint).

    Returns:
        Cleanup result message
    """
    try:
        count = auth_service.cleanup_expired_sessions()
        return {"message": f"Cleaned up {count} expired sessions"}

    except Exception as e:
        logger.exception(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions") from e
