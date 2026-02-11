"""
Admin API endpoints for user credit management.

Provides endpoints for admins to:
- View all users with their wallet balances
- Add credit to existing users
- Create pending credits for unregistered emails
- View pending credits
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.middleware.admin import require_admin
from app.services.database import get_database

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# Request/Response Models


class UserWithBalanceModel(BaseModel):
    """User with wallet balance."""

    id: int
    email: str
    name: str
    is_active: bool
    balance_cents: int
    created_at: str


class UserListWithBalancesResponse(BaseModel):
    """Response for listing users with balances."""

    users: list[UserWithBalanceModel]
    total_count: int


class AddCreditRequest(BaseModel):
    """Request to add credit to a user."""

    user_id: int = Field(..., description="User ID to add credit to")
    amount_cents: int = Field(..., gt=0, description="Amount in cents (must be positive)")
    description: str = Field(
        ..., min_length=1, max_length=500, description="Description of the credit"
    )


class AddCreditResponse(BaseModel):
    """Response after adding credit."""

    success: bool
    message: str


class CreatePendingCreditRequest(BaseModel):
    """Request to create a pending credit for an unregistered email."""

    email: EmailStr = Field(..., description="Email address to grant credit to")
    amount_cents: int = Field(..., gt=0, description="Amount in cents (must be positive)")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")


class PendingCreditModel(BaseModel):
    """Pending credit record."""

    id: int
    email: str
    amount_cents: int
    description: Optional[str]
    granted_by_email: str
    claimed_by_user_id: Optional[int]
    claimed_at: Optional[str]
    created_at: str


class PendingCreditsListResponse(BaseModel):
    """Response for listing pending credits."""

    pending_credits: list[PendingCreditModel]
    total_count: int


# Endpoints


@router.get("/users", response_model=UserListWithBalancesResponse)
async def list_users_with_balances(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
) -> UserListWithBalancesResponse:
    """
    List all active users with their wallet balances.

    Admin only endpoint.
    """
    require_admin(request)

    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit (1-500)")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset")

    db = get_database()
    users, total_count = await db.list_active_users_with_balances(
        limit=limit,
        offset=offset,
        search=search,
    )

    return UserListWithBalancesResponse(
        users=[
            UserWithBalanceModel(
                id=u.id,
                email=u.email,
                name=u.name,
                is_active=u.is_active,
                balance_cents=u.balance_cents,
                created_at=u.created_at.isoformat(),
            )
            for u in users
        ],
        total_count=total_count,
    )


@router.post("/credits/add", response_model=AddCreditResponse)
async def add_credit_to_user(
    request: Request,
    payload: AddCreditRequest,
) -> AddCreditResponse:
    """
    Add credit to an existing user's wallet.

    Admin only endpoint.
    """
    admin_user = require_admin(request)

    db = get_database()

    # Verify user exists
    target_user = await db.get_user_by_id(payload.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not active")

    await db.admin_add_credit_to_user(
        user_id=payload.user_id,
        amount_cents=payload.amount_cents,
        description=payload.description,
        granted_by_user_id=admin_user.id,
    )

    logger.info(
        "Admin %s added %d cents to user %s (%s)",
        admin_user.email,
        payload.amount_cents,
        target_user.email,
        payload.description,
    )

    return AddCreditResponse(
        success=True,
        message=f"Added ${payload.amount_cents / 100:.2f} to {target_user.email}",
    )


@router.post("/credits/pending", response_model=PendingCreditModel)
async def create_pending_credit(
    request: Request,
    payload: CreatePendingCreditRequest,
) -> PendingCreditModel:
    """
    Create a pending credit for an email that hasn't registered yet.

    The credit will be automatically applied when the user registers.
    Admin only endpoint.
    """
    admin_user = require_admin(request)

    db = get_database()

    # Check if email already has a registered user
    existing_user = await db.get_user_by_email(str(payload.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {payload.email} already exists. "
            "Use the regular add credit endpoint instead.",
        )

    pending_credit = await db.create_pending_credit(
        email=str(payload.email),
        amount_cents=payload.amount_cents,
        description=payload.description,
        granted_by_user_id=admin_user.id,
    )

    logger.info(
        "Admin %s created pending credit of %d cents for %s",
        admin_user.email,
        payload.amount_cents,
        payload.email,
    )

    return PendingCreditModel(
        id=pending_credit.id,
        email=pending_credit.email,
        amount_cents=pending_credit.amount_cents,
        description=pending_credit.description,
        granted_by_email=pending_credit.granted_by_email,
        claimed_by_user_id=pending_credit.claimed_by_user_id,
        claimed_at=pending_credit.claimed_at.isoformat() if pending_credit.claimed_at else None,
        created_at=pending_credit.created_at.isoformat(),
    )


@router.get("/credits/pending", response_model=PendingCreditsListResponse)
async def list_pending_credits(
    request: Request,
    include_claimed: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> PendingCreditsListResponse:
    """
    List pending credits.

    Admin only endpoint.
    """
    require_admin(request)

    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit (1-500)")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset")

    db = get_database()
    pending_credits, total_count = await db.list_pending_credits(
        include_claimed=include_claimed,
        limit=limit,
        offset=offset,
    )

    return PendingCreditsListResponse(
        pending_credits=[
            PendingCreditModel(
                id=pc.id,
                email=pc.email,
                amount_cents=pc.amount_cents,
                description=pc.description,
                granted_by_email=pc.granted_by_email,
                claimed_by_user_id=pc.claimed_by_user_id,
                claimed_at=pc.claimed_at.isoformat() if pc.claimed_at else None,
                created_at=pc.created_at.isoformat(),
            )
            for pc in pending_credits
        ],
        total_count=total_count,
    )
