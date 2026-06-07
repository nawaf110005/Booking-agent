from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.policy import respond
from booking_agent.agent.state import ConversationState
from booking_agent.tools.payments import pay_booking


def _state() -> ConversationState:
    return ConversationState(session_id="test")


def test_full_chat_booking_to_ticket(seeded: Session) -> None:
    st = _state()

    r = respond(seeded, st, "Coldplay in Riyadh")
    assert st.event_id is not None
    assert r["step"] == S.NEED_EMAIL

    r = respond(seeded, st, "nawaf@example.com")
    assert st.email == "nawaf@example.com"
    assert r["step"] == S.CATEGORY_SELECTION
    assert r["member"]["is_member"] is True
    assert r["categories"]

    r = respond(seeded, st, "gold")
    assert r["step"] == S.NEED_QUANTITY

    r = respond(seeded, st, "4")
    assert st.quantity == 4
    assert r["step"] == S.SEAT_SELECTION
    assert r["seatmap_url"] is not None
    assert r["quote"]["total_sar"]

    r = respond(seeded, st, "G3, G4, G5, G6")
    assert r["step"] == S.AWAITING_CONFIRMATION
    assert r["confirmation"]["seats"] == ["G3", "G4", "G5", "G6"]
    assert r["confirmation"]["total_sar"] == "3,128.00 SAR"
    assert st.hold_token is not None

    r = respond(seeded, st, "confirm")
    assert r["step"] == S.PAYMENT
    assert r["payment"]["booking_id"] == st.booking_id

    ticket = pay_booking(seeded, st.booking_id)
    assert ticket["seats"] == ["G3", "G4", "G5", "G6"]
    assert ticket["qr_url"].endswith("/qr.png")


def test_one_shot_message_advances_to_seats(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "4 gold tickets for Coldplay in Riyadh, nawaf@example.com")
    # event + email + category + quantity all extracted in one turn -> seat map.
    assert st.event_id is not None
    assert st.email == "nawaf@example.com"
    assert st.category == "gold"
    assert st.quantity == 4
    assert r["step"] == S.SEAT_SELECTION


def test_cap_enforced_for_guest(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "guest@example.com")  # non-member, cap 4
    respond(seeded, st, "gold")
    r = respond(seeded, st, "6")
    assert r["step"] == S.NEED_QUANTITY
    assert "up to" in r["reply"].lower()
    assert st.quantity is None


def test_event_disambiguation_then_city(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "Coldplay")  # two cities
    assert r["step"] == S.EVENT_SELECTION
    assert r["events"] is not None and len(r["events"]) == 2
    r = respond(seeded, st, "Riyadh")    # disambiguate by city
    assert st.event_id is not None
    assert r["step"] == S.NEED_EMAIL


def test_cancel_releases_hold(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    respond(seeded, st, "gold")
    respond(seeded, st, "2")
    respond(seeded, st, "G7, G8")
    assert st.hold_token is not None
    r = respond(seeded, st, "cancel")
    assert st.hold_token is None
    assert r["step"] == S.SEAT_SELECTION


def test_whats_on_this_weekend_filters(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "What's on this weekend?")
    assert r["step"] == S.EVENT_SELECTION
    assert r["events"] is not None
    titles = [e["title"] for e in r["events"]]
    # Only the seeded weekend event — NOT the whole catalog.
    assert "Riyadh Comedy Night" in titles
    assert "Coldplay — Music of the Spheres" not in titles
    assert st.event_id is None  # discovery shows cards, doesn't auto-select


def test_faq_question_answered_without_derailing(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "is there a discount?")
    assert "%" in r["reply"] or "member" in r["reply"].lower()
    assert st.event_id is None  # asking a question doesn't start a booking


def test_meta_question_about_project(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "who built you?")
    assert "nawaf" in r["reply"].lower() or "booking-agent" in r["reply"].lower()


def test_question_midflow_keeps_state(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    r = respond(seeded, st, "is there a discount?")  # ask mid-flow
    assert st.email == "nawaf@example.com"  # not derailed
    assert st.event_id is not None
    assert "%" in r["reply"] or "member" in r["reply"].lower()


def test_question_and_completion_at_payment_step(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    respond(seeded, st, "gold")
    respond(seeded, st, "4")
    respond(seeded, st, "G3, G4, G5, G6")
    assert respond(seeded, st, "confirm")["step"] == S.PAYMENT
    booking_id = st.booking_id

    # A question at the payment step is answered — not the canned "pay now".
    r = respond(seeded, st, "can you tell me about this event?")
    assert "pay now" not in r["reply"].lower()
    assert "coldplay" in r["reply"].lower()

    # Once paid (separate endpoint), the agent stops asking to pay.
    pay_booking(seeded, booking_id)
    r = respond(seeded, st, "ok")
    assert st.step == S.CONFIRMED
    assert "pay now" not in r["reply"].lower()

    # The user can then start a fresh booking.
    respond(seeded, st, "book the Riyadh derby")
    assert st.booking_id is None
    assert st.event_id is not None
