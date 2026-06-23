"""Orchestrator with the LLM brain switched on (no network).

The booking-flow suite runs with the offline brain. These tests flip the LLM on
and inject a fake `default_complete` so the *model-driven* multi-agent path is
exercised — the specialists choose tools, the orchestrator hands off between them
— including the safety property that a stray `confirm` cannot jump the
human-in-the-loop payment gate (Constitution I; Week 6 "Test Guardrails").
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from booking_agent.agent import orchestrator as orch
from booking_agent.agent import state as S
from booking_agent.agent import tool_agent
from booking_agent.agent.orchestrator import respond
from booking_agent.agent.state import ConversationState
from booking_agent.tools.payments import pay_booking


class TeamBrain:
    """Stands in for the real LLM. Each specialist offers only its own tools; this
    returns the right tool call for whichever specialist is asking, from a fixed
    booking plan — so the orchestrator drives the team end to end, offline."""

    PLAN: ClassVar[dict] = {
        "search_events": {"query": "coldplay", "city": "Riyadh"},
        "lookup_member": {"email": "nawaf@example.com"},
        "quote_price": {"category": "gold", "quantity": 4},
        "hold_seats": {"seat_ids": ["G3", "G4", "G5", "G6"]},
    }

    def __init__(self) -> None:
        self.calls = 0
        self.done: set[str] = set()

    def __call__(self, messages: list[dict], tools: list[dict]) -> dict:
        self.calls += 1
        for t in tools:
            name = t["function"]["name"]
            if name in self.PLAN and name not in self.done:
                self.done.add(name)
                return {"content": "", "tool_calls": [{"id": name, "name": name, "arguments": self.PLAN[name]}]}
        return {"content": "ok", "tool_calls": []}


def _enable_llm(monkeypatch: pytest.MonkeyPatch, brain) -> None:
    # Override the autouse offline fixture for this test only.
    monkeypatch.setattr(orch, "llm_available", lambda: True, raising=False)
    monkeypatch.setattr(orch, "llm_extract", lambda m: None, raising=False)
    monkeypatch.setattr(tool_agent, "default_complete", brain, raising=False)


def test_specialist_team_books_with_injected_brain(seeded: Session, monkeypatch) -> None:
    brain = TeamBrain()
    _enable_llm(monkeypatch, brain)
    st = ConversationState(session_id="t")
    # Seats are named, so the seating specialist actually holds (we no longer let the
    # model invent seats when the user only gave a quantity).
    r = respond(seeded, st, "4 gold for Coldplay in Riyadh, nawaf@example.com, seats G3 G4 G5 G6")

    # The model drove every specialist; the orchestrator reached the HITL gate.
    assert st.event_id is not None
    assert (st.email, st.category, st.quantity) == ("nawaf@example.com", "gold", 4)
    assert st.hold_token is not None
    assert r["step"] == S.AWAITING_CONFIRMATION
    assert r["confirmation"]["total_sar"] == "3,128.00 SAR"

    # Confirm is handled in code — the model is not consulted to take payment.
    r2 = respond(seeded, st, "confirm")
    assert r2["step"] == S.PAYMENT and st.booking_id
    ticket = pay_booking(seeded, st.booking_id)
    assert ticket["seats"] == ["G3", "G4", "G5", "G6"]


def test_confirm_cannot_bypass_hitl_gate(seeded: Session, monkeypatch) -> None:
    # GUARDRAIL: a stray "confirm" on a fresh session must not issue payment,
    # because state != AWAITING_CONFIRMATION.
    _enable_llm(monkeypatch, TeamBrain())
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "confirm")
    assert r["payment"] is None
    assert r["step"] != S.PAYMENT
    assert st.booking_id is None


def test_graceful_when_model_unavailable(seeded: Session, monkeypatch) -> None:
    # If the injected brain raises (slow/down provider), the turn must not crash;
    # the deterministic catalog resolution still carries it forward.
    def boom(messages, tools):
        raise RuntimeError("provider timeout")

    _enable_llm(monkeypatch, boom)
    st = ConversationState(session_id="t")
    r = respond(seeded, st, "Coldplay in Riyadh")
    assert r["reply"]                       # answered, didn't hang/crash
    assert st.booking_id is None            # no payment slipped through
