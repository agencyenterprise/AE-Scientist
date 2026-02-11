"""
Admin authorization helpers.

Provides utility functions for verifying admin access in API endpoints.
"""

from fastapi import HTTPException, Request, status

from app.middleware.auth import get_current_user
from app.services.database.users import UserData


def require_admin(request: Request) -> UserData:
    """
    Get the current user and verify they have admin privileges.

    Args:
        request: The FastAPI request object

    Returns:
        The authenticated admin user

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
    """
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
