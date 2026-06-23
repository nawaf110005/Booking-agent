from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def ensure_aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on read; re-attach UTC so comparisons are safe."""

    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Shared declarative base.

    Every concrete model picks up `created_at`/`updated_at` automatically.
    Append-only tables (audit_log, interaction_log) only ever insert.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
