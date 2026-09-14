"""In-house simulated payment rail.

Not a real payment processor. It exists so the full donation/subscription/
webhook/ledger/receipt/cancellation flow can be exercised end-to-end while
no live Stripe/PayPal/M-Pesa/BTC credentials have been supplied. It is
always available regardless of feature flags, but the frontend only offers
it when `TEST_PROVIDER_ENABLED=true` (never in a real `production` deploy
serving real donors).

Behaviour: `create_one_off` and `create_subscription` succeed immediately
(status="succeeded"/"active") -- there is no external round trip, so the
router synthesizes the matching webhook_event itself instead of waiting for
a callback.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from app.payments.base import DonorInput, OneOffResult, SubscriptionResult, WebhookEvent


class TestProvider:
    name = "test"

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult:
        payment_id = f"test_pay_{secrets.token_hex(10)}"
        return OneOffResult(provider_payment_id=payment_id, status="succeeded")

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult:
        sub_id = f"test_sub_{secrets.token_hex(10)}"
        return SubscriptionResult(provider_subscription_id=sub_id, status="active")

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        return None

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        return headers.get("x-test-signature") == "test-signature"

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        data = json.loads(raw_body)
        return WebhookEvent(
            provider_event_id=data["event_id"],
            event_type=data["event_type"],
            payload=data,
            signature_valid=True,
        )

    @staticmethod
    def synthetic_event(*, event_type: str, provider_payment_id: str) -> dict:
        return {
            "event_id": f"test_evt_{secrets.token_hex(10)}",
            "event_type": event_type,
            "provider_payment_id": provider_payment_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
