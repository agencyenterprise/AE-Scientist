"""
Business logic for wallet queries, checkout sessions, and Stripe webhooks.

All amounts are in cents (e.g., 100 = $1.00).
With the new billing model, users pay $X and get $X added to their wallet (1:1 mapping).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

import sentry_sdk
import stripe
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
                sentry_sdk.capture_exception(exc)
                continue

            amount_cents = getattr(price, "unit_amount", None)
            currency = getattr(price, "currency", None)
            nickname = getattr(price, "nickname", None)

            if amount_cents is None:
                logger.warning("Stripe price %s missing unit_amount; skipping.", price_id)
                sentry_sdk.capture_message(
                    f"Stripe price {price_id} missing unit_amount",
                    level="warning",
                )
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
        # Validate that the price_id is in the allowed list
        allowed_price_ids = settings.stripe.price_ids
        if price_id not in allowed_price_ids:
            logger.warning("User %s attempted to use invalid price_id: %s", user.id, price_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid price ID.",
            )

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

        # Get or create Stripe customer
        stripe_customer_id = user.stripe_customer_id
        if not stripe_customer_id:
            customer = await asyncio.to_thread(
                self._stripe().create_customer,
                email=user.email,
                name=user.name,
            )
            stripe_customer_id = customer.id
            await self.db.set_user_stripe_customer_id(user.id, stripe_customer_id)
            logger.debug("Created Stripe customer %s for user %s", stripe_customer_id, user.id)

        session = await asyncio.to_thread(
            self._stripe().create_checkout_session,
            customer=stripe_customer_id,
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
            payment_status = session_object.get("payment_status")
            if payment_status != "paid":
                logger.warning(
                    "Stripe session %s completed but payment_status=%s; skipping fulfillment.",
                    session_id,
                    payment_status,
                )
                return
            await self._complete_checkout_session(session_id)
        elif event_type == "checkout.session.expired":
            session_object = event["data"]["object"]
            session_id = session_object["id"]
            await self.db.update_stripe_checkout_session_status(session_id, "expired")
        elif event_type == "refund.created":
            refund = event["data"]["object"]
            await self._handle_refund_created(refund)
        else:
            # Note: charge.refunded webhook has empty refunds.data, so we use refund.created instead
            logger.debug("Unhandled Stripe event type: %s", event_type)

    async def _complete_checkout_session(self, session_id: str) -> None:
        # Use atomic update with expected_status to prevent race conditions.
        # This ensures only one concurrent webhook call can complete the session.
        updated_session = await self.db.update_stripe_checkout_session_status(
            session_id, "completed", expected_status="created"
        )
        if updated_session is None:
            # Either session doesn't exist or was already completed/expired
            session = await self.db.get_stripe_checkout_session(session_id)
            if session is None:
                logger.warning("Stripe session %s not found; skipping fulfillment.", session_id)
            elif session.status == "completed":
                logger.debug("Stripe session %s already completed; skipping.", session_id)
            else:
                logger.warning(
                    "Stripe session %s has unexpected status %s; skipping.",
                    session_id,
                    session.status,
                )
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

    async def _handle_refund_created(self, refund: Dict[str, Any]) -> None:
        """Handle a refund.created webhook event.

        This is an alternative to charge.refunded that receives the refund object directly.
        """
        refund_id = refund.get("id")
        refund_amount = refund.get("amount", 0)
        charge_id = refund.get("charge")

        logger.info(
            "Processing refund.created: refund_id=%s, amount=%d, charge_id=%s",
            refund_id,
            refund_amount,
            charge_id,
        )

        if not refund_id or refund_amount <= 0:
            logger.warning("Invalid refund data: id=%s, amount=%d", refund_id, refund_amount)
            return

        # Check if we've already processed this refund (idempotency)
        existing = await self.db.get_transaction_by_stripe_refund_id(refund_id)
        if existing is not None:
            logger.debug("Refund %s already processed; skipping.", refund_id)
            return

        # Get the charge to find the payment_intent
        if not charge_id:
            logger.warning("Refund %s has no charge_id; cannot process.", refund_id)
            return

        # Use Stripe API to get the charge and its payment_intent
        try:
            charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
            # payment_intent can be a string ID or a PaymentIntent object
            pi = charge.payment_intent
            payment_intent_id = pi if isinstance(pi, str) else (pi.id if pi else None)
        except Exception as exc:
            logger.warning("Failed to retrieve charge %s: %s", charge_id, exc)
            sentry_sdk.capture_exception(exc)
            sentry_sdk.capture_message(
                f"Refund {refund_id} not processed - failed to retrieve charge {charge_id}. "
                "Customer may have credits but refund not reflected in wallet.",
                level="error",
            )
            return

        if not payment_intent_id:
            logger.warning("Charge %s has no payment_intent; cannot process refund.", charge_id)
            return

        # Look up the checkout session via Stripe API
        stripe_session = await asyncio.to_thread(
            self._stripe().get_checkout_session_by_payment_intent, payment_intent_id
        )
        if stripe_session is None:
            logger.warning(
                "No checkout session found for payment_intent %s; cannot process refund %s.",
                payment_intent_id,
                refund_id,
            )
            return

        # Look up our local record to get the user_id
        our_session = await self.db.get_stripe_checkout_session(stripe_session.id)
        if our_session is None:
            logger.warning(
                "Checkout session %s not found in our database; cannot process refund %s.",
                stripe_session.id,
                refund_id,
            )
            return

        # Create a refund transaction (negative amount to deduct from wallet)
        await self.db.add_completed_transaction(
            user_id=our_session.user_id,
            amount=-refund_amount,
            transaction_type="refund",
            description="Stripe refund",
            metadata={
                "refund_id": refund_id,
                "charge_id": charge_id,
                "payment_intent_id": payment_intent_id,
                "original_session_id": stripe_session.id,
            },
        )
        logger.info(
            "Processed refund %s for user %s: $%.2f deducted.",
            refund_id,
            our_session.user_id,
            refund_amount / 100,
        )
