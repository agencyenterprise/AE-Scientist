"""
Authentication middleware.

Provides dual authentication support:
1. Service-to-service authentication via X-API-Key header
2. User authentication via session cookie
"""

import logging
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import AuthService
from app.services.database.users import UserData

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication."""

    def __init__(self, app: FastAPI, exclude_paths: Optional[list[str]] = None) -> None:
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
            "/api/auth/login",
            "/api/auth/callback",
            "/api/auth/status",
            "/api/research-pipeline/events",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
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
            return await call_next(request)  # type: ignore[no-any-return]

        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            return await call_next(request)  # type: ignore[no-any-return]

        # Try user session authentication (cookie)
        session_token = request.cookies.get("session_token")
        if session_token:
            user = self.auth_service.get_user_by_session(session_token)
            if user:
                request.state.auth_type = "user"
                request.state.user = user
                return await call_next(request)  # type: ignore[no-any-return]

        # No valid authentication found
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Please log in or provide valid API key."},
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
    if not hasattr(request.state, "auth_type") or request.state.auth_type != "user":
        raise HTTPException(status_code=401, detail="User authentication required")

    return request.state.user  # type: ignore[no-any-return]


def get_current_service(request: Request) -> str:
    """
    Get current authenticated service from request state.

    Args:
        request: Current request

    Returns:
        Service name

    Raises:
        HTTPException: If no service is authenticated
    """
    if not hasattr(request.state, "auth_type") or request.state.auth_type != "service":
        raise HTTPException(status_code=401, detail="Service authentication required")

    return request.state.service_name  # type: ignore[no-any-return]


def require_auth(auth_types: Optional[list[str]] = None) -> Callable:
    """
    Decorator to require specific authentication types for endpoints.

    Args:
        auth_types: List of required auth types ("user", "service", or both)

    Returns:
        Decorator function
    """
    if auth_types is None:
        auth_types = ["user", "service"]  # Allow both by default

    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args, **kwargs):  # type: ignore[no-untyped-def]
            if not hasattr(request.state, "auth_type"):
                raise HTTPException(status_code=401, detail="Authentication required")

            if request.state.auth_type not in auth_types:
                allowed = " or ".join(auth_types)
                raise HTTPException(
                    status_code=403, detail=f"This endpoint requires {allowed} authentication"
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
