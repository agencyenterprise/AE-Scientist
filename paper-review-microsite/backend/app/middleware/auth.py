"""
Authentication middleware.

Simplified version for AE Paper Review (user auth only, no service keys).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.auth.tokens import extract_bearer_token
from app.services.auth_service import AuthService
from app.services.database.users import UserData

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for handling user authentication."""

    def __init__(self, app: ASGIApp, exclude_paths: list[str] | None = None) -> None:
        """
        Initialize authentication middleware.

        Args:
            app: FastAPI application
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.auth_service = AuthService()

        # Default paths that don't require authentication
        self.exclude_paths = exclude_paths or [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/auth/clerk-session",
            "/api/auth/status",
            "/api/auth/logout",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process request through authentication middleware.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler
        """

        # Skip authentication for CORS preflight requests (OPTIONS)
        if request.method == "OPTIONS":
            return await call_next(request)
        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            return await call_next(request)
        # Try user session authentication using bearer tokens
        authorization_header = request.headers.get("authorization")
        session_token = extract_bearer_token(authorization_header)
        if session_token:
            user = await self.auth_service.get_user_by_session(session_token=session_token)
            if user:
                request.state.auth_type = "user"
                request.state.user = user
                return await call_next(request)
        # No valid authentication found
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Please log in."},
        )

    def _should_skip_auth(self, request: Request) -> bool:
        """
        Check if request path should skip authentication.

        Args:
            request: Incoming request

        Returns:
            True if authentication should be skipped
        """
        path = request.url.path

        # Check exact matches
        if path in self.exclude_paths:
            return True

        # Check if path starts with any excluded prefix (but not root path)
        for exclude_path in self.exclude_paths:
            # Skip prefix matching for root path to avoid matching everything
            if exclude_path == "/":
                continue
            if path.startswith(exclude_path):
                return True

        return False


def get_current_user(request: Request) -> UserData:
    """
    Get current authenticated user from request state.

    Args:
        request: Current request

    Returns:
        User NamedTuple

    Raises:
        HTTPException: If no user is authenticated
    """
    auth_type = getattr(request.state, "auth_type", None)
    if auth_type != "user":
        raise HTTPException(status_code=401, detail="User authentication required")

    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="User authentication required")

    return cast(UserData, user)
