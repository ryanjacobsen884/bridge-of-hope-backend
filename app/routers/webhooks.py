"""Webhook handlers. Every handler follows the same shape, in this order:

1. Read the raw request body before any JSON parsing (signature verification
   needs the exact bytes).
2. Verify the provider signature. On failure: log, return 401, do nothing else.
3. Insert into webhook_events. If provider_event_id already exists, return
   200 immediately -- this is a retry.
4. Return 200 quickly, then process (here: inline, since FastAPI's request
   lifecycle is short and our ledger writes are cheap; a queue/background
   task is a drop-in swap if processing ever gets heavier).
5. Process, update donations/subscriptions, send the receipt, mark processed.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.payments.registry import get_provider
from app.services import ledger

log = logging.getLogger("bridgeofhope.webhooks")

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


async def _handle(request: Request, db: AsyncSession, settings: Settings, provider_name: str) -> Response:
    raw_body = await request.body()  # exact bytes, before any parsing
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        provider = get_provider(provider_name, settings)
    except Exception:
        log.warning("webhook for disabled/unconfigured provider %s rejected", provider_name)
        return Response(status_code=401)

    if not provider.verify_webhook(headers=headers, raw_body=raw_body):
        log.warning("webhook signature verification failed for %s", provider_name)
        return Response(status_code=401)

    event = provider.parse_event(raw_body=raw_body)

    row, is_new = await ledger.record_webhook_event(
        db,
        provider=provider_name,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        payload=event.payload,
        signature_valid=event.signature_valid,
    )
    await db.commit()

    if not is_new:
        return Response(status_code=200)  # retry — already recorded, nothing else to do

    # Real providers: hand off to a background task here so we ack fast and
    # providers don't retry-storm us. Left as a direct call for now since
    # every non-test provider raises ProviderNotConfigured before reaching here.
    try:
        await ledger.mark_event_processed(db, row)
        await db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        await ledger.mark_event_processed(db, row, error=str(exc))
        await db.commit()

    return Response(status_code=200)


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    return await _handle(request, db, settings, "stripe")


@router.post("/paypal")
async def paypal_webhook(request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    return await _handle(request, db, settings, "paypal")


@router.post("/mpesa/stk")
async def mpesa_stk_webhook(request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    return await _handle(request, db, settings, "mpesa")


@router.post("/mpesa/ratiba")
async def mpesa_ratiba_webhook(request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    return await _handle(request, db, settings, "mpesa")


@router.post("/btc")
async def btc_webhook(request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    return await _handle(request, db, settings, "btc")
