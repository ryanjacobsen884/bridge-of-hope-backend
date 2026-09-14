"""Bitcoin, via a payment processor (never raw wallet/private-key handling).

One-off only, off at launch (BTC_ENABLED=false). Defaults to BTCPay Server
in config. Records sats and fiat value at *confirmation*, not at pledge.
"""
from __future__ import annotations

from app.config import Settings
from app.payments.base import DonorInput, OneOffResult, ProviderNotConfigured, SubscriptionResult, WebhookEvent


class BtcProvider:
    name = "btc"

    def __init__(self, settings: Settings):
        if not settings.btc_enabled or not settings.btc_api_key:
            raise ProviderNotConfigured("Bitcoin is not enabled/configured (BTC_ENABLED, BTC_API_KEY)")
        self._settings = settings

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult:
        raise ProviderNotConfigured("BTC provider needs BTCPay/OpenNode/Coinbase Commerce credentials")

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult:
        raise NotImplementedError("Bitcoin is one-off only per the build spec — no recurring BTC")

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        raise NotImplementedError

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        return False

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        import json

        data = json.loads(raw_body)
        return WebhookEvent(
            provider_event_id=str(data.get("id")), event_type=str(data.get("type")), payload=data, signature_valid=False
        )
