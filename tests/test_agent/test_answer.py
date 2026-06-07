from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent.answer import answer_question


def test_discount_question(seeded: Session) -> None:
    a = answer_question(seeded, "is there a discount?").lower()
    assert "%" in a or "member" in a or "discount" in a


def test_who_built_question(seeded: Session) -> None:
    a = answer_question(seeded, "who built you?").lower()
    assert "nawaf" in a or "booking-agent" in a


def test_how_it_works_question(seeded: Session) -> None:
    a = answer_question(seeded, "how does this work?").lower()
    assert any(w in a for w in ("seat", "email", "book", "ticket"))


def test_event_type_question_surfaces_catalog(seeded: Session) -> None:
    a = answer_question(seeded, "what football matches are there?")
    assert "Al-Hilal" in a or "Derby" in a or "coming up" in a.lower()


def test_describe_current_event(coldplay_riyadh_id: int, seeded: Session) -> None:
    a = answer_question(seeded, "tell me about this event", coldplay_riyadh_id).lower()
    assert "coldplay" in a
    assert "kingdom arena" in a or "riyadh" in a
