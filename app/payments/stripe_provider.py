"""Stripe provider.

Off at launch (STRIPE_ENABLED=false) -- Stripe does not currently support
businesses registered in Kenya. Built so the switch is a config change once
a US/UK partner entity exists. Uses Stripe Checkout: subscription mode for
monthly, payment mode for one-off.

Before wiring this up for real: fetch Stripe's current API docs, this spec
was written 2026-09-14 and Checkout/webhook shapes do change.
"""
from __future__ import annotations

from app.config import Settings
from app.payments.base import DonorInput, OneOffResult, ProviderNotConfigured, SubscriptionResult, WebhookEvent


class StripeProvider:
    name = "stripe"

    def __init__(self, settings: Settings):
        if not settings.stripe_enabled or not settings.stripe_secret_key:
            raise ProviderNotConfigured("Stripe is not enabled/configured (STRIPE_ENABLED, STRIPE_SECRET_KEY)")
        self._settings = settings
        # import stripe here (not at module scope) so the app can boot without the
        # provider ever being selected when the flag is off
        import stripe

        stripe.api_key = settings.stripe_secret_key
        self._stripe = stripe

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult:
        session = self._stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price_data": {"currency": currency.lower(), "unit_amount": amount_minor,
                                         "product_data": {"name": "One-off gift — Bridge of Hope"}}, "quantity": 1}],
            customer_email=donor.email,
            success_url=f"{self._settings.frontend_url}/give/thank-you?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{self._settings.frontend_url}/give",
        )
        return OneOffResult(provider_payment_id=session.id, checkout_url=session.url, status="pending")

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult:
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price_data": {"currency": currency.lower(), "unit_amount": amount_minor,
                                         "recurring": {"interval": "month"},
                                         "product_data": {"name": "Monthly gift — Bridge of Hope"}}, "quantity": 1}],
            customer_email=donor.email,
            success_url=f"{self._settings.frontend_url}/give/thank-you?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{self._settings.frontend_url}/give",
        )
        return SubscriptionResult(provider_subscription_id=session.id, checkout_url=session.url, status="pending")

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        self._stripe.Subscription.delete(provider_subscription_id)

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        try:
            self._stripe.Webhook.construct_event(
                raw_body, headers.get("stripe-signature", ""), self._settings.stripe_webhook_secret
            )
            return True
        except Exception:
            return False

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        import json

        data = json.loads(raw_body)
        return WebhookEvent(
            provider_event_id=data["id"], event_type=data["type"], payload=data, signature_valid=True
        )
