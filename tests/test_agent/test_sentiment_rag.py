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
