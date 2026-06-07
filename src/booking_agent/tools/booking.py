"""Create a booking from a confirmed seat hold (post-HITL, pre-payment)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.config import settings
from booking_agent.db.enums import BookingStatus, Category, HoldStatus, MemberTier
from booking_agent.db.models import AuditLog, Booking, BookingItem, Hold
from booking_agent.tools.money import pct_bps
from booking_agent.tools.pricing import compute_quote


def create_booking_from_hold(
    db: Session,
    *,
    email: str,
    event_id: int,
    category: Category | str,
    quantity: int,
    seat_ids: list[str],
    hold_token: str,
    tier: MemberTier | None = None,
) -> Booking:
    """Persist a booking (status pending_payment) and link its active holds.

    Money is taken from a freshly-computed quote (authoritative), so totals are
    never trusted from the caller. Called only after the HITL confirmation gate.
    """

    quote = compute_quote(db, event_id, category, quantity, tier)
    cat = category if isinstance(category, Category) else Category(str(category).lower())

    booking = Booking(
        buyer_email=email,
        event_id=event_id,
        category=cat,
        quantity=quantity,
        status=BookingStatus.PENDING_PAYMENT,
        subtotal=quote.subtotal,
        discount_total=quote.discount_total,
        vat=quote.vat,
        total=quote.total,
        currency=quote.currency,
        hold_token=hold_token,
    )
    db.add(booking)
    db.flush()

    per_seat_vat = pct_bps(quote.net_unit_price, settings.vat_bps)
    for sid in seat_ids:
        db.add(
            BookingItem(
                booking_id=booking.id,
                seat_id=sid,
                unit_price=quote.net_unit_price,
                discount_applied=quote.unit_discount,
                vat=per_seat_vat,
            )
        )

    for hold in db.query(Hold).filter(
        Hold.token == hold_token, Hold.status == HoldStatus.ACTIVE
    ):
        hold.booking_id = booking.id

    db.add(
        AuditLog(
            entity_type="booking",
            entity_id=str(booking.id),
            action="created",
            detail=f"{quantity}x {cat.value} seats={','.join(seat_ids)} total={quote.total}",
        )
    )
    db.flush()
    return booking
