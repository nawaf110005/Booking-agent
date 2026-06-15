"""The conversational + personalised layer.

Two kinds of coverage: the deterministic offline behaviour (name from email,
rule-based greetings) and the runtime behaviour gated behind the LLM (chat/ask at
any step routes to a personalised answer and does NOT get misparsed into the flow).
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.agent import answer as answer_mod
from booking_agent.agent import policy as policy_mod
from booking_agent.agent import state as S
from booking_agent.agent.answer import answer_question
from booking_agent.agent.policy import respond
from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.state import ConversationState


def test_name_personalised_from_email(seeded: Session) -> None:
    st = ConversationState(session_id="c1")
    respond(seeded, st, "Coldplay in Riyadh")
    r = respond(seeded, st, "nawaf@example.com")
    assert st.name == "Nawaf"
    assert "Nawaf" in r["reply"]  # the agent greets them by name


def test_rule_based_greeting_offline(seeded: Session) -> None:
    # No key → friendly canned greeting (not the "I can only…" brush-off).
    assert "Tazkara" in answer_question(seeded, "hello")
    assert "event" in answer_question(seeded, "thanks!").lower()


def test_greeting_routes_to_chat_when_llm_on(seeded: Session, monkeypatch) -> None:
    monkeypatch.setattr(policy_mod, "llm_available", lambda: True)
    monkeypatch.setattr(policy_mod, "llm_extract", lambda m: BookingParams(intent="greet"))
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)
    monkeypatch.setattr(answer_mod, "chat_complete", lambda s, u, **k: "Hey! Ready to find you something fun?")
    st = ConversationState(session_id="c3")
    r = respond(seeded, st, "yo")
    assert r["reply"] == "Hey! Ready to find you something fun?"
    assert st.event_id is None  # a greeting doesn't force a booking


def test_question_midstep_is_answered_not_misparsed(seeded: Session, coldplay_riyadh_id: int, monkeypatch) -> None:
    # At the quantity step, "which is better, gold or vip?" must be answered — not
    # silently turned into a category/quantity by stray keyword extraction.
    monkeypatch.setattr(policy_mod, "llm_available", lambda: True)
    monkeypatch.setattr(policy_mod, "llm_extract", lambda m: BookingParams(intent="ask"))
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)
    monkeypatch.setattr(answer_mod, "chat_complete", lambda s, u, **k: "Gold's the sweet spot, and you get 15% off.")
    st = ConversationState(session_id="c4", event_id=coldplay_riyadh_id, email="nawaf@example.com",
                          name="Nawaf", tier="platinum", is_member=True, ticket_cap=8,
                          category="gold", step=S.NEED_QUANTITY)
    r = respond(seeded, st, "which is better, gold or vip?")
    assert r["reply"] == "Gold's the sweet spot, and you get 15% off."
    assert st.quantity is None  # not misparsed into the flow


def test_context_passed_to_answerer(seeded: Session, monkeypatch) -> None:
    # The personalisation context (name/tier/step) reaches the model prompt.
    captured = {}
    monkeypatch.setattr(policy_mod, "llm_available", lambda: True)
    monkeypatch.setattr(policy_mod, "llm_extract", lambda m: BookingParams(intent="ask"))
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)

    def _spy(system, user, **kw):
        captured["user"] = user
        return "ok"

    monkeypatch.setattr(answer_mod, "chat_complete", _spy)
    st = ConversationState(session_id="c5", email="nawaf@example.com", name="Nawaf",
                          tier="platinum", is_member=True, ticket_cap=8)
    respond(seeded, st, "what do you recommend?")
    assert "Nawaf" in captured["user"] and "Platinum member" in captured["user"]


def test_offtopic_gets_clear_answer_not_canned_greeting(seeded: Session, monkeypatch) -> None:
    # "write me code" must get a clear reply — not the canned greeting that ignores it.
    monkeypatch.setattr(policy_mod, "llm_available", lambda: True)
    monkeypatch.setattr(policy_mod, "llm_extract", lambda m: BookingParams())  # nothing actionable
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)
    monkeypatch.setattr(answer_mod, "chat_complete",
                        lambda s, u, **k: "I can't write code — I'm Tazkara, your ticket concierge. Want to find an event?")
    st = ConversationState(session_id="c6")
    r = respond(seeded, st, "write me code")
    assert r["reply"] == "I can't write code — I'm Tazkara, your ticket concierge. Want to find an event?"
    assert "Tell me what you'd like to see" not in r["reply"]  # not the canned greeting
