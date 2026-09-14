from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models.admin_user import AdminUser
from app.models.data_request import DataRequest
from app.models.donation import Donation, DonationStatus
from app.models.donor import Donor
from app.models.post import Post
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.admin_auth import issue_session, login_rate_limiter, verify_password, verify_session, verify_totp

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

SESSION_COOKIE = "boh_admin_session"


class LoginBody(BaseModel):
    email: str
    password: str
    totp_code: str


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    boh_admin_session: str | None = Cookie(default=None),
) -> AdminUser:
    if not boh_admin_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    admin_id = verify_session(settings.secret_key, boh_admin_session)
    if admin_id is None:
        raise HTTPException(status_code=401, detail="Session expired")
    admin = await db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return admin


@router.post("/login")
async def login(body: LoginBody, response: Response, request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.check(f"{client_ip}:{body.email.lower()}"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    admin = await db.scalar(select(AdminUser).where(AdminUser.email == body.email))
    if admin is None or not admin.is_active or not verify_password(admin.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not admin.totp_secret or not verify_totp(admin.totp_secret, body.totp_code):
        raise HTTPException(status_code=401, detail="Invalid authentication code")

    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = issue_session(settings.secret_key, admin.id)
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax",
        secure=settings.environment != "development", max_age=60 * 60 * 8,
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@router.get("/me")
async def me(admin: AdminUser = Depends(require_admin)):
    return {"email": admin.email, "last_login_at": admin.last_login_at}


@router.get("/donors")
async def list_donors(db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    donors = await db.scalars(select(Donor).order_by(Donor.created_at.desc()).limit(200))
    return [
        {"id": str(d.id), "email": d.email, "first_name": d.first_name, "last_name": d.last_name,
         "country_code": d.country_code, "marketing_consent": d.marketing_consent, "created_at": d.created_at}
        for d in donors
    ]


@router.get("/donations")
async def list_donations(
    status: str | None = None, format: str | None = None,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin),
):
    query = select(Donation).order_by(Donation.created_at.desc()).limit(1000)
    if status:
        query = query.where(Donation.status == DonationStatus(status))
    rows = list(await db.scalars(query))

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "donor_id", "provider", "amount_minor", "currency", "status", "is_recurring", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.donor_id, r.provider.value, r.amount_minor, r.currency, r.status.value, r.is_recurring, r.created_at])
        return Response(content=buf.getvalue(), media_type="text/csv",
                         headers={"Content-Disposition": "attachment; filename=donations.csv"})

    return [
        {"id": str(r.id), "donor_id": str(r.donor_id), "provider": r.provider.value, "amount_minor": r.amount_minor,
         "currency": r.currency, "status": r.status.value, "is_recurring": r.is_recurring, "created_at": r.created_at}
        for r in rows
    ]


@router.get("/subscriptions")
async def list_subscriptions(
    status: str | None = None, db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)
):
    query = select(Subscription).order_by(Subscription.created_at.desc()).limit(500)
    if status:
        query = query.where(Subscription.status == SubscriptionStatus(status))
    rows = await db.scalars(query)
    return [
        {"id": str(s.id), "donor_id": str(s.donor_id), "provider": s.provider.value, "amount_minor": s.amount_minor,
         "currency": s.currency, "status": s.status.value, "next_charge_at": s.next_charge_at}
        for s in rows
    ]


@router.get("/failed-payments")
async def failed_payments(db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    rows = await db.scalars(
        select(Donation).where(Donation.status == DonationStatus.failed).order_by(Donation.created_at.desc())
    )
    return [{"id": str(r.id), "donor_id": str(r.donor_id), "provider": r.provider.value, "amount_minor": r.amount_minor,
             "currency": r.currency, "created_at": r.created_at} for r in rows]


@router.get("/data-requests")
async def data_requests(db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    rows = await db.scalars(select(DataRequest).order_by(DataRequest.requested_at.desc()))
    return [{"id": str(r.id), "donor_id": str(r.donor_id), "type": r.type.value, "requested_at": r.requested_at,
             "fulfilled_at": r.fulfilled_at, "notes": r.notes} for r in rows]


class PostBody(BaseModel):
    slug: str
    title: str
    body_md: str
    excerpt: str
    cover_image_url: str | None = None
    published: bool = False


@router.get("/posts")
async def admin_list_posts(db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    rows = await db.scalars(select(Post).order_by(Post.created_at.desc()))
    return [{"id": str(p.id), "slug": p.slug, "title": p.title, "published_at": p.published_at} for p in rows]


@router.post("/posts")
async def admin_create_post(body: PostBody, db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    post = Post(
        slug=body.slug, title=body.title, body_md=body.body_md, excerpt=body.excerpt,
        cover_image_url=body.cover_image_url,
        published_at=datetime.now(timezone.utc) if body.published else None,
    )
    db.add(post)
    await db.commit()
    return {"id": str(post.id)}


@router.put("/posts/{post_id}")
async def admin_update_post(post_id: str, body: PostBody, db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Not found")
    post.slug, post.title, post.body_md, post.excerpt, post.cover_image_url = (
        body.slug, body.title, body.body_md, body.excerpt, body.cover_image_url
    )
    if body.published and post.published_at is None:
        post.published_at = datetime.now(timezone.utc)
    elif not body.published:
        post.published_at = None
    await db.commit()
    return {"status": "updated"}


@router.delete("/posts/{post_id}")
async def admin_delete_post(post_id: str, db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(post)
    await db.commit()
    return {"status": "deleted"}
