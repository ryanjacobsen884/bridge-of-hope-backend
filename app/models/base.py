from __future__ import annotations

import os
import time
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uuid7() -> uuid.UUID:
    """Generate a UUIDv7 (time-ordered) without an extra dependency.

    48-bit unix-ms timestamp + 74 bits of randomness, per draft RFC 9562.
    Time-ordered primary keys keep Postgres b-tree inserts sequential,
    which matters for the high-write donations/webhook_events tables.
    """
    unix_ms = int(time.time() * 1000)
    rand = os.urandom(10)
    b = unix_ms.to_bytes(6, "big") + rand
    b = bytearray(b)
    b[6] = (b[6] & 0x0F) | 0x70  # version 7
    b[8] = (b[8] & 0x3F) | 0x80  # variant 10
    return uuid.UUID(bytes=bytes(b))


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
