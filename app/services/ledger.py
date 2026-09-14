"""The ledger service: the only place that writes donations/subscriptions
rows in response to a confirmed payment event. Idempotent on
`provider_payment_id` / `provider_event_id`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donation import Donation, DonationStatus
from app.models.donor import Donor
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.webhook_event import WebhookEvent as WebhookEventRow
from app.models.webhook_event import WebhookEventStatus


async def record_webhook_event(
    db: AsyncSession,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload: dict,
    signature_valid: bool,
) -> tuple[WebhookEventRow, bool]:
    """Insert the raw event before processing it. Returns (row, is_new).

    If provider_event_id already exists, is_new=False — this is a retry;
    the caller must return 200 immediately and do nothing else.
    """
    existing = await db.scalar(select(WebhookEventRow).where(WebhookEventRow.provider_event_id == provider_event_id))
    if existing is not None:
        return existing, False

    row = WebhookEventRow(
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload=payload,
        signature_valid=signature_valid,
        received_at=datetime.now(timezone.utc),
        status=WebhookEventStatus.received,
    )
    db.add(row)
    await db.flush()
    return row, True


async def mark_event_processed(db: AsyncSession, event: WebhookEventRow, *, error: str | None = None) -> None:
    event.processed_at = datetime.now(timezone.utc)
    event.status = WebhookEventStatus.failed if error else WebhookEventStatus.processed
    event.error = error
    event.attempts += 1
    await db.flush()


async def record_donation(
    db: AsyncSession,
    *,
    donor_id: uuid.UUID,
    subscription_id: uuid.UUID | None,
    provider: str,
    provider_payment_id: str,
    amount_minor: int,
    currency: str,
    is_recurring: bool,
    raw_payload: dict,
) -> Donation:
    """Idempotent on provider_payment_id — this is the idempotency key."""
    existing = await db.scalar(select(Donation).where(Donation.provider_payment_id == provider_payment_id))
    if existing is not None:
        return existing

    donation = Donation(
        donor_id=donor_id,
        subscription_id=subscription_id,
        provider=provider,
        provider_payment_id=provider_payment_id,
        amount_minor=amount_minor,
        currency=currency,
        status=DonationStatus.succeeded,
        is_recurring=is_recurring,
        completed_at=datetime.now(timezone.utc),
        raw_payload=raw_payload,
    )
    db.add(donation)
    await db.flush()
    return donation


async def activate_subscription(db: AsyncSession, subscription: Subscription) -> None:
    subscription.status = SubscriptionStatus.active
    subscription.started_at = subscription.started_at or datetime.now(timezone.utc)
    await db.flush()


async def cancel_subscription_row(db: AsyncSession, subscription: Subscription, *, reason: str | None) -> None:
    subscription.status = SubscriptionStatus.cancelled
    subscription.cancelled_at = datetime.now(timezone.utc)
    subscription.cancellation_reason = reason
    await db.flush()
