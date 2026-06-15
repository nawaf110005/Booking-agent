"""LLM-enabled policy tests, incl. the HITL guardrail.

The booking-flow suite runs with the LLM forced off. These tests flip it on
(with a stubbed extractor, no network) so the *LLM-driven* path through
`policy.respond` is exercised — including the safety property that a stray
`confirm` from the model cannot jump the human-in-the-loop payment gate
(Constitution I; Week 6 "Test Guardrails").
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.agent import policy as policy_mod
from booking_agent.agent import state as S
from booking_agent.agent.policy import respond
from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.state import ConversationState


def _enable_llm(monkeypatch: pytest.MonkeyPatch, extract_fn) -> None:
    # Overrides the autouse `_force_heuristic` fixture for this test only.
    monkeypatch.setattr(policy_mod, "llm_available", lambda: True, raising=False)
    monkeypatch.setattr(policy_mod, "llm_extract", extract_fn, raising=False)


def test_llm_extractor_drives_one_shot_booking(seeded: Session, monkeypatch) -> None:
    # Slots come from the LLM (not regex); the agent should still reach the seat
    # map in one turn — parity with the heuristic one-shot, via the LLM path.
    def fake_extract(message: str) -> BookingParams:
        return BookingParams(intent="book", event_query="coldplay", city="Riyadh",
                             category="gold", quantity=4, email="nawaf@example.com")

    _enable_llm(monkeypatch, fake_extract)
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "free-form text the LLM turns into slots")
    assert st.event_id is not None
    assert (st.email, st.category, st.quantity) == ("nawaf@example.com", "gold", 4)
    assert r["step"] == S.SEAT_SELECTION


def test_heuristic_ask_intent_not_downgraded_by_llm(seeded: Session, monkeypatch) -> None:
    # A question must stay a question even if the LLM mislabels it as a booking.
    _enable_llm(monkeypatch, lambda m: BookingParams(intent="book", event_query="coldplay"))
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "is there a discount?")
    assert st.event_id is None  # not derailed into a booking
    assert "%" in r["reply"] or "member" in r["reply"].lower()


def test_llm_confirm_cannot_bypass_hitl_gate(seeded: Session, monkeypatch) -> None:
    # GUARDRAIL: model returns intent=confirm on a fresh session; no payment may
    # be issued because state != AWAITING_CONFIRMATION.
    _enable_llm(monkeypatch, lambda m: BookingParams(intent="confirm"))
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "go")
    assert r["payment"] is None
    assert r["step"] != S.PAYMENT
    assert st.booking_id is None


def test_policy_falls_back_when_llm_returns_none(seeded: Session, monkeypatch) -> None:
    # If the model is unavailable/malformed (extractor -> None), the heuristic
    # still carries the turn.
    _enable_llm(monkeypatch, lambda m: None)
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "Coldplay in Riyadh")
    assert st.event_id is not None
    assert r["step"] == S.NEED_EMAIL
