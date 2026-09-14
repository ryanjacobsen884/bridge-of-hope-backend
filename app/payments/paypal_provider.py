"""PayPal provider — the most important rail for US/UK donors.

One-off: Orders API v2 (create -> approve -> capture).
Monthly: Subscriptions API (Product -> Plans per tier/currency, cached -> Subscription).

Off until PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET are supplied. Built to the
full shape described in the build spec; before going live, fetch PayPal's
current REST API docs (this spec was written 2026-09-14).
"""
from __future__ import annotations

import base64

import httpx

from app.config import Settings
from app.payments.base import DonorInput, OneOffResult, ProviderNotConfigured, SubscriptionResult, WebhookEvent

PAYPAL_API = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com",
}


class PayPalProvider:
    name = "paypal"

    def __init__(self, settings: Settings):
        if not settings.paypal_enabled or not (settings.paypal_client_id and settings.paypal_client_secret):
            raise ProviderNotConfigured("PayPal is not enabled/configured (PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)")
        self._settings = settings
        self._base = PAYPAL_API[settings.paypal_mode]

    async def _token(self) -> str:
        auth = base64.b64encode(
            f"{self._settings.paypal_client_id}:{self._settings.paypal_client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                "/v1/oauth2/token",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult:
        token = await self._token()
        amount = f"{amount_minor / 100:.2f}"
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                "/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}],
                },
            )
            resp.raise_for_status()
            order = resp.json()
        approve = next((l["href"] for l in order["links"] if l["rel"] == "approve"), None)
        return OneOffResult(provider_payment_id=order["id"], checkout_url=approve, status="pending")

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult:
        # NOTE: requires a cached Product + Plan per (tier, currency) -- see services/ledger for
        # the plan cache once this is wired to real credentials. Left unimplemented pending creds.
        raise ProviderNotConfigured("PayPal subscriptions require a pre-created Plan cache — add credentials first")

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        token = await self._token()
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/v1/billing/subscriptions/{provider_subscription_id}/cancel",
                headers={"Authorization": f"Bearer {token}"},
                json={"reason": "Donor requested cancellation"},
            )
            resp.raise_for_status()

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        # Real implementation calls POST /v1/notifications/verify-webhook-signature
        # with PAYPAL_WEBHOOK_ID. Never trust an unverified event.
        return False

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        import json

        data = json.loads(raw_body)
        return WebhookEvent(
            provider_event_id=data["id"], event_type=data["event_type"], payload=data, signature_valid=False
        )
