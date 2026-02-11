"""
Utility helpers to enforce minimum balance requirements and charge users.

All amounts are in cents (e.g., 100 = $1.00).
"""

import logging
from typing import Dict, List, Optional

import sentry_sdk
from fastapi import HTTPException, status

from app.config import settings
from app.services.database import get_database
from app.services.database.llm_token_usages import BaseLlmTokenUsage

logger = logging.getLogger(__name__)


def _calculate_llm_cost_cents(token_usages: List[BaseLlmTokenUsage]) -> int:
    """
    Calculate the total cost in cents for the given token usages.

    Args:
        token_usages: List of token usage records.

    Returns:
        Total cost in cents (minimum 1 cent if any tokens were used).
    """
    total_cents = 0.0
    for tu in token_usages:
        model_key = f"{tu.provider}:{tu.model}"
        uncached_input_tokens = max(tu.input_tokens - tu.cached_input_tokens, 0)

        try:
            input_price_cents_per_million = settings.llm_pricing.get_input_price(model_key)
            cached_input_price_cents_per_million = settings.llm_pricing.get_cached_input_price(
                model_key
            )
            output_price_cents_per_million = settings.llm_pricing.get_output_price(model_key)
        except ValueError as exc:
            # If pricing not found for this model, log to Sentry so we can add it
            logger.warning("LLM pricing not configured for model %s: %s", model_key, exc)
            sentry_sdk.capture_message(
                f"LLM usage not charged - pricing not configured for model {model_key}. "
                f"Tokens used: input={tu.input_tokens}, output={tu.output_tokens}",
                level="error",
            )
            continue

        input_cost_cents = (
            uncached_input_tokens * input_price_cents_per_million
            + tu.cached_input_tokens * cached_input_price_cents_per_million
        ) / 1_000_000
        output_cost_cents = tu.output_tokens * output_price_cents_per_million / 1_000_000

        total_cents += input_cost_cents + output_cost_cents

    # Return at least 1 cent if any tokens were used
    if total_cents > 0:
        return max(1, int(total_cents + 0.5))  # Round to nearest cent
    return 0


async def enforce_minimum_balance(*, user_id: int, required_cents: int, action: str) -> None:
    """
    Ensure the user has at least the required balance (in cents) before starting an operation.

    This is a pre-check before starting expensive operations. It does NOT charge the user.

    Args:
        user_id: The user's ID.
        required_cents: Minimum balance required (in cents).
        action: Description of the action being attempted (for error reporting).

    Raises:
        HTTPException: 402 Payment Required when balance < required_cents.
    """
    if required_cents <= 0:
        return

    db = get_database()
    balance = await db.get_user_wallet_balance(user_id)
    if balance >= required_cents:
        return

    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "message": "Insufficient balance",
            "required_cents": required_cents,
            "available_cents": balance,
            "action": action,
        },
    )


async def charge_cents(
    *,
    user_id: int,
    amount_cents: int,
    action: str,
    description: str,
    metadata: Optional[Dict[str, object]] = None,
) -> None:
    """
    Charge the user's wallet and record the transaction.

    This does NOT check balance - the user's balance can go negative.
    Use enforce_minimum_balance() first if you need a pre-check.

    If the balance goes negative after the charge, all user content
    (research runs and paper reviews) will be locked.

    Args:
        user_id: The user's ID.
        amount_cents: Amount to charge (in cents). Must be positive.
        action: Action type (for metadata).
        description: Human-readable description of the charge.
        metadata: Additional metadata to store with the transaction.
    """
    if amount_cents <= 0:
        return

    db = get_database()
    transaction_metadata = {"action": action, **(metadata or {})}
    await db.add_completed_transaction(
        user_id=user_id,
        amount=-amount_cents,  # Negative for debit
        transaction_type="debit",
        description=description,
        metadata=transaction_metadata,
    )

    # Check if balance went negative and lock active user content if so
    balance = await db.get_user_wallet_balance(user_id)
    if balance <= 0:
        locked_runs = await db.lock_active_research_runs_for_user(user_id)
        locked_reviews = await db.lock_active_paper_reviews_for_user(user_id)
        if locked_runs > 0 or locked_reviews > 0:
            logger.info(
                "User %d balance went negative (%d cents); locked %d active runs and %d active reviews",
                user_id,
                balance,
                locked_runs,
                locked_reviews,
            )


async def charge_for_llm_usage(
    *,
    user_id: int,
    conversation_id: int,
    provider: str,
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    description: str,
    run_id: str | None = None,
) -> int:
    """
    Charge the user for LLM token usage.

    Args:
        user_id: The user's ID.
        conversation_id: The conversation ID.
        provider: LLM provider (e.g., "openai", "anthropic").
        model: Model name (e.g., "gpt-4", "claude-3").
        input_tokens: Number of input tokens.
        cached_input_tokens: Number of cached input tokens.
        output_tokens: Number of output tokens.
        description: Human-readable description of what the tokens were used for.
        run_id: Optional research run ID (used instead of conversation_id for source link).

    Returns:
        The cost in cents that was charged.
    """
    if input_tokens == 0 and output_tokens == 0:
        return 0

    # Create a token usage tuple for cost calculation
    token_usage = BaseLlmTokenUsage(
        conversation_id=conversation_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
    )

    # Calculate cost
    cost_cents = _calculate_llm_cost_cents([token_usage])
    if cost_cents <= 0:
        return 0

    model_key = f"{provider}:{model}"
    # Use run_id as the source link if provided, otherwise use conversation_id
    metadata: dict[str, object] = {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
    }
    if run_id:
        metadata["run_id"] = run_id
    else:
        metadata["conversation_id"] = conversation_id
    await charge_cents(
        user_id=user_id,
        amount_cents=cost_cents,
        action="llm_usage",
        description=f"{description} ({model_key})",
        metadata=metadata,
    )

    logger.debug(
        "Charged %d cents to user %d for LLM usage (model=%s, tokens=%d/%d/%d)",
        cost_cents,
        user_id,
        model_key,
        input_tokens,
        cached_input_tokens,
        output_tokens,
    )

    return cost_cents
