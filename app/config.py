"""Application configuration.

Fails loudly on boot if a variable required by an *enabled* feature flag is
missing. A silent misconfiguration in a payment system is worse than a crash.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---------- Core ----------
    environment: str = "development"
    secret_key: str
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    allowed_origins: str = "http://localhost:3000"

    # ---------- Database ----------
    database_url: str
    direct_database_url: str

    # ---------- Feature flags ----------
    test_provider_enabled: bool = True
    stripe_enabled: bool = False
    paypal_enabled: bool = False
    mpesa_enabled: bool = False
    btc_enabled: bool = False

    # ---------- Stripe ----------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ---------- PayPal ----------
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_mode: str = "sandbox"

    # ---------- M-Pesa ----------
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_passkey: str = ""
    mpesa_environment: str = "sandbox"
    mpesa_callback_url: str = ""
    mpesa_ratiba_callback_url: str = ""

    # ---------- Bitcoin ----------
    btc_provider: str = "btcpay"
    btc_api_key: str = ""
    btc_store_id: str = ""
    btc_webhook_secret: str = ""
    btc_min_confirmations: int = 2

    # ---------- Email ----------
    email_provider: str = "console"
    email_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "The Bridge of Hope Foundation <giving@example.org>"
    email_reply_to: str = ""

    # ---------- Admin ----------
    admin_email: str = ""
    admin_password_hash: str = ""

    # ---------- Ops ----------
    sentry_dsn: str = ""
    log_level: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_feature_flags(self) -> "Settings":
        missing: list[str] = []

        if self.stripe_enabled and not self.stripe_secret_key:
            missing.append("STRIPE_SECRET_KEY is required when STRIPE_ENABLED=true")
        if self.paypal_enabled and not (self.paypal_client_id and self.paypal_client_secret):
            missing.append("PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET required when PAYPAL_ENABLED=true")
        if self.mpesa_enabled and not (
            self.mpesa_consumer_key and self.mpesa_consumer_secret and self.mpesa_shortcode and self.mpesa_passkey
        ):
            missing.append("MPESA_* credentials required when MPESA_ENABLED=true")
        if self.btc_enabled and not self.btc_api_key:
            missing.append("BTC_API_KEY required when BTC_ENABLED=true")
        if self.email_provider == "smtp" and not (self.smtp_host and self.smtp_user and self.smtp_password):
            missing.append("SMTP_HOST/SMTP_USER/SMTP_PASSWORD required when EMAIL_PROVIDER=smtp")

        if missing:
            raise ValueError(
                "Refusing to boot due to incomplete configuration:\n- " + "\n- ".join(missing)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
