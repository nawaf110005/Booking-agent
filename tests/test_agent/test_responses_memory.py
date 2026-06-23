"""Typed responses (FR-010) and long-term agent memory (Week 5)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.orchestrator import respond
from booking_agent.agent.responses import AgentResponse, infer_response_type
from booking_agent.agent.state import ConversationState

# --- typed responses (FR-010) --------------------------------------------- #

def test_infer_response_type() -> None:
    assert infer_response_type({"payment": {"x": 1}}) == "payment"
    assert infer_response_type({"confirmation": {"x": 1}}) == "confirmation"
    assert infer_response_type({"quote": {}, "seatmap_url": "/x"}) == "seatmap"
    assert infer_response_type({"events": [1]}) == "event_cards"
    assert infer_response_type({}) == "message"


def test_respond_payload_is_typed(seeded: Session) -> None:
    st = ConversationState(session_id="r1")
    r = respond(seeded, st, "Coldplay in Riyadh")
    assert r["response_type"] == "message"
    model = AgentResponse(**r)          # validates without raising
    assert model.step == r["step"] == S.NEED_EMAIL


def test_event_cards_get_typed(seeded: Session) -> None:
    st = ConversationState(session_id="r2")
    r = respond(seeded, st, "show me concerts")
    assert r["response_type"] == "event_cards"


# --- long-term agent memory (Week 5) -------------------------------------- #

def test_long_term_memory_record_and_recall() -> None:
    from booking_agent.agent.memory import MEMORY

    MEMORY.record("fan@example.com", "Coldplay — 2× gold")
    assert "Coldplay — 2× gold" in MEMORY.recall("fan@example.com")
    assert MEMORY.recall("stranger@example.com") == []


def test_booking_is_remembered_after_confirm(seeded: Session) -> None:
    from booking_agent.agent.memory import MEMORY

    st = ConversationState(session_id="mem1")
    for msg in ("Coldplay in Riyadh", "fanmem@example.com", "gold", "4", "G3, G4, G5, G6", "confirm"):
        respond(seeded, st, msg)
    assert any("Coldplay" in s for s in MEMORY.recall("fanmem@example.com"))
