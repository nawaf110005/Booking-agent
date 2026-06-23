"""Payment + ticket issuance.

The app ships a **virtual (fake)** gateway that completes the booking offline (no
real charge) so the chat demo finishes end to end. It is idempotent — paying the
same booking twice yields exactly one paid booking and one ticket (Constitution V).
A real provider (signature-verified webhook) is a possible future swap.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.db.base import utcnow
from booking_agent.db.enums import BookingStatus, HoldStatus, PaymentStatus, SeatStatus
from booking_agent.db.models import AuditLog, Booking, Hold, Payment, Seat, Ticket
from booking_agent.fulfilment.qr import sign_qr_token
from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.money import sar_str


def _ticket_payload(db: Session, booking: Booking) -> dict:
    seat_ids = [item.seat_id for item in booking.items]
    return {
        "booking_id": booking.id,
        "event_title": booking.event.title,
        "seats": seat_ids,
        "total_sar": sar_str(booking.total, booking.currency),
        "email": booking.buyer_email,
        "qr_url": f"/v1/tickets/{booking.id}/qr.png",
    }


def pay_booking(db: Session, booking_id: int) -> dict:
    """Complete payment (fake gateway) and issue a ticket. Idempotent."""

    booking = db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError(f"booking {booking_id} not found")

    existing_ticket = db.query(Ticket).filter(Ticket.booking_id == booking_id).first()
    if booking.status == BookingStatus.PAID and existing_ticket is not None:
        return _ticket_payload(db, booking)  # idempotent replay

    idem = f"fake-{booking_id}"
    if db.query(Payment).filter(Payment.idempotency_key == idem).first() is None:
        db.add(
            Payment(
                booking_id=booking_id,
                gateway="fake",
                session_id=f"sess_fake_{booking_id}",
                status=PaymentStatus.PAID,
                amount=booking.total,
                idempotency_key=idem,
                signature_verified=True,
            )
        )

    booking.status = BookingStatus.PAID
    seat_ids = [item.seat_id for item in booking.items]
    for sid in seat_ids:
        seat = db.query(Seat).filter(
            Seat.event_id == booking.event_id, Seat.seat_id == sid
        ).first()
        if seat is not None:
            seat.status = SeatStatus.SOLD
    for hold in db.query(Hold).filter(
        Hold.booking_id == booking_id, Hold.status == HoldStatus.ACTIVE
    ):
        hold.status = HoldStatus.CONVERTED

    if existing_ticket is None:
        db.add(
            Ticket(
                booking_id=booking_id,
                qr_token=sign_qr_token(booking_id, seat_ids),
                issued_at=utcnow(),
            )
        )

    db.add(
        AuditLog(
            entity_type="booking",
            entity_id=str(booking_id),
            action="paid",
            detail=f"total={booking.total}",
        )
    )
    db.flush()
    return _ticket_payload(db, booking)


def get_ticket_token(db: Session, booking_id: int) -> str | None:
    ticket = db.query(Ticket).filter(Ticket.booking_id == booking_id).first()
    return ticket.qr_token if ticket else None
