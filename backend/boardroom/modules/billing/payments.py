"""Stripe Checkout and the customer portal (FR-9.2). Tests swap in a recorded client, so CI
never calls Stripe."""

import uuid
from typing import Protocol

import stripe
from stripe.params.checkout import SessionCreateParams

from boardroom.config import get_settings


class PaymentsUnavailable(Exception):
    pass


class Payments(Protocol):
    def checkout_url(
        self,
        *,
        tenant_id: uuid.UUID,
        price_id: str,
        customer_id: str | None,
        email: str,
        success_url: str,
        cancel_url: str,
    ) -> str: ...

    def portal_url(self, *, customer_id: str, return_url: str) -> str: ...


class StripePayments:
    def __init__(self, secret_key: str) -> None:
        self._client = stripe.StripeClient(secret_key)

    def checkout_url(
        self,
        *,
        tenant_id: uuid.UUID,
        price_id: str,
        customer_id: str | None,
        email: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        params: SessionCreateParams = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            # The webhook finds the company from these, never from the customer's email.
            "client_reference_id": str(tenant_id),
            "subscription_data": {"metadata": {"tenant_id": str(tenant_id)}},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = email
        session = self._client.v1.checkout.sessions.create(params=params)
        if not session.url:
            raise PaymentsUnavailable("Stripe returned no checkout link.")
        return session.url

    def portal_url(self, *, customer_id: str, return_url: str) -> str:
        session = self._client.v1.billing_portal.sessions.create(
            params={"customer": customer_id, "return_url": return_url}
        )
        return session.url


_override: Payments | None = None


def get_payments() -> Payments:
    if _override is not None:
        return _override
    key = get_settings().stripe_secret_key
    if not key:
        raise PaymentsUnavailable("Payment is not set up yet.")
    return StripePayments(key)


def ready() -> bool:
    return _override is not None or bool(get_settings().stripe_secret_key)


def set_payments(payments: Payments | None) -> None:
    """Tests and local demos only."""
    global _override
    _override = payments
