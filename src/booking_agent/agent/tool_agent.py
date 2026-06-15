"""Tool-calling agent mode — the model drives the tools (Week 4: *Reason–Act–
Observe Loop*; Week 5: *Loop Prevention*).

This is the genuinely "agentic" path: instead of a hardcoded state machine, the
LLM decides which tool to call each step, we execute it (`tool_specs.dispatch`),
feed the result back, and repeat until the model answers or a step cap trips
(loop prevention). The dangerous action — creating the booking / payment — is
kept OUT of the model's reach and handled deterministically only after an
explicit user "confirm" at the gate (Constitution I).

Off by default (`BOOKING_AGENT_MODE=fsm`); the deterministic `policy.respond`
remains the MVP (Constitution VIII). `complete` is injectable so the whole loop
is unit-tested offline with a scripted fake model.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy.orm import Session

from booking_agent.agent import guardrails, observability
from booking_agent.agent import state as S
from booking_agent.agent.extract import heuristic_extract
from booking_agent.agent.llm import NANOGPT_BASE_URL, llm_available
from booking_agent.agent.sentiment import classify_sentiment
from booking_agent.agent.memory import MEMORY
from booking_agent.agent.state import ConversationState
from booking_agent.agent.tool_specs import TOOL_SCHEMAS, dispatch
from booking_agent.agent.responses import infer_response_type
from booking_agent.config import settings
from booking_agent.db.enums import MemberTier
from booking_agent.tools.booking import create_booking_from_hold
from booking_agent.tools.events import get_event_details
from booking_agent.tools.holds import release_seat_hold
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote

# Type of the injectable model interface: (messages, tools) -> {content, tool_calls}.
Complete = Callable[[list[dict], list[dict]], dict]

MAX_STEPS = 6  # loop-prevention cap on tool round-trips per user turn

SYSTEM = (
    "You are Booking Agent, a warm, witty event-ticketing concierge for Saudi Arabia "
    "(Arabic/English). Chat naturally like a helpful friend: greet back, make a little "
    "small talk, answer questions, and give honest recommendations (best-value seats, "
    "what's fun this weekend). PERSONALISE using the booking-state note provided — use "
    "the user's name and membership tier when they're known. "
    "Use the tools to actually get things done — find the event, look up membership by "
    "email, quote a category + quantity, hold seats — and ask for any missing detail "
    "instead of guessing. When they want to browse but haven't said what they like, ask "
    "about their interests (concerts, sports, comedy, tech) and any city/date first — "
    "don't list the whole catalog. You don't have to call a tool every turn: if the user "
    "is just chatting or asking something, simply reply. "
    "After you HOLD seats, summarise the order and ask them to confirm — NEVER claim "
    "payment is done; the system charges only after the user explicitly confirms. "
    "Never invent events, prices, or seats; if you don't have it, say so."
)


def tool_mode_available() -> bool:
    return llm_available()


def _tier(state: ConversationState) -> MemberTier | None:
    return MemberTier(state.tier) if state.tier else None


def _blank_payload(state: ConversationState) -> dict:
    return {"session_id": state.session_id, "reply": "", "step": state.step,
            "suggestions": [], "events": None, "member": None, "categories": None,
            "quote": None, "seatmap_url": None, "hold": None, "confirmation": None,
            "payment": None}


def _payload(state: ConversationState, text: str, *, suggestions: list[str] | None = None, **extra) -> dict:
    state.record("agent", text)
    payload = _blank_payload(state)
    payload["reply"] = text
    payload["suggestions"] = suggestions or []
    payload.update(extra)
    payload["response_type"] = infer_response_type(payload)
    return payload


def _state_summary(state: ConversationState) -> str:
    # Privacy: share the first name + whether an email is known, never the address.
    return (f"name={state.name or 'unknown'}, event_selected={bool(state.event_id)}, "
            f"email_known={bool(state.email)}, member_tier={state.tier or 'none'}, "
            f"ticket_cap={state.ticket_cap}, category={state.category}, quantity={state.quantity}, "
            f"seats_held={bool(state.hold_token)}, step={state.step}")


def _confirmation_payload(db: Session, state: ConversationState) -> dict:
    ev = get_event_details(db, state.event_id)
    quote = compute_quote(db, state.event_id, state.category, state.quantity, _tier(state))
    return _payload(
        state,
        "Please review and confirm before payment:",
        quote={"category": quote.category.value, "quantity": quote.quantity,
               "lines": quote.summary_lines(), "total_sar": sar_str(quote.total, quote.currency)},
        hold={"seat_ids": state.seat_ids, "expires_at": state.hold_expires, "ttl_minutes": 10},
        confirmation={"event_title": ev.title, "when": ev.starts_at.strftime("%a %d %b %Y, %H:%M"),
                      "venue": f"{ev.venue}, {ev.city}", "seats": state.seat_ids,
                      "subtotal_sar": sar_str(quote.net_subtotal, quote.currency),
                      "vat_sar": sar_str(quote.vat, quote.currency),
                      "total_sar": sar_str(quote.total, quote.currency),
                      "expires_at": state.hold_expires},
        suggestions=["confirm", "cancel"],
    )


def respond_with_tools(db: Session, state: ConversationState, message: str,
                       complete: Complete, max_steps: int = MAX_STEPS) -> dict:
    state.turn += 1
    state.record("user", message)
    state.sentiment = classify_sentiment(message)

    # --- HITL gate: confirm/cancel handled in code, never by the model. ----- #
    if state.step == S.AWAITING_CONFIRMATION:
        intent = heuristic_extract(message, state.step).intent
        if intent == "confirm":
            assert guardrails.can_issue_payment(state.step)  # Constitution I
            booking = create_booking_from_hold(
                db, email=state.email, event_id=state.event_id, category=state.category,
                quantity=state.quantity, seat_ids=state.seat_ids,
                hold_token=state.hold_token, tier=_tier(state))
            state.booking_id = booking.id
            state.step = S.PAYMENT
            observability.log_tool(state.session_id, "create_booking", turn=state.turn,
                                   booking_id=booking.id, total_sar=sar_str(booking.total, booking.currency))
            observability.log_transition(state.session_id, S.AWAITING_CONFIRMATION, S.PAYMENT, turn=state.turn)
            MEMORY.record(state.email, f"{get_event_details(db, state.event_id).title} — {state.quantity}× {state.category}")
            return _payload(state, "Confirmed! ✅ Complete your payment to get your ticket.",
                            payment={"booking_id": booking.id, "total_sar": sar_str(booking.total, booking.currency)})
        if intent == "cancel":
            if state.hold_token:
                release_seat_hold(db, state.hold_token)
            state.hold_token = state.hold_expires = None
            state.seat_ids = []
            state.step = S.SEAT_SELECTION
            return _payload(state, "No problem — I released those seats. Want to pick different ones?")
        return _payload(state, "Reply **confirm** to pay, or **cancel** to release the seats.",
                        suggestions=["confirm", "cancel"])

    # --- Reason–Act–Observe loop ------------------------------------------- #
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "system", "content": "Current booking state: " + _state_summary(state)},
        {"role": "user", "content": message},
    ]
    for _ in range(max_steps):
        try:
            resp = complete(messages, TOOL_SCHEMAS)
        except Exception:  # noqa: BLE001 — never hang/500 on a slow or down model
            return _payload(state, "Sorry — I'm having trouble reaching my assistant brain "
                                   "right now. Tell me an event (e.g. \"Coldplay in Riyadh\") "
                                   "and I'll get you sorted.")
        calls = resp.get("tool_calls") or []
        if not calls:
            return _payload(state, resp.get("content") or "How can I help with your booking?")

        messages.append({"role": "assistant", "content": resp.get("content") or "", "tool_calls": calls})
        for call in calls:
            args = call.get("arguments") or {}
            result = dispatch(db, state, call["name"], args)
            observability.log_tool(state.session_id, call["name"], turn=state.turn,
                                   args=json.dumps(args, default=str))
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "name": call["name"], "content": json.dumps(result, default=str)})

        # The moment seats are held we present the HITL confirmation card.
        if state.step == S.AWAITING_CONFIRMATION:
            observability.log_transition(state.session_id, S.SEAT_SELECTION, S.AWAITING_CONFIRMATION, turn=state.turn)
            return _confirmation_payload(db, state)

    # Loop prevention: never spin forever.
    return _payload(state, "I couldn't wrap that up in a few steps — could you give me one "
                           "detail at a time (event, email, category, quantity, seats)?")


# --------------------------------------------------------------------------- #
# Production model interface (nano-gpt / OpenAI tool-calling). Live-only; the
# loop above is what tests exercise via a scripted fake `complete`.
# --------------------------------------------------------------------------- #

def _to_openai(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content") or "",
                        "tool_calls": [{"id": c.get("id", ""), "type": "function",
                                        "function": {"name": c["name"],
                                                     "arguments": json.dumps(c.get("arguments") or {})}}
                                       for c in m["tool_calls"]]})
        elif m.get("role") == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""), "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m.get("content", "")})
    return out


def default_complete(messages: list[dict], tools: list[dict]) -> dict:
    """Call the configured nano-gpt/OpenAI model with tools; normalise the reply."""
    from openai import OpenAI  # deferred

    provider = settings.booking_agent_provider.lower()
    base_url = NANOGPT_BASE_URL if provider in {"nanogpt", "nano-gpt", "nano_gpt"} else None
    client = OpenAI(api_key=settings.active_llm_key, base_url=base_url,
                    timeout=settings.llm_timeout_seconds)
    resp = client.chat.completions.create(
        model=settings.booking_agent_model, messages=_to_openai(messages),
        tools=tools, temperature=0)
    msg = resp.choices[0].message
    calls: list[dict] = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        try:
            arguments = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        calls.append({"id": tc.id, "name": tc.function.name, "arguments": arguments})
    return {"content": msg.content, "tool_calls": calls}
