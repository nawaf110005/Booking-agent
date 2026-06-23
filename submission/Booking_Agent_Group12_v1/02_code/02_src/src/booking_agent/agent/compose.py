"""Optional dynamic reply phrasing — directly targets the "it feels scripted"
problem without giving up the deterministic state machine's safety.

When ``BOOKING_AGENT_DYNAMIC_REPLIES`` is enabled AND a provider key is set, the
agent's canned reply text is rephrased by the model (warmer, more varied wording)
while every fact, number, price, seat code and the ask stay identical — and the
structured payloads (quote/confirmation/payment) are never touched, so correctness
and the HITL gate are unaffected. Off by default: pass-through, so the FSM's
behavior and the whole test suite are unchanged unless explicitly turned on.
"""

from __future__ import annotations

from booking_agent.agent.llm import chat_complete, llm_available
from booking_agent.config import settings

_SYSTEM = (
    "You are a friendly event-booking concierge. Rephrase the assistant message "
    "below so it sounds warm, natural and concise. KEEP every fact, number, price, "
    "seat code, email and the SAME question/ask exactly — do not add, drop, or "
    "change any information. Do NOT invent a person's name, and never turn an email "
    "address into a name (e.g. don't write 'nawaf gmail'). Reply with ONLY the "
    "rephrased message, no preamble."
)


def dynamic_replies_enabled() -> bool:
    return bool(getattr(settings, "booking_agent_dynamic_replies", False)) and llm_available()


def compose_reply(text: str) -> str:
    """Return a rephrased message when dynamic replies are on, else ``text``."""
    if not text or not dynamic_replies_enabled():
        return text
    try:
        rephrased = chat_complete(_SYSTEM, text, max_tokens=200).strip()
        return rephrased or text
    except Exception:
        return text  # never let phrasing break a turn
