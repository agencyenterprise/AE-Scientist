"""
Authentication API endpoints.

Handles user authentication via Clerk.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.auth.tokens import extract_bearer_token
from app.middleware.auth import get_current_user
from app.models.auth import AuthStatus, AuthUser
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize auth service
auth_service = AuthService()


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

    user = await auth_service.get_user_by_session(session_token=session_token)
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
            success = await auth_service.logout_user(session_token=session_token)
            if success:
                logger.debug("User logged out successfully")
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
        count = await auth_service.cleanup_expired_sessions()
        return {"message": f"Cleaned up {count} expired sessions"}

    except Exception as e:
        logger.exception(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions") from e


@router.post("/clerk-session")
async def clerk_session_exchange(request: Request) -> Dict[str, Any]:
    """
    Exchange Clerk session token for internal session token.

    This allows the frontend to use Clerk for auth UI,
    but still use our internal session system for API calls.

    Args:
        request: Request with Authorization header containing Clerk session token

    Returns:
        Dict with internal session_token and user info
    """
    try:
        # Extract Clerk session token from Authorization header
        authorization_header = request.headers.get("authorization")
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
            )

        clerk_session_token = authorization_header.split(" ", 1)[1]

        # Authenticate with Clerk
        auth_result = await auth_service.authenticate_with_clerk(clerk_session_token)
        if not auth_result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Clerk session"
            )

        user = auth_result["user"]
        internal_session_token = auth_result["session_token"]

        return {
            "session_token": internal_session_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error exchanging Clerk session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to exchange session"
        ) from e
