"""Per-turn sentiment (FR-012) and the venue/FAQ RAG (spec 007)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent.answer import answer_question
from booking_agent.agent.policy import respond
from booking_agent.agent.rag import retrieve
from booking_agent.agent.sentiment import classify_sentiment, is_unhappy
from booking_agent.agent.state import ConversationState


def test_sentiment_labels() -> None:
    assert classify_sentiment("this is dumb") == "frustrated"
    assert classify_sentiment("the seat map is broken") == "negative"
    assert classify_sentiment("thanks, perfect!") == "positive"
    assert classify_sentiment("4 gold tickets please") == "neutral"
    assert is_unhappy("frustrated") and not is_unhappy("positive")


def test_respond_records_sentiment_each_turn(seeded: Session) -> None:
    st = ConversationState(session_id="s1")
    respond(seeded, st, "this is dumb, it's broken")
    assert st.sentiment in ("frustrated", "negative")


def test_rag_retrieves_relevant_snippet() -> None:
    hits = retrieve("is there parking at the venue?")
    assert hits and "parking" in hits[0].lower()


def test_rag_ignores_irrelevant_query() -> None:
    assert retrieve("tell me about the weather") == []


def test_answer_grounds_in_kb_offline(seeded: Session) -> None:
    assert "parking" in answer_question(seeded, "is there parking?").lower()


def test_rag_ignores_generic_booking_words() -> None:
    # "ticket"/"book"/"seat" are too generic to anchor an FAQ — must not match.
    assert retrieve("I need a ticket for jb") == []
    assert retrieve("book me some seats") == []


def test_extractor_captures_unknown_event_name() -> None:
    from booking_agent.agent.extract import heuristic_extract

    assert heuristic_extract("I need ticket for jb").event_query == "jb"
    assert heuristic_extract("tickets to the weeknd please").event_query == "weeknd"
    # known events still resolve via keyword
    assert heuristic_extract("4 gold tickets for Coldplay").event_query == "coldplay"


def test_unknown_event_is_acknowledged_not_ignored(seeded: Session) -> None:
    # "ticket for jb" (not in the catalog) must be acknowledged — not answered with
    # an unrelated FAQ snippet (the old bug).
    from booking_agent.agent.policy import respond
    from booking_agent.agent.state import ConversationState

    st = ConversationState(session_id="ue1")
    r = respond(seeded, st, "I need ticket for jb")
    assert st.event_id is None
    assert "jb" in r["reply"].lower() or "couldn't find" in r["reply"].lower()
    assert r["events"]                                # shows the catalog instead of ignoring
    assert "showtime" not in r["reply"].lower()       # not the gates FAQ snippet
