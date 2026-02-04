"""
Business logic for wallet queries, checkout sessions, and Stripe webhooks.

All amounts are in cents (e.g., 100 = $1.00).
With the new billing model, users pay $X and get $X added to their wallet (1:1 mapping).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import HTTPException, status
from stripe import Event

from app.config import settings
from app.services import get_database
from app.services.database.billing import BillingWallet, CreditTransaction
from app.services.database.users import UserData
from app.services.stripe_client import StripeClient

logger = logging.getLogger(__name__)


class BillingService:
    """High-level orchestration for billing flows."""

    def __init__(self) -> None:
        self.db: Any = get_database()
        self._stripe_client: Optional[StripeClient] = None

    def _stripe(self) -> StripeClient:
        if self._stripe_client is None:
            self._stripe_client = StripeClient()
        return self._stripe_client

    # ------------------------------------------------------------------
    # Wallet helpers
    # ------------------------------------------------------------------
    async def get_wallet(
        self,
        *,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        transaction_types: Optional[List[str]] = None,
    ) -> tuple[BillingWallet, List[CreditTransaction], int]:
        """Get user's wallet, transactions, and total transaction count.

        Args:
            user_id: The user's ID.
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip.
            transaction_types: List of transaction types to include.
                If None, returns all transaction types.

        Returns:
            Tuple of (wallet, transactions, total_count)
        """
        wallet = await self.db.get_user_wallet(user_id)
        if wallet is None:
            raise RuntimeError(f"Wallet missing for user {user_id}")
        transactions, total_count = await self.db.list_credit_transactions(
            user_id, limit=limit, offset=offset, transaction_types=transaction_types
        )
        return wallet, transactions, total_count

    async def get_balance(self, user_id: int) -> int:
        """Get user's balance in cents."""
        return cast(int, await self.db.get_user_wallet_balance(user_id))

    # ------------------------------------------------------------------
    # Stripe price / funding options
    # ------------------------------------------------------------------
    async def list_funding_options(self, price_ids: List[str]) -> List[Dict[str, Any]]:
        """List available funding options from Stripe.

        With the new 1:1 model, the Stripe unit_amount equals the amount added to wallet.

        Args:
            price_ids: List of Stripe price IDs to retrieve.

        Returns:
            List of funding options with amount_cents, currency, etc.
        """
        if not price_ids:
            return []

        options: List[Dict[str, Any]] = []
        for price_id in price_ids:
            try:
                price = await asyncio.to_thread(self._stripe().retrieve_price, price_id)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.exception("Failed to retrieve price %s: %s", price_id, exc)
                continue

            amount_cents = getattr(price, "unit_amount", None)
            currency = getattr(price, "currency", None)
            nickname = getattr(price, "nickname", None)

            if amount_cents is None:
                logger.warning("Stripe price %s missing unit_amount; skipping.", price_id)
                continue

            options.append(
                {
                    "price_id": price_id,
                    "amount_cents": int(amount_cents),  # Amount added to wallet (1:1)
                    "currency": currency or "usd",
                    "unit_amount": int(amount_cents),  # Stripe amount
                    "nickname": nickname or f"${int(amount_cents) / 100:.2f}",
                }
            )
        return options

    # Backwards compatibility alias
    async def list_credit_packs(self) -> List[Dict[str, Any]]:
        """Deprecated: Use list_funding_options instead."""
        # For backwards compatibility, try to get price IDs from environment
        # In practice, the caller should provide the price IDs
        return []

    # ------------------------------------------------------------------
    # Checkout sessions
    # ------------------------------------------------------------------
    async def create_checkout_session(
        self,
        *,
        user: UserData,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe checkout session.

        With the new 1:1 model, the Stripe unit_amount is exactly what gets added to wallet.
        No credit mapping needed.
        """
        price = await asyncio.to_thread(self._stripe().retrieve_price, price_id)
        amount_cents = getattr(price, "unit_amount", None)
        currency = getattr(price, "currency", "usd")

        if amount_cents is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe price is missing unit amount.",
            )

        if amount_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid price amount.",
            )

        resolved_success_url = (
            success_url
            or settings.stripe.checkout_success_url
            or (f"{settings.server.frontend_url.rstrip('/')}/billing?success=1")
        )
        resolved_cancel_url = cancel_url or f"{settings.server.frontend_url.rstrip('/')}/billing"

        session = await asyncio.to_thread(
            self._stripe().create_checkout_session,
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

        # Store checkout session - amount_added_cents equals Stripe amount (1:1)
        await self.db.create_stripe_checkout_session_record(
            user_id=user.id,
            stripe_session_id=session.id,
            price_id=price_id,
            amount_added_cents=int(amount_cents),  # 1:1 mapping
            amount_cents=int(amount_cents),
            currency=str(currency),
            metadata={"price_id": price_id},
        )
        return checkout_url

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------
    async def handle_webhook(self, event: Event) -> None:
        event_type = event["type"]

        if event_type == "checkout.session.completed":
            session_object = event["data"]["object"]
            session_id = session_object["id"]
            await self._complete_checkout_session(session_id)
        elif event_type == "checkout.session.expired":
            session_object = event["data"]["object"]
            session_id = session_object["id"]
            await self.db.update_stripe_checkout_session_status(session_id, "expired")
        else:
            logger.debug("Unhandled Stripe event type: %s", event_type)

    async def _complete_checkout_session(self, session_id: str) -> None:
        session = await self.db.get_stripe_checkout_session(session_id)
        if session is None:
            logger.warning("Stripe session %s not found; skipping fulfillment.", session_id)
            return
        if session.status == "completed":
            logger.debug("Stripe session %s already completed; skipping.", session_id)
            return

        updated_session = await self.db.update_stripe_checkout_session_status(
            session_id, "completed"
        )
        if updated_session is None:
            logger.warning("Failed to update Stripe session status for %s", session_id)
            return

        metadata = updated_session.metadata or {}
        metadata["price_id"] = updated_session.price_id
        metadata["currency"] = updated_session.currency

        # Add the amount to user's wallet (1:1 with Stripe amount)
        await self.db.add_completed_transaction(
            user_id=updated_session.user_id,
            amount=updated_session.amount_added_cents,  # Positive for purchase
            transaction_type="purchase",
            description="Stripe wallet funding",
            metadata=metadata,
            stripe_session_id=session_id,
        )
        logger.debug(
            "Fulfilled Stripe session %s for user %s ($%.2f added).",
            session_id,
            updated_session.user_id,
            updated_session.amount_added_cents / 100,
        )
