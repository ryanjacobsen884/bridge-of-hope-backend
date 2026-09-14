from __future__ import annotations

from app.config import Settings
from app.payments.base import PaymentProvider, ProviderNotConfigured
from app.payments.btc_provider import BtcProvider
from app.payments.mpesa_provider import MpesaProvider
from app.payments.paypal_provider import PayPalProvider
from app.payments.stripe_provider import StripeProvider
from app.payments.test_provider import TestProvider

_BUILDERS = {
    "test": lambda s: TestProvider(),
    "stripe": StripeProvider,
    "paypal": PayPalProvider,
    "mpesa": MpesaProvider,
    "btc": BtcProvider,
}


def get_provider(name: str, settings: Settings) -> PaymentProvider:
    builder = _BUILDERS.get(name)
    if builder is None:
        raise ProviderNotConfigured(f"Unknown payment provider '{name}'")
    return builder(settings)


def available_providers(settings: Settings) -> list[str]:
    names = []
    if settings.test_provider_enabled:
        names.append("test")
    if settings.stripe_enabled:
        names.append("stripe")
    if settings.paypal_enabled:
        names.append("paypal")
    if settings.mpesa_enabled:
        names.append("mpesa")
    if settings.btc_enabled:
        names.append("btc")
    return names
