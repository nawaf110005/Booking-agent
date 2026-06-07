from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.db.models import Payment, Ticket
from booking_agent.fulfilment.qr import make_qr_png, sign_qr_token, verify_qr_token
from booking_agent.tools.booking import create_booking_from_hold
from booking_agent.tools.holds import place_seat_hold
from booking_agent.tools.payments import pay_booking

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_qr_token_signs_and_verifies() -> None:
    token = sign_qr_token(7, ["G3", "G4"])
    assert verify_qr_token(token)


def test_qr_token_tamper_is_rejected() -> None:
    token = sign_qr_token(7, ["G3", "G4"])
    parts = token.split("|")
    parts[0] = "999"  # forge a different booking id
    assert not verify_qr_token("|".join(parts))


def test_qr_png_is_png() -> None:
    assert make_qr_png(sign_qr_token(1, ["A1"]))[:8] == _PNG_MAGIC


def test_booking_creation_and_idempotent_payment(coldplay_riyadh_id: int, seeded: Session) -> None:
    hold = place_seat_hold(seeded, coldplay_riyadh_id, ["A2", "B2"], "x@a.com")
    booking = create_booking_from_hold(
        seeded,
        email="x@a.com",
        event_id=coldplay_riyadh_id,
        category="vip",
        quantity=2,
        seat_ids=["A2", "B2"],
        hold_token=hold.token,
        tier=None,
    )
    assert booking.total > 0

    pay_booking(seeded, booking.id)
    pay_booking(seeded, booking.id)  # duplicate → must stay exactly one

    assert seeded.query(Ticket).filter_by(booking_id=booking.id).count() == 1
    assert seeded.query(Payment).filter_by(booking_id=booking.id).count() == 1
