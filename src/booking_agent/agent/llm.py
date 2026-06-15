"""Optional LLM slot extractor.

Activates only when a provider key is configured (see config.active_llm_key).
Supports Anthropic, OpenAI, and Nano-GPT (OpenAI-compatible proxy). On any
import/auth/parse error it returns None and the caller uses the heuristic —
the failure is recorded in `LAST_ERROR` so the UI/health can surface it.
"""

from __future__ import annotations

import json
import re

from booking_agent.agent.schemas import BookingParams
from booking_agent.config import settings

NANOGPT_BASE_URL = "https://nano-gpt.com/api/v1"

LAST_ERROR: str | None = None

_SYSTEM = (
    "You extract booking slots from the user's latest message in an event-ticket "
    "booking chat for Saudi Arabia (users may mix Arabic and English). "
    "Return ONLY a compact JSON object with these keys:\n"
    '  intent: one of "book","select_event","email","category","quantity",'
    '"seats","confirm","cancel","browse","ask","greet", or null\n'
    "  event_query: short search term like \"coldplay\",\"derby\",\"leap\",\"soundstorm\", or null\n"
    '  city: "Riyadh" | "Jeddah" | null\n'
    '  when: "weekend" | "today" | "tomorrow" | "week" | null\n'
    "  event_id: integer or null\n"
    "  email: string or null\n"
    '  category: "vip" | "gold" | "silver" | "standing" | null\n'
    "  quantity: integer or null\n"
    "  seat_ids: array of seat labels like [\"G3\",\"G4\"] or []\n"
    "Do NOT invent values; use null/[] when the message doesn't state them."
)


def llm_available() -> bool:
    return settings.llm_configured


def _parse_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def chat_complete(system: str, user: str, max_tokens: int = 600) -> str:
    """One chat turn against the configured provider. Raises on failure.

    Covers Anthropic directly and OpenAI / Nano-GPT via the OpenAI SDK.
    """

    provider = settings.booking_agent_provider.lower()
    if provider == "anthropic":
        import anthropic  # deferred

        client = anthropic.Anthropic(api_key=settings.active_llm_key,
                                     timeout=settings.llm_timeout_seconds)
        resp = client.messages.create(
            model=settings.booking_agent_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    from openai import OpenAI  # deferred

    base_url = NANOGPT_BASE_URL if provider in {"nanogpt", "nano-gpt", "nano_gpt"} else None
    client = OpenAI(api_key=settings.active_llm_key, base_url=base_url,
                    timeout=settings.llm_timeout_seconds)
    resp = client.chat.completions.create(
        model=settings.booking_agent_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def llm_extract(message: str) -> BookingParams | None:
    """Extract slots via the configured LLM, or None on unavailable/failure."""

    global LAST_ERROR
    if not llm_available():
        return None

    try:
        raw = chat_complete(_SYSTEM, message, max_tokens=400)
    except Exception as exc:
        LAST_ERROR = f"{type(exc).__name__}: {str(exc)[:200]}"
        return None

    data = _parse_json(raw)
    if data is None:
        LAST_ERROR = "LLM did not return parseable JSON"
        return None

    LAST_ERROR = None
    # Coerce into the schema, ignoring unknown/garbage values.
    allowed = {"intent", "event_query", "city", "when", "event_id", "email", "category", "quantity", "seat_ids"}
    clean = {k: v for k, v in data.items() if k in allowed and v is not None}
    if isinstance(clean.get("seat_ids"), list):
        clean["seat_ids"] = [str(s).upper() for s in clean["seat_ids"]]
    try:
        return BookingParams(**clean)
    except Exception as exc:
        LAST_ERROR = f"schema coercion failed: {exc}"
        return None
