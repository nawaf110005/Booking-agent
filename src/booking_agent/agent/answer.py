"""Grounded platform Q&A.

Answers any question *about this events-ticketing platform* — discounts and
membership, how booking works, who built it, prices/VAT, payment, policies, and
event-discovery questions ("what football matches this week?"). Uses the LLM
(grounded in the facts + live catalog) when a key is set; otherwise a rule-based
FAQ fallback. Stays on-topic: politely declines anything unrelated.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking_agent.agent.llm import chat_complete, llm_available
from booking_agent.db.models import Seat
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.money import sar_str

# --- Platform knowledge (single source of truth for the answerer) -----------

ABOUT = (
    "Tazkara is an AI event-ticketing concierge for live events in Saudi Arabia "
    "(concerts, sports, theatre, conferences, comedy, festivals). It is a capstone "
    "project — codename Booking-Agent — built for the Agentic AI Bootcamp by "
    "Nawaf Almufarej (lead), Dana, Hessa, and Refal."
)
HOW_IT_WORKS = (
    "How booking works: tell me an event, share your email so I apply any member "
    "discount, pick a category and how many tickets, choose seats on a live seat "
    "map, I hold them for 10 minutes, you confirm the summary, then pay — and you "
    "get a QR ticket."
)
MEMBERSHIP = (
    "Member discounts are applied automatically from your email: Bronze 5%, "
    "Silver 10%, Gold 12%, Platinum 15%. Non-members pay full price. Tickets per "
    "booking: non-member and Bronze up to 4, Silver and Gold up to 6, Platinum up "
    "to 8. VAT of 15% is added to every order."
)
CATEGORIES = "Seat categories vary per event: VIP, Gold, Silver, and Standing."
PAYMENT = (
    "Payment goes through Moyasar — a sandbox for this demo, so no real charge — "
    "with Mada / Apple Pay / STC Pay planned. Tickets are PDFs carrying an "
    "HMAC-signed QR code."
)
LANGUAGES = "You can chat in Arabic or English."

_ANSWER_SYSTEM = (
    "You are Tazkara's friendly booking concierge. Answer the user's question "
    "using ONLY the facts and live catalog provided. Be concise (1-4 sentences), "
    "warm and specific. "
    "Questions about Tazkara itself — what it is, WHO BUILT IT, how it works, "
    "membership/discounts, prices, VAT, payment, and policies — ARE on-topic; "
    "answer them from the facts. "
    "If they ask about events by type or time (e.g. football this week, concerts), "
    "name the most relevant/closest event(s) from the catalog with their date and "
    "offer to book. "
    "When they ask about 'this event' / 'it' / 'the show' and a current event is "
    "provided below, DESCRIBE it from its title, date, venue, description and price — "
    "never say you lack details when they are given. "
    "Only if the question is clearly unrelated to events, tickets, or Tazkara "
    "(e.g. weather, math, trivia) should you politely say you can only help with "
    "events and tickets here. Never invent events, prices, or policies."
)


def _catalog_brief(db: Session) -> str:
    events = search_events(db)
    if not events:
        return "(no events currently listed)"
    return "\n".join(
        f"- {e.title} · {e.city} · {e.starts_at:%a %d %b %Y %H:%M}" for e in events
    )


def _facts(db: Session) -> str:
    return "\n\n".join(
        [ABOUT, HOW_IT_WORKS, MEMBERSHIP, CATEGORIES, PAYMENT, LANGUAGES, "Live catalog:\n" + _catalog_brief(db)]
    )


def _event_detail(db: Session, event_id: int) -> str | None:
    """A short description of one event (title, when, venue, blurb, from-price)."""

    try:
        ev = get_event_details(db, event_id)
    except Exception:
        return None
    price = db.execute(
        select(func.min(Seat.base_price)).where(Seat.event_id == event_id)
    ).scalar_one_or_none()
    parts = [f"{ev.title} — {ev.venue}, {ev.city} · {ev.starts_at:%a %d %b %Y at %H:%M}"]
    if ev.description:
        parts.append(ev.description)
    if price is not None:
        parts.append(f"Tickets from {sar_str(int(price))} (VIP / Gold / Silver / Standing).")
    return "\n".join(parts)


def answer_question(db: Session, message: str, current_event_id: int | None = None) -> str:
    """Grounded answer to a platform question (LLM if available, else rules).

    `current_event_id` is the event in the active booking, so "this event"/"it"
    resolve correctly.
    """

    current = _event_detail(db, current_event_id) if current_event_id else None
    if llm_available():
        try:
            prompt = _facts(db)
            if current:
                prompt += (
                    "\n\nThe user is currently looking at THIS event (so 'this event', "
                    "'it', 'the show' refer to it):\n" + current
                )
            reply = chat_complete(_ANSWER_SYSTEM, prompt + f"\n\nUser question: {message}")
            if reply.strip():
                return reply.strip()
        except Exception:
            pass
    return _rule_based_answer(db, message, current)


def _rule_based_answer(db: Session, message: str, current: str | None = None) -> str:
    low = (message or "").lower()

    def has(*words: str) -> bool:
        return any(w in low for w in words)

    if current and has(
        "describe", "description", "detail", "about it", "about this", "this event",
        "this show", "when is", "what time", "where is", "venue", "located", "location",
        "tell me about",
    ):
        return current

    if has("discount", "member", "membership", "loyalty", "tier"):
        return MEMBERSHIP + " Share your email and I'll apply your tier."
    if has("who", "made", "built", "implement", "created", "developed", "about you", "what are you"):
        return ABOUT
    if has("how", "work", "steps", "process"):
        return HOW_IT_WORKS
    if has("vat", "tax", "price", "prices", "cost", "how much", "fee"):
        return f"{CATEGORIES} {MEMBERSHIP.split('. ')[-1]} Tell me an event and I'll quote exact prices."
    if has("pay", "payment", "mada", "apple pay", "stc", "card"):
        return PAYMENT
    if has("refund", "cancel", "exchange", "return"):
        return "This demo doesn't process refunds yet — a refund/cancellation flow is planned. You can cancel an unconfirmed hold anytime in chat."
    if has("arabic", "english", "language", "عربي"):
        return LANGUAGES
    if has("match", "matches", "football", "concert", "theatre", "comedy", "festival", "this week", "weekend", "what's on", "whats on", "events"):
        return "Here's what's coming up:\n" + _catalog_brief(db) + "\nWant me to book any of these?"
    return (
        "I'm Tazkara — I can help you find live events and book tickets (with your "
        "member discount, a seat map, and a QR ticket). Try “what's on this weekend?”, "
        "“is there a discount?”, or name an event like “Coldplay in Riyadh”."
    )
