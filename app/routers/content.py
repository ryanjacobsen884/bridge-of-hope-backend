from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.data_request import DataRequest, DataRequestType
from app.models.donor import Donor
from app.models.post import Post
from app.schemas.content import DataRequestCreate, NewsletterSubscribe, PostDetailOut, PostOut

router = APIRouter(prefix="/api/v1", tags=["content"])


@router.get("/posts", response_model=list[PostOut])
async def list_posts(limit: int = 20, offset: int = 0, db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(Post)
        .where(Post.published_at.is_not(None))
        .order_by(Post.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/posts/{slug}", response_model=PostDetailOut)
async def get_post(slug: str, db: AsyncSession = Depends(get_db)):
    post = await db.scalar(select(Post).where(Post.slug == slug))
    if post is None:
        raise HTTPException(status_code=404, detail="Not found")
    return post


@router.post("/newsletter/subscribe")
async def subscribe(body: NewsletterSubscribe, db: AsyncSession = Depends(get_db)):
    donor = await db.scalar(select(Donor).where(Donor.email == body.email))
    if donor is None:
        donor = Donor(email=body.email, first_name="", last_name="", country_code="")
        db.add(donor)
    donor.marketing_consent = True
    donor.consent_recorded_at = datetime.now(timezone.utc)
    donor.consent_source = "newsletter_double_optin"
    await db.commit()
    return {"status": "subscribed"}


@router.get("/newsletter/unsubscribe/{donor_id}")
async def unsubscribe(donor_id: str, db: AsyncSession = Depends(get_db)):
    donor = await db.get(Donor, donor_id)
    if donor is not None:
        donor.marketing_consent = False
        await db.commit()
    return {"status": "unsubscribed"}


@router.post("/data-requests")
async def create_data_request(body: DataRequestCreate, db: AsyncSession = Depends(get_db)):
    donor = await db.scalar(select(Donor).where(Donor.email == body.email))
    if donor is None:
        raise HTTPException(status_code=404, detail="No donor record found for that email")
    req = DataRequest(
        donor_id=donor.id, type=DataRequestType(body.type), requested_at=datetime.now(timezone.utc), notes=body.notes
    )
    db.add(req)
    await db.commit()
    return {"status": "received"}


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ok"}
