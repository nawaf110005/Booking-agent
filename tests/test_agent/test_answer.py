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


def test_no_moyasar_in_payment_copy() -> None:
    # Payment is a virtual/sandbox checkout — no external provider named to users.
    from booking_agent.agent import answer as ans
    from booking_agent.agent.rag import KNOWLEDGE_BASE

    assert "moyasar" not in ans.PAYMENT.lower()
    assert "virtual" in ans.PAYMENT.lower() or "sandbox" in ans.PAYMENT.lower()
    assert not any("moyasar" in d["text"].lower() for d in KNOWLEDGE_BASE)


# --- RAG relevance: no coincidental single-word FAQ match (FR-005 / SC-002) ---

def test_rag_ignores_coincidental_word() -> None:
    from booking_agent.agent.rag import retrieve

    # "here" appears in the payment entry but the question is not about payment.
    assert retrieve("dose cold play will be here in saudi", k=1, min_overlap=1) == []
    # genuine, on-topic FAQ questions still match
    assert retrieve("parking?", k=1, min_overlap=1)
    assert retrieve("where do i park", k=1, min_overlap=1)
    assert retrieve("is there a refund", k=1, min_overlap=1)


def test_event_question_not_answered_with_faq(seeded=None) -> None:
    import booking_agent.agent.answer as ans
    ans.llm_available = lambda: False
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from booking_agent.db import models  # noqa
    from booking_agent.db.base import Base
    from booking_agent.db.seed import seed_demo

    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    db = sessionmaker(bind=e)()
    seed_demo(db)
    db.commit()
    reply = ans.answer_question(db, "dose cold play will be here in saudi")
    assert "payment" not in reply.lower() and "moyasar" not in reply.lower()
