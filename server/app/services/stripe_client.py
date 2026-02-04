"""
Lightweight wrapper around the Stripe SDK used by the billing service.
"""

import stripe

from app.config import settings


class StripeClient:
    """Provides typed helpers for the Stripe SDK."""

    def __init__(self) -> None:
        if not settings.stripe.secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
        stripe.api_key = settings.stripe.secret_key

    def retrieve_price(self, price_id: str) -> stripe.Price:
        return stripe.Price.retrieve(price_id)

    def create_checkout_session(
        self,
        *,
        customer_email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
    ) -> stripe.checkout.Session:
        return stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=customer_email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            allow_promotion_codes=True,
        )

    def get_checkout_session_by_payment_intent(
        self, payment_intent_id: str
    ) -> stripe.checkout.Session | None:
        """Retrieve a checkout session by its payment intent ID.

        Args:
            payment_intent_id: The Stripe payment intent ID.

        Returns:
            The checkout session if found, None otherwise.
        """
        sessions = stripe.checkout.Session.list(payment_intent=payment_intent_id, limit=1)
        if sessions.data:
            return sessions.data[0]
        return None
