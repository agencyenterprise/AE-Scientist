"""
API endpoints for user management.
"""

import logging

from fastapi import APIRouter, Request

from app.middleware.auth import get_current_user
from app.models.auth import UserListItem, UserListResponse
from app.services import get_database

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=UserListResponse)
def list_users(request: Request) -> UserListResponse:
    """
    List all active users.

    Returns all active users sorted by name.
    """
    # Ensure user is authenticated
    get_current_user(request)

    db = get_database()
    users = db.list_all_users()

    items = [UserListItem(id=u.id, email=u.email, name=u.name) for u in users]

    return UserListResponse(items=items, total=len(items))
