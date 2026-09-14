from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models.donor import Donor
from app.models.subscription import Subscription, SubscriptionProvider, SubscriptionStatus
from app.payments.base import DonorInput, ProviderNotConfigured
from app.payments.registry import get_provider
from app.payments.test_provider import TestProvider
from app.schemas.donation import OneOffCreate, OneOffResponse, SubscriptionCreate, SubscriptionResponse
from app.services import ledger
from app.services.email import EmailService
from app.services.tokens import issue_manage_token

router = APIRouter(prefix="/api/v1", tags=["donations"])


async def _get_or_create_donor(db: AsyncSession, payload) -> Donor:
    donor = await db.scalar(select(Donor).where(Donor.email == payload.email))
    if donor is None:
        donor = Donor(
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            country_code=payload.country_code.upper(),
        )
        db.add(donor)
        await db.flush()
    return donor


@router.post("/donations/one-off", response_model=OneOffResponse)
async def create_one_off(
    body: OneOffCreate,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        provider = get_provider(body.provider, settings)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    donor = await _get_or_create_donor(db, body.donor)
    if body.consent:
        donor.marketing_consent = True
        donor.consent_recorded_at = datetime.now(timezone.utc)
        donor.consent_source = "give_form_oneoff"

    donor_input = DonorInput(
        email=body.donor.email, first_name=body.donor.first_name, last_name=body.donor.last_name,
        country_code=body.donor.country_code, phone=body.donor.phone,
    )
    result = await provider.create_one_off(
        amount_minor=body.amount_minor, currency=body.currency, cover_fees=body.cover_fees,
        donor=donor_input, consent=body.consent,
    )

    if isinstance(provider, TestProvider):
        # No external round trip — record the webhook + donation synchronously,
        # exactly as the real webhook handler would once the callback arrives.
        event_payload = TestProvider.synthetic_event(
            event_type="payment.succeeded", provider_payment_id=result.provider_payment_id
        )
        event_row, is_new = await ledger.record_webhook_event(
            db, provider="test", provider_event_id=event_payload["event_id"],
            event_type=event_payload["event_type"], payload=event_payload, signature_valid=True,
        )
        if is_new:
            await ledger.record_donation(
                db, donor_id=donor.id, subscription_id=None, provider="test",
                provider_payment_id=result.provider_payment_id, amount_minor=body.amount_minor,
                currency=body.currency, is_recurring=False, raw_payload=event_payload,
            )
            await ledger.mark_event_processed(db, event_row)
            email = EmailService(settings)
            await email.send(
                to=donor.email, template="oneoff_receipt", subject="Your gift to The Bridge of Hope Foundation",
                amount=f"{body.currency} {body.amount_minor / 100:.2f}",
                date=datetime.now(timezone.utc).date().isoformat(),
                reference=result.provider_payment_id,
            )

    await db.commit()
    return OneOffResponse(
        checkout_url=result.checkout_url, client_secret=result.client_secret,
        mpesa_request_id=result.mpesa_request_id, provider_payment_id=result.provider_payment_id,
        status=result.status,
    )


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    body: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        provider = get_provider(body.provider, settings)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    donor = await _get_or_create_donor(db, body.donor)
    if body.consent:
        donor.marketing_consent = True
        donor.consent_recorded_at = datetime.now(timezone.utc)
        donor.consent_source = "give_form_monthly"

    donor_input = DonorInput(
        email=body.donor.email, first_name=body.donor.first_name, last_name=body.donor.last_name,
        country_code=body.donor.country_code, phone=body.donor.phone,
    )
    result = await provider.create_subscription(
        amount_minor=body.amount_minor, currency=body.currency, cover_fees=body.cover_fees,
        donor=donor_input, consent=body.consent,
    )

    subscription = Subscription(
        donor_id=donor.id,
        provider=SubscriptionProvider(body.provider),
        provider_subscription_id=result.provider_subscription_id,
        amount_minor=body.amount_minor,
        currency=body.currency,
        cover_fees=body.cover_fees,
        status=SubscriptionStatus.pending,
    )
    db.add(subscription)
    await db.flush()

    if isinstance(provider, TestProvider):
        await ledger.activate_subscription(db, subscription)
        event_payload = TestProvider.synthetic_event(
            event_type="subscription.activated", provider_payment_id=result.provider_subscription_id
        )
        event_row, is_new = await ledger.record_webhook_event(
            db, provider="test", provider_event_id=event_payload["event_id"],
            event_type=event_payload["event_type"], payload=event_payload, signature_valid=True,
        )
        if is_new:
            first_payment_id = f"{result.provider_subscription_id}_initial"
            await ledger.record_donation(
                db, donor_id=donor.id, subscription_id=subscription.id, provider="test",
                provider_payment_id=first_payment_id, amount_minor=body.amount_minor,
                currency=body.currency, is_recurring=True, raw_payload=event_payload,
            )
            await ledger.mark_event_processed(db, event_row)
            manage_token = issue_manage_token(settings.secret_key, donor.id)
            email = EmailService(settings)
            await email.send(
                to=donor.email, template="monthly_signup", subject="Your monthly gift is set up",
                amount=f"{body.currency} {body.amount_minor / 100:.2f}",
                manage_url=f"{settings.frontend_url}/manage/{manage_token}",
            )

    await db.commit()
    return SubscriptionResponse(
        checkout_url=result.checkout_url, approval_url=result.approval_url,
        ratiba_request_id=result.ratiba_request_id, provider_subscription_id=result.provider_subscription_id,
        status=result.status,
    )
