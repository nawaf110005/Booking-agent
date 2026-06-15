"""Tests for observable reasoning (Constitution VII / FR-011)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import observability as obs
from booking_agent.agent import state as S
from booking_agent.agent.policy import respond
from booking_agent.agent.state import ConversationState


def test_redacts_email() -> None:
    assert obs.redact_pii("ping nawaf@example.com now") == "ping n***@example.com now"
    assert obs.redact_pii(42) == 42  # non-strings pass through


def test_tool_calls_are_logged_with_redacted_pii(seeded: Session) -> None:
    obs.reset()
    st = ConversationState(session_id="obs-1")
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")

    evs = obs.events("obs-1")
    tools = [e["tool"] for e in evs if e["kind"] == "tool_call"]
    assert "nlu_extract" in tools
    assert "lookup_member" in tools

    blob = repr(evs)
    assert "nawaf@example.com" not in blob        # raw PII never stored
    assert "n***@example.com" in blob             # ...only its redaction


def test_state_transitions_are_logged_end_to_end(seeded: Session) -> None:
    obs.reset()
    st = ConversationState(session_id="obs-2")
    respond(seeded, st, "4 gold tickets for Coldplay in Riyadh, nawaf@example.com")
    respond(seeded, st, "G3, G4, G5, G6")   # -> AWAITING_CONFIRMATION
    respond(seeded, st, "confirm")           # -> PAYMENT

    transitions = [(e["from"], e["to"]) for e in obs.events("obs-2") if e["kind"] == "transition"]
    tos = {to for _, to in transitions}
    assert S.AWAITING_CONFIRMATION in tos
    assert S.PAYMENT in tos
