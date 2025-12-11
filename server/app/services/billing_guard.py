"""
Utility helpers to enforce minimum credit requirements on API actions.
"""

from typing import Dict

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


def charge_user_credits(
    *,
    user_id: int,
    cost: int,
    action: str,
    description: str,
    metadata: Dict[str, object],
) -> None:
    """
    Deduct credits from the user's wallet and record the transaction.

    Raises:
        HTTPException: when the user does not have enough credits.
    """
    if cost <= 0:
        return

    db = get_database()
    balance = db.get_user_wallet_balance(user_id)
    if balance < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Insufficient credits",
                "required": cost,
                "available": balance,
                "action": action,
            },
        )

    transaction_metadata = {"action": action, **metadata}
    db.add_completed_transaction(
        user_id=user_id,
        amount=-cost,
        transaction_type="debit",
        description=description,
        metadata=transaction_metadata,
    )
