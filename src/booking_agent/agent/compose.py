"""Optional dynamic reply phrasing — targets the "it feels scripted" problem.

When ``BOOKING_AGENT_DYNAMIC_REPLIES`` is enabled AND a provider key is set, a
*plain-text* reply is rephrased by the model (warmer, more varied wording) while
every fact, number, price, seat code and the ask stay identical.

**Off by default**, and `payloads.make_payload` only ever calls this for plain
conversational replies — replies that carry structured booking data
(confirmation/payment/quote/categories/…) are NEVER rephrased, because their text
is a thin label and the model would fabricate the missing details. So correctness
and the HITL gate are unaffected whether this is on or off.
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
        rephrased = chat_complete(_SYSTEM, text, max_tokens=220).strip()
        return rephrased or text
    except Exception:
        return text  # never let phrasing break a turn
