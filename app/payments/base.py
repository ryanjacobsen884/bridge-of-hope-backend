"""Payment provider protocol.

Routers must not contain provider-specific branching beyond selecting the
implementation via `get_provider()`. Every rail — including the in-house
`test` rail used while no live payment credentials are configured —
implements this same shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider is selected but its feature flag is off / creds are missing."""


@dataclass
class OneOffResult:
    provider_payment_id: str
    checkout_url: str | None = None
    client_secret: str | None = None
    mpesa_request_id: str | None = None
    status: str = "pending"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriptionResult:
    provider_subscription_id: str
    checkout_url: str | None = None
    approval_url: str | None = None
    ratiba_request_id: str | None = None
    status: str = "pending"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DonorInput:
    email: str
    first_name: str
    last_name: str
    country_code: str
    phone: str | None = None


@dataclass
class WebhookEvent:
    provider_event_id: str
    event_type: str
    payload: dict[str, Any]
    signature_valid: bool


class PaymentProvider(Protocol):
    name: str

    async def create_one_off(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> OneOffResult: ...

    async def create_subscription(
        self, *, amount_minor: int, currency: str, cover_fees: bool, donor: DonorInput, consent: bool
    ) -> SubscriptionResult: ...

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None: ...

    def verify_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> bool:
        """Verify the provider signature against the exact raw bytes."""
        ...

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent: ...
