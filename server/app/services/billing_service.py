"""
Business logic for wallet queries, checkout sessions, and Stripe webhooks.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from stripe import Event

from app.config import settings
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.billing import BillingWallet, CreditTransaction
from app.services.database.users import UserData
from app.services.stripe_client import StripeClient

logger = logging.getLogger(__name__)


class BillingService:
    """High-level orchestration for billing flows."""

    def __init__(self) -> None:
        self.db: DatabaseManager = get_database()
        self._stripe_client: Optional[StripeClient] = None

    def _stripe(self) -> StripeClient:
        if self._stripe_client is None:
            self._stripe_client = StripeClient()
        return self._stripe_client

    # ------------------------------------------------------------------
    # Wallet helpers
    # ------------------------------------------------------------------
    def get_wallet(
        self, *, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[BillingWallet, List[CreditTransaction]]:
        self.db.ensure_user_wallet(user_id)
        wallet = self.db.get_user_wallet(user_id)
        if wallet is None:
            raise RuntimeError(f"Wallet missing for user {user_id}")
        transactions = self.db.list_credit_transactions(user_id, limit=limit, offset=offset)
        return wallet, transactions

    def get_balance(self, user_id: int) -> int:
        self.db.ensure_user_wallet(user_id)
        return self.db.get_user_wallet_balance(user_id)

    # ------------------------------------------------------------------
    # Stripe price / pack helpers
    # ------------------------------------------------------------------
    def list_credit_packs(self) -> List[Dict[str, Any]]:
        price_map = settings.STRIPE_PRICE_TO_CREDITS
        logger.info("Price map: %s", price_map)
        if not price_map:
            return []

        packs: List[Dict[str, Any]] = []
        for price_id, credits in price_map.items():
            try:
                price = self._stripe().retrieve_price(price_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to retrieve price %s: %s", price_id, exc)
                continue
            amount_cents = getattr(price, "unit_amount", None)
            currency = getattr(price, "currency", None)
            nickname = getattr(price, "nickname", None)
            if amount_cents is None:
                logger.warning("Stripe price %s missing unit_amount; skipping pack.", price_id)
                continue
            packs.append(
                {
                    "price_id": price_id,
                    "credits": credits,
                    "currency": currency or "usd",
                    "unit_amount": int(amount_cents),
                    "nickname": nickname or price_id,
                }
            )
        # Preserve declaration order in env
        return packs

    # ------------------------------------------------------------------
    # Checkout sessions
    # ------------------------------------------------------------------
    def create_checkout_session(
        self,
        *,
        user: UserData,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        price_map = settings.STRIPE_PRICE_TO_CREDITS
        if price_id not in price_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown price_id. Please refresh available packs.",
            )
        credits = price_map[price_id]
        if credits <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Credit pack misconfigured."
            )

        price = self._stripe().retrieve_price(price_id)
        amount_cents = getattr(price, "unit_amount", None)
        currency = getattr(price, "currency", "usd")
        if amount_cents is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe price is missing unit amount.",
            )

        resolved_success_url = (
            success_url
            or settings.STRIPE_CHECKOUT_SUCCESS_URL
            or (f"{settings.FRONTEND_URL.rstrip('/')}/billing?success=1")
        )
        resolved_cancel_url = cancel_url or f"{settings.FRONTEND_URL.rstrip('/')}/billing"

        session = self._stripe().create_checkout_session(
            customer_email=user.email,
            price_id=price_id,
            success_url=resolved_success_url,
            cancel_url=resolved_cancel_url,
            metadata={"user_id": str(user.id)},
        )
        checkout_url = session.url
        if not checkout_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe did not return a checkout URL.",
            )
        self.db.create_stripe_checkout_session_record(
            user_id=user.id,
            stripe_session_id=session.id,
            price_id=price_id,
            credits=credits,
            amount_cents=int(amount_cents),
            currency=str(currency),
            metadata={"price_id": price_id},
        )
        return checkout_url

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------
    def handle_webhook(self, event: Event) -> None:
        event_type = event["type"]

        if event_type == "checkout.session.completed":
            session_object = event["data"]["object"]
            session_id = session_object["id"]
            self._complete_checkout_session(session_id)
        elif event_type == "checkout.session.expired":
            session_object = event["data"]["object"]
            session_id = session_object["id"]
            self.db.update_stripe_checkout_session_status(session_id, "expired")
        else:
            logger.debug("Unhandled Stripe event type: %s", event_type)

    def _complete_checkout_session(self, session_id: str) -> None:
        session = self.db.get_stripe_checkout_session(session_id)
        if session is None:
            logger.warning("Stripe session %s not found; skipping fulfillment.", session_id)
            return
        if session.status == "completed":
            logger.info("Stripe session %s already completed; skipping.", session_id)
            return

        updated_session = self.db.update_stripe_checkout_session_status(session_id, "completed")
        if updated_session is None:
            logger.warning("Failed to update Stripe session status for %s", session_id)
            return

        metadata = updated_session.metadata or {}
        metadata["price_id"] = updated_session.price_id
        metadata["currency"] = updated_session.currency

        self.db.add_completed_transaction(
            user_id=updated_session.user_id,
            amount=updated_session.credits,
            transaction_type="purchase",
            description="Stripe credit purchase",
            metadata=metadata,
            stripe_session_id=session_id,
        )
        logger.info(
            "Fulfilled Stripe session %s for user %s (%s credits).",
            session_id,
            updated_session.user_id,
            updated_session.credits,
        )
