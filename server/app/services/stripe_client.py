"""
Lightweight wrapper around the Stripe SDK used by the billing service.
"""

import stripe

from app.config import settings


class StripeClient:
    """Provides typed helpers for the Stripe SDK."""

    def __init__(self) -> None:
        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

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
