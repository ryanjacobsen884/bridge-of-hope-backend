"""Donor self-service — the manage/cancel page. No login: the signed token
in the link IS the credential. Cancellation must work in one click."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models.donor import Donor
from app.models.subscription import Subscription, SubscriptionStatus
from app.payments.registry import get_provider
from app.schemas.donation import ManageSubscriptionOut, ManageSubscriptionPatch
from app.services import ledger
from app.services.email import EmailService
from app.services.tokens import verify_manage_token

router = APIRouter(prefix="/api/v1/subscriptions/manage", tags=["subscriptions"])


async def _donor_subscriptions(db: AsyncSession, token: str, secret_key: str) -> list[Subscription]:
    donor_id = verify_manage_token(secret_key, token)
    if donor_id is None:
        raise HTTPException(status_code=404, detail="This link has expired or is invalid.")
    result = await db.scalars(
        select(Subscription).where(Subscription.donor_id == donor_id, Subscription.status != SubscriptionStatus.cancelled)
    )
    return list(result)


@router.get("/{token}", response_model=list[ManageSubscriptionOut])
async def get_subscriptions(token: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    subs = await _donor_subscriptions(db, token, settings.secret_key)
    return [
        ManageSubscriptionOut(
            id=str(s.id), amount_minor=s.amount_minor, currency=s.currency, status=s.status.value,
            next_charge_at=s.next_charge_at.isoformat() if s.next_charge_at else None, provider=s.provider.value,
        )
        for s in subs
    ]


@router.patch("/{token}")
async def change_amount(
    token: str, body: ManageSubscriptionPatch, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
):
    subs = await _donor_subscriptions(db, token, settings.secret_key)
    if not subs:
        raise HTTPException(status_code=404, detail="No active monthly gift found.")
    subs[0].amount_minor = body.amount_minor
    await db.commit()
    return {"status": "updated"}


@router.delete("/{token}")
async def cancel(token: str, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    """One click. No retention flow, no guilt, no phone number required."""
    subs = await _donor_subscriptions(db, token, settings.secret_key)
    if not subs:
        raise HTTPException(status_code=404, detail="No active monthly gift found.")

    sub = subs[0]
    try:
        provider = get_provider(sub.provider.value, settings)
        await provider.cancel_subscription(provider_subscription_id=sub.provider_subscription_id)
    except Exception:
        pass  # cancellation on our side proceeds regardless; provider sync is best-effort here

    await ledger.cancel_subscription_row(db, sub, reason="donor requested cancellation via manage page")

    donor_result = await db.get(Donor, sub.donor_id)
    if donor_result is not None:
        email = EmailService(settings)
        await email.send(
            to=donor_result.email, template="subscription_cancelled", subject="Your monthly gift has been cancelled"
        )

    await db.commit()
    return {"status": "cancelled"}
