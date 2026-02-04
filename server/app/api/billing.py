"""
Billing API endpoints for wallet info, funding options, checkout sessions, and Stripe webhooks.

All amounts are in cents (e.g., 100 = $1.00).
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, cast

import stripe
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import HttpUrl

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import (
    BillingWalletResponse,
    CheckoutSessionCreateRequest,
    CheckoutSessionCreateResponse,
    CreditTransactionModel,
    FundingOptionListResponse,
    FundingOptionModel,
    WalletStreamEvent,
)
from app.services import get_database
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])

logger = logging.getLogger(__name__)


def _get_service() -> BillingService:
    return BillingService()


@router.get("/wallet", response_model=BillingWalletResponse)
async def get_wallet(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    transaction_types: Optional[str] = None,
) -> BillingWalletResponse:
    """Return wallet balance (in cents) plus recent transactions for the authenticated user.

    Args:
        limit: Maximum number of transactions to return (1-100).
        offset: Number of transactions to skip.
        transaction_types: Comma-separated list of transaction types to include.
            Valid types: purchase, debit, refund, adjustment, hold, hold_reversal.
            If not specified, returns all transaction types.
    """
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset")

    # Parse transaction types filter
    types_filter: Optional[list[str]] = None
    if transaction_types:
        types_filter = [t.strip() for t in transaction_types.split(",") if t.strip()]

    user = get_current_user(request)
    logger.debug(
        "Wallet requested for user_id=%s (limit=%s offset=%s types=%s)",
        user.id,
        limit,
        offset,
        types_filter,
    )
    service = _get_service()
    wallet, transactions, total_count = await service.get_wallet(
        user_id=user.id, limit=limit, offset=offset, transaction_types=types_filter
    )
    transaction_models = [
        CreditTransactionModel(
            id=tx.id,
            amount_cents=tx.amount,
            transaction_type=tx.transaction_type,
            status=tx.status,
            description=tx.description,
            metadata=tx.metadata,
            stripe_session_id=tx.stripe_session_id,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]
    return BillingWalletResponse(
        balance_cents=wallet.balance, transactions=transaction_models, total_count=total_count
    )


@router.get("/packs", response_model=FundingOptionListResponse)
async def list_funding_options(request: Request) -> FundingOptionListResponse:
    """List available funding options (Stripe prices).

    With the new 1:1 model, paying $X adds $X to the wallet.
    """
    user = get_current_user(request)
    logger.debug("Funding options requested by user_id=%s", user.id)
    service = _get_service()

    options = [
        FundingOptionModel(
            price_id=str(opt["price_id"]),
            amount_cents=int(opt["amount_cents"]),
            currency=str(opt["currency"]),
            unit_amount=int(opt["unit_amount"]),
            nickname=str(opt["nickname"]),
        )
        for opt in await service.list_funding_options(list(settings.stripe.price_ids))
    ]
    return FundingOptionListResponse(options=options)


@router.post("/checkout-session", response_model=CheckoutSessionCreateResponse)
async def create_checkout_session(
    payload: CheckoutSessionCreateRequest,
    request: Request,
) -> CheckoutSessionCreateResponse:
    """Create a Stripe Checkout session for the requested price ID.

    With the new 1:1 model, the Stripe amount equals the wallet credit amount.
    """
    user = get_current_user(request)
    logger.debug("Creating checkout session for user_id=%s price_id=%s", user.id, payload.price_id)
    service = _get_service()
    checkout_url = await service.create_checkout_session(
        user=user,
        price_id=payload.price_id,
        success_url=str(payload.success_url),
        cancel_url=str(payload.cancel_url),
    )
    logger.debug(
        "Stripe checkout session created for user_id=%s price_id=%s", user.id, payload.price_id
    )
    return CheckoutSessionCreateResponse(checkout_url=cast(HttpUrl, checkout_url))


@router.get(
    "/wallet/stream",
    response_model=WalletStreamEvent,
    responses={
        200: {
            "description": "Wallet balance updates (in cents) and heartbeats",
            "content": {
                "text/event-stream": {"schema": {"$ref": "#/components/schemas/WalletStreamEvent"}}
            },
        }
    },
)
async def stream_wallet(request: Request) -> StreamingResponse:
    """
    Stream wallet balance updates for the authenticated user.
    Uses PostgreSQL LISTEN/NOTIFY for efficient real-time updates.
    Emits a balance event (in cents) when the balance changes and a heartbeat periodically.
    """
    user = get_current_user(request)
    db = get_database()

    async def event_generator() -> AsyncGenerator[str, None]:
        last_balance: int | None = None

        # Send initial balance
        balance = await db.get_user_wallet_balance(user.id)
        payload = {"type": "balance", "data": {"balance_cents": balance}}
        yield f"data: {json.dumps(payload)}\n\n"
        last_balance = balance

        # Get a dedicated connection for LISTEN
        async with db.aget_connection() as conn:
            try:
                await conn.execute("LISTEN wallet_balance_changed")

                while True:
                    if await request.is_disconnected():
                        logger.debug("Wallet SSE client disconnected for user_id=%s", user.id)
                        break

                    # Wait for notification with timeout for heartbeat
                    try:
                        notify = await asyncio.wait_for(
                            conn.notifies().__anext__(),
                            timeout=30.0,
                        )
                        # Parse notification payload: "user_id:balance"
                        parts = notify.payload.split(":", 1)
                        if len(parts) == 2:
                            notified_user_id, new_balance_str = parts
                            if int(notified_user_id) == user.id:
                                new_balance = int(new_balance_str)
                                if new_balance != last_balance:
                                    payload = {
                                        "type": "balance",
                                        "data": {"balance_cents": new_balance},
                                    }
                                    yield f"data: {json.dumps(payload)}\n\n"
                                    last_balance = new_balance
                    except asyncio.TimeoutError:
                        # Send heartbeat on timeout
                        yield 'data: {"type":"heartbeat"}\n\n'
                    except StopAsyncIteration:
                        # Connection closed
                        break
            except asyncio.CancelledError:
                # Client disconnected - clean up gracefully
                logger.debug("Wallet SSE cancelled for user_id=%s", user.id)
            finally:
                # Ensure UNLISTEN before connection returns to pool
                try:
                    await conn.execute("UNLISTEN wallet_balance_changed")
                except Exception:
                    pass  # Connection may already be closed

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/stripe-webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> JSONResponse:
    """Handle Stripe webhook events."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    service = _get_service()
    webhook_secret = settings.stripe.webhook_secret
    if not webhook_secret:
        logger.error("Stripe webhook secret is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret is not configured.",
        )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
        event_type = event["type"]
        event_id = event.get("id", "unknown")
        logger.info("Stripe webhook received: type=%s, event_id=%s", event_type, event_id)
        await service.handle_webhook(event)
        logger.info(
            "Stripe webhook processed successfully: type=%s, event_id=%s", event_type, event_id
        )
    except ValueError as exc:
        logger.warning("Stripe webhook payload invalid (JSON decode error): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload"
        ) from exc
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe webhook handling error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing error"
        ) from exc
    return JSONResponse({"received": True})
