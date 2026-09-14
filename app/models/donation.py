from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid7
from app.models.subscription import SubscriptionProvider


class DonationStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class Donation(Base, TimestampMixin):
    __tablename__ = "donations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True
    )

    provider: Mapped[SubscriptionProvider] = mapped_column(Enum(SubscriptionProvider, name="subscription_provider"), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fee_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    net_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settled_kes_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    status: Mapped[DonationStatus] = mapped_column(
        Enum(DonationStatus, name="donation_status"), nullable=False, default=DonationStatus.pending
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    btc_amount_sats: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
