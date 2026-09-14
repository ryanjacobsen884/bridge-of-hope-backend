"""Email sending, provider-agnostic.

Every template is plain, text-first, and carries a working one-click
unsubscribe/cancel link where relevant. `EMAIL_PROVIDER=console` (the
default until SMTP creds are supplied) logs the rendered email instead of
sending it, so the flow is fully exercisable in test/dev.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger("bridgeofhope.email")

TEMPLATES = {
    "oneoff_receipt": "Thank you for your gift of {amount} to The Bridge of Hope Foundation.\n"
    "Date: {date}\nReference: {reference}\nOrganisation registration no. SCH/2026/001\n\n"
    "Keep this email as your receipt.",
    "monthly_signup": "Thank you for setting up a monthly gift of {amount} to The Bridge of Hope Foundation.\n"
    "You will be charged this amount every month and receive a receipt each time.\n"
    "Cancel any time, in one click, here: {manage_url}",
    "monthly_receipt": "Your monthly gift of {amount} was received today.\nReference: {reference}\n\n"
    "Manage or cancel your monthly gift: {manage_url}",
    "payment_failed": "We could not process your gift of {amount}.\nWhat happened: {reason}\n"
    "You can update your payment details here: {manage_url}",
    "subscription_cancelled": "Your monthly gift has been cancelled, as requested. "
    "No further charges will be made. Thank you for everything you have already given.",
    "newsletter_confirm": "Please confirm you'd like to receive updates from The Bridge of Hope Foundation: {confirm_url}",
}


class EmailService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def render(self, template: str, **context) -> str:
        return TEMPLATES[template].format(**context)

    async def send(self, *, to: str, template: str, subject: str, **context) -> str:
        body = self.render(template, **context)
        message_id = f"local-{datetime.now(timezone.utc).timestamp()}"

        if self._settings.email_provider == "smtp" and self._settings.smtp_host:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self._settings.email_from
            msg["To"] = to
            if self._settings.email_reply_to:
                msg["Reply-To"] = self._settings.email_reply_to
            msg.set_content(body)
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.starttls()
                server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.send_message(msg)
        else:
            log.info("EMAIL (console provider) to=%s subject=%s\n%s", to, subject, body)

        return message_id
