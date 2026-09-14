from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid7


class SubscriptionProvider(str, enum.Enum):
    stripe = "stripe"
    paypal = "paypal"
    mpesa_ratiba = "mpesa_ratiba"
    test = "test"


class SubscriptionInterval(str, enum.Enum):
    monthly = "monthly"


class SubscriptionStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    failed = "failed"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False, index=True)

    provider: Mapped[SubscriptionProvider] = mapped_column(Enum(SubscriptionProvider, name="subscription_provider"), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)

    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    interval: Mapped[SubscriptionInterval] = mapped_column(
        Enum(SubscriptionInterval, name="subscription_interval"), nullable=False, default=SubscriptionInterval.monthly
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"), nullable=False, default=SubscriptionStatus.pending, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cover_fees: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("provider", "provider_subscription_id", name="uq_subscriptions_provider_subid"),
    )
