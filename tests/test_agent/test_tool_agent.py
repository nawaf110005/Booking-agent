"""Tool-calling agent tests — fully offline via a scripted fake model.

Exercises the Reason–Act–Observe loop, the autonomy guardrail (the model cannot
book/pay), loop prevention, observability, and the mode router. The model is
injected, so no network or key is needed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import handle, tool_agent
from booking_agent.agent import observability as obs
from booking_agent.agent import state as S
from booking_agent.agent.state import ConversationState
from booking_agent.agent.tool_specs import dispatch
from booking_agent.tools.payments import pay_booking

# --- fake model helpers ---------------------------------------------------- #

def _tc(name: str, **arguments) -> dict:
    return {"id": f"call_{name}", "name": name, "arguments": arguments}


def _step(*calls) -> dict:
    return {"content": "", "tool_calls": list(calls)}


def _final(text: str) -> dict:
    return {"content": text, "tool_calls": []}


class FakeModel:
    """Returns scripted responses; counts calls; defaults to a final answer."""

    def __init__(self, script: list[dict]) -> None:
        self.script = list(script)
        self.calls = 0

    def __call__(self, messages: list[dict], tools: list[dict]) -> dict:
        self.calls += 1
        return self.script.pop(0) if self.script else _final("done")


# --- tests ----------------------------------------------------------------- #

def test_tool_agent_books_end_to_end(seeded: Session) -> None:
    model = FakeModel([
        _step(_tc("search_events", query="coldplay", city="Riyadh")),
        _step(_tc("lookup_member", email="nawaf@example.com")),
        _step(_tc("quote_price", category="gold", quantity=4)),
        _step(_tc("hold_seats", seat_ids=["G3", "G4", "G5", "G6"])),
    ])
    st = ConversationState(session_id="ta-1")
    r = tool_agent.respond_with_tools(seeded, st, "4 gold for Coldplay Riyadh, nawaf@example.com", model)

    assert st.event_id is not None
    assert st.email == "nawaf@example.com" and st.tier == "platinum"
    assert (st.category, st.quantity) == ("gold", 4)
    assert st.hold_token is not None
    assert r["step"] == S.AWAITING_CONFIRMATION
    assert r["confirmation"]["seats"] == ["G3", "G4", "G5", "G6"]
    assert r["confirmation"]["total_sar"] == "3,128.00 SAR"
    assert model.calls == 4  # four tool round-trips

    # The confirm turn is deterministic — the model is NOT consulted.
    r2 = tool_agent.respond_with_tools(seeded, st, "confirm", model)
    assert r2["step"] == S.PAYMENT and st.booking_id
    assert model.calls == 4  # unchanged → model wasn't called on confirm
    ticket = pay_booking(seeded, st.booking_id)
    assert ticket["seats"] == ["G3", "G4", "G5", "G6"]


def test_model_cannot_book_or_pay_as_a_tool(seeded: Session) -> None:
    # Even if the model tries to call a payment/booking tool, it's refused.
    model = FakeModel([
        _step(_tc("create_booking", event_id=1, seats=["G3"])),  # forbidden
        _final("Sorry, I can't do that step myself."),
    ])
    st = ConversationState(session_id="ta-2")
    r = tool_agent.respond_with_tools(seeded, st, "just book it and pay now", model)
    assert st.booking_id is None
    assert r["step"] != S.PAYMENT


def test_dispatch_refuses_forbidden_and_unknown_tools(seeded: Session) -> None:
    st = ConversationState(session_id="ta-3")
    for name in ("create_booking", "pay", "issue_payment", "delete_everything"):
        out = dispatch(seeded, st, name, {})
        assert "error" in out


def test_loop_prevention_caps_steps(seeded: Session) -> None:
    # A model that never stops calling tools must not loop forever.
    class AlwaysTool:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages, tools):
            self.calls += 1
            return _step(_tc("search_events", query="coldplay"))  # 2 matches → never auto-selects

    model = AlwaysTool()
    st = ConversationState(session_id="ta-4")
    r = tool_agent.respond_with_tools(seeded, st, "find me something", model, max_steps=3)
    assert model.calls == 3                 # stopped at the cap
    assert st.step != S.PAYMENT
    assert r["reply"]                       # returned a safe message, didn't hang


def test_plain_answer_when_no_tool_calls(seeded: Session) -> None:
    model = FakeModel([_final("Hi! Which event would you like?")])
    st = ConversationState(session_id="ta-5")
    r = tool_agent.respond_with_tools(seeded, st, "hello", model)
    assert r["reply"] == "Hi! Which event would you like?"


def test_tool_calls_are_observable(seeded: Session) -> None:
    obs.reset()
    model = FakeModel([
        _step(_tc("search_events", query="coldplay", city="Riyadh")),
        _step(_tc("lookup_member", email="nawaf@example.com")),
        _final("What category and how many?"),
    ])
    st = ConversationState(session_id="ta-6")
    tool_agent.respond_with_tools(seeded, st, "coldplay riyadh nawaf@example.com", model)
    tools = [e["tool"] for e in obs.events("ta-6") if e["kind"] == "tool_call"]
    assert "search_events" in tools and "lookup_member" in tools


def test_router_defaults_to_multi_agent(seeded: Session) -> None:
    # Default mode routes to the orchestrator + specialist team (offline brain).
    st = ConversationState(session_id="ta-7")
    r = handle(seeded, st, "Coldplay in Riyadh")
    assert r["step"] == S.NEED_EMAIL  # orchestrator resolved the event, asks for email


def test_router_selects_tool_agent_when_configured(seeded: Session, monkeypatch) -> None:
    monkeypatch.setattr(tool_agent.settings, "booking_agent_mode", "tool_agent", raising=False)
    monkeypatch.setattr(tool_agent, "tool_mode_available", lambda: True)
    monkeypatch.setattr(tool_agent, "default_complete",
                        lambda messages, tools: _final("routed to the tool agent"))
    st = ConversationState(session_id="ta-8")
    r = handle(seeded, st, "hello")
    assert r["reply"] == "routed to the tool agent"


def test_tool_agent_no_hang_on_model_failure(seeded: Session) -> None:
    # A slow/down model raises — the agent must return a clear message, not crash/hang.
    def boom(messages, tools):
        raise RuntimeError("nano-gpt timeout")

    st = ConversationState(session_id="ta-9")
    r = tool_agent.respond_with_tools(seeded, st, "hi", boom)
    assert r["reply"] and "trouble" in r["reply"].lower()
    assert st.booking_id is None
