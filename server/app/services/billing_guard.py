"""
Utility helpers to enforce minimum credit requirements on API actions.
"""

from fastapi import HTTPException, status

from app.services import get_database


def enforce_minimum_credits(*, user_id: int, required: int, action: str) -> None:
    """
    Ensure the user has at least the required credit balance.

    Raises:
        HTTPException: when the user does not meet the threshold.
    """
    if required <= 0:
        return

    db = get_database()
    balance = db.get_user_wallet_balance(user_id)
    if balance >= required:
        return

    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "message": "Insufficient credits",
            "required": required,
            "available": balance,
            "action": action,
        },
    )
