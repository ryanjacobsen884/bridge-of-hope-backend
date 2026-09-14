"""Seed the database with fake donors/donations/subscriptions/posts and a
test admin account.

Per the build spec (rule 9): never invent organisational facts. Everything
seeded here is either clearly-fake test data (donor names via Faker, all
emails @yopmail.com so nothing goes to a real inbox) or content explicitly
marked as a placeholder/test post -- nothing here claims to be a real fact
about The Bridge of Hope Foundation.

Usage:
    .venv\\Scripts\\python.exe -m scripts.seed
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import AdminUser, Donation, Donor, Post, Subscription
from app.models.base import Base, uuid7
from app.models.donation import DonationStatus
from app.models.subscription import SubscriptionInterval, SubscriptionProvider, SubscriptionStatus
from app.services.admin_auth import hash_password

fake = Faker()
Faker.seed(20260914)
random.seed(20260914)

ADMIN_EMAIL = "bridgeofhope.admin@yopmail.com"
ADMIN_PASSWORD = "TestAdmin#2026"  # test env only; printed at the end, never invented in prod

TEST_DONOR_EMAILS = [
    "amara.donor@yopmail.com",
    "james.donor@yopmail.com",
    "priya.donor@yopmail.com",
    "oliver.donor@yopmail.com",
    "grace.donor@yopmail.com",
    "liam.donor@yopmail.com",
    "sophie.donor@yopmail.com",
    "daniel.donor@yopmail.com",
]

COUNTRIES = ["US", "US", "US", "GB", "GB", "KE"]
CURRENCY_BY_COUNTRY = {"US": "USD", "GB": "GBP", "KE": "KES"}
AMOUNTS_MINOR = {"USD": [1500, 3000, 5000], "GBP": [1200, 2500, 4000], "KES": [200000, 400000, 650000]}


async def reset_schema_if_needed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # no-op if alembic already created everything


async def seed() -> None:
    async with SessionLocal() as db:
        # ---- admin user (TOTP secret generated fresh, printed for the tester) ----
        import pyotp

        existing_admin = await db.scalar(select(AdminUser).where(AdminUser.email == ADMIN_EMAIL))
        totp_secret = existing_admin.totp_secret if existing_admin else pyotp.random_base32()
        if existing_admin is None:
            admin = AdminUser(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                totp_secret=totp_secret,
                is_active=True,
            )
            db.add(admin)
        else:
            existing_admin.password_hash = hash_password(ADMIN_PASSWORD)

        # ---- donors ----
        donors: list[Donor] = []
        for email in TEST_DONOR_EMAILS:
            existing = await db.scalar(select(Donor).where(Donor.email == email))
            if existing:
                donors.append(existing)
                continue
            country = random.choice(COUNTRIES)
            donor = Donor(
                email=email,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                country_code=country,
                marketing_consent=random.choice([True, False]),
                consent_recorded_at=datetime.now(timezone.utc) if random.random() > 0.3 else None,
                consent_source="seed_script",
            )
            db.add(donor)
            donors.append(donor)
        await db.flush()

        # ---- subscriptions + donations ----
        for donor in donors:
            currency = CURRENCY_BY_COUNTRY[donor.country_code]
            amount = random.choice(AMOUNTS_MINOR[currency])
            provider = SubscriptionProvider.test
            status = random.choice(
                [SubscriptionStatus.active, SubscriptionStatus.active, SubscriptionStatus.cancelled]
            )

            existing_sub = await db.scalar(
                select(Subscription).where(Subscription.donor_id == donor.id)
            )
            if existing_sub is None:
                sub = Subscription(
                    donor_id=donor.id,
                    provider=provider,
                    provider_subscription_id=f"seed_sub_{uuid7()}",
                    amount_minor=amount,
                    currency=currency,
                    interval=SubscriptionInterval.monthly,
                    status=status,
                    started_at=datetime.now(timezone.utc) - timedelta(days=random.randint(10, 300)),
                    next_charge_at=datetime.now(timezone.utc) + timedelta(days=random.randint(1, 28))
                    if status == SubscriptionStatus.active else None,
                    cancelled_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
                    if status == SubscriptionStatus.cancelled else None,
                    cover_fees=random.choice([True, False]),
                )
                db.add(sub)
                await db.flush()
            else:
                sub = existing_sub

            # a handful of historical donations per donor
            for i in range(random.randint(1, 4)):
                payment_id = f"seed_pay_{donor.id}_{i}"
                existing_don = await db.scalar(select(Donation).where(Donation.provider_payment_id == payment_id))
                if existing_don:
                    continue
                donation = Donation(
                    donor_id=donor.id,
                    subscription_id=sub.id if random.random() > 0.2 else None,
                    provider=provider,
                    provider_payment_id=payment_id,
                    amount_minor=amount,
                    currency=currency,
                    fee_minor=round(amount * 0.039) + 30,
                    net_minor=amount - (round(amount * 0.039) + 30),
                    status=random.choice([DonationStatus.succeeded, DonationStatus.succeeded, DonationStatus.failed]),
                    is_recurring=sub is not None,
                    completed_at=datetime.now(timezone.utc) - timedelta(days=30 * i),
                    raw_payload={"seed": True},
                )
                db.add(donation)

        # ---- posts ----
        posts = [
            {
                "slug": "welcome-update",
                "title": "[TEST CONTENT] A placeholder update — replace before launch",
                "excerpt": "This post was generated by the seed script for testing. Do not publish as real content.",
                "body_md": "This is placeholder body copy generated for testing the posts list/detail flow. "
                           "Replace with a real, honest update before this site goes live — see CONTENT-TODO.md.",
                "published_at": datetime.now(timezone.utc) - timedelta(days=5),
            },
            {
                "slug": "second-test-update",
                "title": "[TEST CONTENT] Second placeholder update",
                "excerpt": "Another seeded placeholder post, used to test pagination on /updates.",
                "body_md": "Placeholder body text for the second seeded post.",
                "published_at": datetime.now(timezone.utc) - timedelta(days=20),
            },
            {
                "slug": "draft-unpublished",
                "title": "[TEST CONTENT] Draft, unpublished",
                "excerpt": "Unpublished draft used to test that the admin can see drafts but the public API cannot.",
                "body_md": "Draft body.",
                "published_at": None,
            },
        ]
        for p in posts:
            existing_post = await db.scalar(select(Post).where(Post.slug == p["slug"]))
            if existing_post is None:
                db.add(Post(**p))

        await db.commit()

    print("Seed complete.")
    print(f"Admin login:  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"Admin TOTP secret (base32, add to an authenticator app): {totp_secret}")
    print("Test donor emails (all @yopmail.com — check inbox at https://yopmail.com):")
    for e in TEST_DONOR_EMAILS:
        print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(seed())
