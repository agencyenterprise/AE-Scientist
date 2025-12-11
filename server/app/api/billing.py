"""
Billing API endpoints for wallet info, packs, checkout sessions, and Stripe webhooks.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, cast

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
    CreditPackListResponse,
    CreditPackModel,
    CreditTransactionModel,
)
from app.services import get_database
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])

logger = logging.getLogger(__name__)


def _get_service() -> BillingService:
    return BillingService()


@router.get("/wallet", response_model=BillingWalletResponse)
def get_wallet(request: Request, limit: int = 20, offset: int = 0) -> BillingWalletResponse:
    """Return wallet balance plus recent transactions for the authenticated user."""
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offset")

    user = get_current_user(request)
    logger.info("Wallet requested for user_id=%s (limit=%s offset=%s)", user.id, limit, offset)
    service = _get_service()
    wallet, transactions = service.get_wallet(user_id=user.id, limit=limit, offset=offset)
    transaction_models = [
        CreditTransactionModel(
            id=tx.id,
            amount=tx.amount,
            transaction_type=tx.transaction_type,
            status=tx.status,
            description=tx.description,
            metadata=tx.metadata,
            stripe_session_id=tx.stripe_session_id,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]
    return BillingWalletResponse(balance=wallet.balance, transactions=transaction_models)


@router.get("/packs", response_model=CreditPackListResponse)
def list_credit_packs(request: Request) -> CreditPackListResponse:
    """Expose the configured Stripe price IDs and their associated credit amounts."""
    user = get_current_user(request)
    logger.info("Credit packs requested by user_id=%s", user.id)
    service = _get_service()
    packs = [
        CreditPackModel(
            price_id=str(pack["price_id"]),
            credits=int(pack["credits"]),
            currency=str(pack["currency"]),
            unit_amount=int(pack["unit_amount"]),
            nickname=str(pack["nickname"]),
        )
        for pack in service.list_credit_packs()
    ]
    return CreditPackListResponse(packs=packs)


@router.post("/checkout-session", response_model=CheckoutSessionCreateResponse)
def create_checkout_session(
    payload: CheckoutSessionCreateRequest,
    request: Request,
) -> CheckoutSessionCreateResponse:
    """Create a Stripe Checkout session for the requested price ID."""
    user = get_current_user(request)
    logger.info("Creating checkout session for user_id=%s price_id=%s", user.id, payload.price_id)
    service = _get_service()
    checkout_url = service.create_checkout_session(
        user=user,
        price_id=payload.price_id,
        success_url=str(payload.success_url),
        cancel_url=str(payload.cancel_url),
    )
    logger.info(
        "Stripe checkout session created for user_id=%s price_id=%s", user.id, payload.price_id
    )
    return CheckoutSessionCreateResponse(checkout_url=cast(HttpUrl, checkout_url))


@router.get("/wallet/stream")
async def stream_wallet(request: Request) -> StreamingResponse:
    """
    Stream wallet balance updates for the authenticated user.
    Emits a credits event when the balance changes and a heartbeat periodically.
    """
    user = get_current_user(request)
    db = get_database()

    async def event_generator() -> AsyncGenerator[str, None]:
        last_balance: int | None = None
        last_heartbeat = datetime.now(timezone.utc)

        while True:
            if await request.is_disconnected():
                logger.info("Wallet SSE client disconnected for user_id=%s", user.id)
                break

            balance = db.get_user_wallet_balance(user.id)
            if last_balance is None or balance != last_balance:
                payload = {"type": "credits", "data": {"balance": balance}}
                yield f"data: {json.dumps(payload)}\n\n"
                last_balance = balance
                last_heartbeat = datetime.now(timezone.utc)

            now = datetime.now(timezone.utc)
            if (now - last_heartbeat).total_seconds() >= 30:
                yield 'data: {"type":"heartbeat"}\n\n'
                last_heartbeat = now

            await asyncio.sleep(5)

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
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
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
        logger.info("Stripe webhook event received: %s", event["type"])
        service.handle_webhook(event)
    except ValueError as exc:
        logger.warning("Stripe webhook signature invalid: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe webhook handling error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook error"
        ) from exc
    return JSONResponse({"received": True})
