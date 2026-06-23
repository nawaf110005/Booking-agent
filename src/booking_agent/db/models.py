from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from booking_agent.db.base import Base, utcnow
from booking_agent.db.enums import (
    BookingStatus,
    Category,
    EventStatus,
    HoldStatus,
    MemberTier,
    PaymentStatus,
    SeatStatus,
)

# Money is stored as integer minor units (halalas; 1 SAR = 100 halalas) so all
# arithmetic is exact (Constitution IV). Never store money as float.


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    events: Mapped[list[Event]] = relationship(back_populates="venue")
    layouts: Mapped[list[SeatLayout]] = relationship(back_populates="venue")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_starts_at", "starts_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    detail_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="event_status"),
        default=EventStatus.SCHEDULED,
        nullable=False,
    )

    venue: Mapped[Venue] = relationship(back_populates="events")
    seats: Mapped[list[Seat]] = relationship(back_populates="event")
    bookings: Mapped[list[Booking]] = relationship(back_populates="event")


class SeatLayout(Base):
    """Template grid for a venue section (rows × seats-per-row). Per-event seat
    instances live in `seats`; this records how the grid is shaped for rendering."""

    __tablename__ = "seat_layouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    section: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[Category] = mapped_column(
        SAEnum(Category, name="layout_category"), nullable=False
    )
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_per_row: Mapped[int] = mapped_column(Integer, nullable=False)

    venue: Mapped[Venue] = relationship(back_populates="layouts")


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("event_id", "seat_id", name="uq_seat_event_seatid"),
        Index("ix_seats_event_status", "event_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[str] = mapped_column(String(12), nullable=False)  # e.g. "G12"
    section: Mapped[str] = mapped_column(String(40), nullable=False)
    row: Mapped[str] = mapped_column(String(8), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[Category] = mapped_column(SAEnum(Category, name="seat_category"), nullable=False)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)  # halalas
    status: Mapped[SeatStatus] = mapped_column(
        SAEnum(SeatStatus, name="seat_status"), default=SeatStatus.AVAILABLE, nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="seats")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    tier: Mapped[MemberTier] = mapped_column(SAEnum(MemberTier, name="member_tier"), nullable=False)
    discount_bps: Mapped[int] = mapped_column(Integer, nullable=False)  # basis points
    ticket_cap: Mapped[int] = mapped_column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (Index("ix_bookings_email", "buyer_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    category: Mapped[Category] = mapped_column(SAEnum(Category, name="booking_category"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status"),
        default=BookingStatus.HELD,
        nullable=False,
    )
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vat: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="SAR", nullable=False)
    hold_token: Mapped[str | None] = mapped_column(String(64), index=True)

    event: Mapped[Event] = relationship(back_populates="bookings")
    items: Mapped[list[BookingItem]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(back_populates="booking")
    ticket: Mapped[Ticket | None] = relationship(back_populates="booking", uselist=False)


class BookingItem(Base):
    __tablename__ = "booking_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    seat_id: Mapped[str] = mapped_column(String(12), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vat: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    booking: Mapped[Booking] = relationship(back_populates="items")


class Hold(Base):
    """Atomic seat lock with a TTL (Constitution II). One row per held seat;
    rows sharing a `token` were held together in one all-or-nothing call."""

    __tablename__ = "holds"
    __table_args__ = (
        Index("ix_holds_event_seat", "event_id", "seat_id"),
        Index("ix_holds_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[str] = mapped_column(String(12), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[HoldStatus] = mapped_column(
        SAEnum(HoldStatus, name="hold_status"), default=HoldStatus.ACTIVE, nullable=False
    )
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payment_idempotency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    gateway: Mapped[str] = mapped_column(String(40), nullable=False, default="fake")
    session_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.INITIATED,
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    booking: Mapped[Booking] = relationship(back_populates="payments")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, unique=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    qr_token: Mapped[str | None] = mapped_column(String(512))  # HMAC-signed payload
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped[Booking] = relationship(back_populates="ticket")


class AuditLog(Base):
    """Append-only record of state transitions (Constitution VII)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserPreferences(Base):
    """Per-user preference profile for personalisation."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    preferred_categories: Mapped[str | None] = mapped_column(Text)  # comma-separated
    preferred_venues: Mapped[str | None] = mapped_column(Text)
    rejected_categories: Mapped[str | None] = mapped_column(Text)
    price_band: Mapped[str | None] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(8))  # ar | en | mixed


class InteractionLog(Base):
    """Per-turn conversation log incl. sentiment, for evaluation."""

    __tablename__ = "interaction_log"
    __table_args__ = (Index("ix_interaction_session", "session_id", "turn_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    user_msg: Mapped[str | None] = mapped_column(Text)
    agent_msg: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(40))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    tools_called: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
