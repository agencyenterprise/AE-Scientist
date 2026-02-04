"""
Lightweight wrapper around the Stripe SDK used by the billing service.
"""

from typing import Optional

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

    def create_customer(self, *, email: str, name: Optional[str] = None) -> stripe.Customer:
        """Create a new Stripe customer.

        Args:
            email: Customer email address.
            name: Optional customer name.

        Returns:
            The created Stripe Customer object.
        """
        if name:
            return stripe.Customer.create(email=email, name=name)
        return stripe.Customer.create(email=email)

    def create_checkout_session(
        self,
        *,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
        customer: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> stripe.checkout.Session:
        """Create a Stripe Checkout session.

        Args:
            price_id: Stripe price ID.
            success_url: URL to redirect to on success.
            cancel_url: URL to redirect to on cancel.
            metadata: Metadata to attach to the session.
            customer: Optional Stripe customer ID (preferred over customer_email).
            customer_email: Optional customer email (used if customer is not provided).

        Returns:
            The created Stripe Checkout Session.
        """
        params: dict = {
            "mode": "payment",
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "allow_promotion_codes": True,
        }
        if customer:
            params["customer"] = customer
        elif customer_email:
            params["customer_email"] = customer_email
        return stripe.checkout.Session.create(**params)

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
