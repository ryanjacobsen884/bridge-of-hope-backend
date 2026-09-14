"""M-Pesa via Safaricom Daraja. KES only.

One-off: STK Push (Lipa na M-Pesa Online) -- the initiating response only
acknowledges the request; the real result arrives async at the callback URL.
Monthly: M-Pesa Ratiba standing orders.

Off until MPESA_* credentials are supplied. Before wiring up for real,
fetch Safaricom's current Daraja docs (this spec was written 2026-09-14).
"""
from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings
from app.payments.base import DonorInput, OneOffResult, ProviderNotConfigured, SubscriptionResult, WebhookEvent

EAT = timezone(timedelta(hours=3))

DARAJA_HOST = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


def normalize_phone(raw: str) -> str:
    """Accept 07..., +2547..., 2547..., 01... -> normalise to 2547.../2541...

    Raises ValueError on anything else, with a clear message.
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("254") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10 and digits[1] in "17":
        return "254" + digits[1:]
    if digits.startswith("7") and len(digits) == 9:
        return "254" + digits
    if digits.startswith("1") and len(digits) == 9:
        return "254" + digits
    raise ValueError(
        f"Could not recognise '{raw}' as a Kenyan phone number. Use 07XXXXXXXX, 01XXXXXXXX, +2547XXXXXXXX or 2547XXXXXXXX."
    )


class MpesaProvider:
    name = "mpesa"

    def __init__(self, settings: Settings):
        if not settings.mpesa_enabled or not (
            settings.mpesa_consumer_key and settings.mpesa_consumer_secret
            and settings.mpesa_shortcode and settings.mpesa_passkey
        ):
            raise ProviderNotConfigured("M-Pesa is not enabled/configured (MPESA_* env vars)")
        self._settings = settings
        self._host = DARAJA_HOST[settings.mpesa_environment]
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_token(self) -> str:
        if self._token and self._token_expires_at and datetime.now(timezone.utc) < self._token_expires_at:
            return self._token
        auth = base64.b64encode(
            f"{self._settings.mpesa_consumer_key}:{self._settings.mpesa_consumer_secret}".encode()
        ).decode()
        async with httpx.AsyncClient(base_url=self._host) as client:
            resp = await client.get(
                "/oauth/v1/generate", params={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {auth}"},
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3599)) - 60)
        return self._token

    def _stk_password(self, timestamp: str) -> str:
        raw = f"{self._settings.mpesa_shortcode}{self._settings.mpesa_passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode()

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult:
        if currency != "KES":
            raise ValueError("M-Pesa only accepts KES")
        if not donor.phone:
            raise ValueError("A phone number is required for M-Pesa")
        phone = normalize_phone(donor.phone)
        timestamp = datetime.now(EAT).strftime("%Y%m%d%H%M%S")  # EAT, not UTC
        token = await self._get_token()
        async with httpx.AsyncClient(base_url=self._host) as client:
            resp = await client.post(
                "/mpesa/stkpush/v1/processrequest",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "BusinessShortCode": self._settings.mpesa_shortcode,
                    "Password": self._stk_password(timestamp),
                    "Timestamp": timestamp,
                    "TransactionType": "CustomerPayBillOnline",
                    "Amount": round(amount_minor / 100),
                    "PartyA": phone,
                    "PartyB": self._settings.mpesa_shortcode,
                    "PhoneNumber": phone,
                    "CallBackURL": self._settings.mpesa_callback_url,
                    "AccountReference": "BridgeOfHope",
                    "TransactionDesc": "Donation",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return OneOffResult(
            provider_payment_id=data["CheckoutRequestID"],
            mpesa_request_id=data["CheckoutRequestID"],
            status="pending",
        )

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult:
        raise ProviderNotConfigured("M-Pesa Ratiba standing orders need production Daraja credentials")

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        raise ProviderNotConfigured("M-Pesa Ratiba cancellation needs production Daraja credentials")

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        # Real implementation allowlists Safaricom's published callback IP ranges
        # and treats the body as untrusted regardless.
        return False

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        import json

        data = json.loads(raw_body)
        body = data.get("Body", {}).get("stkCallback", {})
        return WebhookEvent(
            provider_event_id=str(body.get("CheckoutRequestID")),
            event_type="stk_callback",
            payload=data,
            signature_valid=False,
        )
