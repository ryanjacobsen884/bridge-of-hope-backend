"""Idempotency: delivering the same webhook event / payment id twice must
produce exactly one row. Runs against the linked Neon branch (test/sandbox
data only, per the build spec)."""
import uuid

import pytest
from sqlalchemy import select

from app.models.donation import Donation
from app.models.donor import Donor
from app.models.webhook_event import WebhookEvent
from app.services import ledger


@pytest.mark.asyncio
async def test_webhook_event_insert_is_idempotent(db_session):
    event_id = f"evt_{uuid.uuid4()}"
    row1, is_new1 = await ledger.record_webhook_event(
        db_session, provider="test", provider_event_id=event_id, event_type="payment.succeeded",
        payload={"a": 1}, signature_valid=True,
    )
    row2, is_new2 = await ledger.record_webhook_event(
        db_session, provider="test", provider_event_id=event_id, event_type="payment.succeeded",
        payload={"a": 1}, signature_valid=True,
    )
    await db_session.commit()

    assert is_new1 is True
    assert is_new2 is False
    assert row1.id == row2.id

    count = await db_session.scalar(
        select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)
    )
    all_rows = list(
        await db_session.scalars(select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id))
    )
    assert len(all_rows) == 1


@pytest.mark.asyncio
async def test_donation_insert_is_idempotent_on_payment_id(db_session):
    donor = Donor(
        email=f"idempotency-test-{uuid.uuid4().hex[:8]}@yopmail.com",
        first_name="Idem", last_name="Potent", country_code="US",
    )
    db_session.add(donor)
    await db_session.flush()

    payment_id = f"pay_{uuid.uuid4()}"
    d1 = await ledger.record_donation(
        db_session, donor_id=donor.id, subscription_id=None, provider="test",
        provider_payment_id=payment_id, amount_minor=1500, currency="USD",
        is_recurring=False, raw_payload={},
    )
    d2 = await ledger.record_donation(
        db_session, donor_id=donor.id, subscription_id=None, provider="test",
        provider_payment_id=payment_id, amount_minor=1500, currency="USD",
        is_recurring=False, raw_payload={},
    )
    await db_session.commit()

    assert d1.id == d2.id
    rows = list(await db_session.scalars(select(Donation).where(Donation.provider_payment_id == payment_id)))
    assert len(rows) == 1
