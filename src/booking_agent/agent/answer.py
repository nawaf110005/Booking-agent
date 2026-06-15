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
from booking_agent.agent.rag import retrieve
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
    "You are Tazkara, a warm, witty event-ticketing concierge for live events in "
    "Saudi Arabia. Talk like a helpful friend, not a form: greet back, make a little "
    "small talk, give honest opinions and recommendations when asked (e.g. which seat "
    "category is best value, what's fun this weekend), and answer questions about "
    "events, prices, membership, payment, and how booking works — using ONLY the facts "
    "and live catalog provided. "
    "PERSONALISE: if the CONTEXT below gives the user's name or membership tier, use "
    "them naturally (e.g. 'Sure, Nawaf —'). "
    "Be concise (1-3 sentences), friendly and specific. You're in the middle of helping "
    "them book: after you answer, gently nudge toward the next step shown in CONTEXT "
    "(share an email, pick a category, choose seats, confirm) — invite, don't pester. "
    "When they ask about 'this event' / 'it' / 'the show' and a current event is provided, "
    "describe it from its title, date, venue, description and price — never say you lack "
    "details that are given. "
    "If they ask you to do something outside ticketing — write code, do homework, "
    "general tasks — tell them clearly and kindly that that isn't something you can do "
    "(you're a ticket-booking concierge), then offer to help them find an event. NEVER "
    "ignore the request or reply with a generic greeting. For light off-topic chat "
    "(weather, a joke), answer briefly and warmly, then steer back to tickets. Never "
    "invent events, prices, seats, or policies — if you don't have it, say so plainly."
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


def _context_block(ctx: dict) -> str:
    return (
        f"User name: {ctx.get('name') or 'unknown yet'}\n"
        f"Membership: {ctx.get('tier_label') or 'not identified yet'}\n"
        f"Current booking step: {ctx.get('step') or 'just starting'}\n"
        f"Next thing to get from them: {ctx.get('needs') or 'help them pick an event'}"
    )


def answer_question(db: Session, message: str, current_event_id: int | None = None,
                    context: dict | None = None) -> str:
    """Conversational, personalised reply (LLM if available, else rules).

    `current_event_id` resolves "this event"/"it"; `context` carries the user's
    name, tier, current step and what's needed next so the reply is personal and
    nudges the booking forward.
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
            if context:
                prompt += "\n\nCONTEXT (use to personalise + steer):\n" + _context_block(context)
            kb = retrieve(message, k=2)
            if kb:
                prompt += "\n\nKnowledge base (use if relevant, don't contradict):\n- " + "\n- ".join(kb)
            reply = chat_complete(_ANSWER_SYSTEM, prompt + f"\n\nUser message: {message}")
            if reply.strip():
                return reply.strip()
        except Exception:
            pass
    return _rule_based_answer(db, message, current)


def _rule_based_answer(db: Session, message: str, current: str | None = None) -> str:
    low = (message or "").lower()

    def has(*words: str) -> bool:
        return any(w in low for w in words)

    first = low.strip().split()[0] if low.strip() else ""
    if first in {"hi", "hey", "hello", "yo", "salam", "hala", "هلا", "اهلا", "مرحبا", "سلام"} or has(
        "good morning", "good evening", "good afternoon"
    ):
        return "Hey! I'm Tazkara 🎫 — I find live events and book tickets. What are you in the mood for?"
    if has("thank", "thanks", "thx", "شكرا"):
        return "Anytime! Want to find an event or check your member discount?"
    if has("how are you", "how r u", "how are u", "how's it going", "what's up", "whats up", "كيفك"):
        return "Doing great and ready to get you tickets! What would you like to see?"

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
    # Venue/FAQ knowledge base (parking, gates, accessibility, prohibited items) — RAG.
    hits = retrieve(message, k=1, min_overlap=1)
    if hits:
        return hits[0]
    return (
        "I'm Tazkara — I can help you find live events and book tickets (with your "
        "member discount, a seat map, and a QR ticket). Try “what's on this weekend?”, "
        "“is there a discount?”, or name an event like “Coldplay in Riyadh”."
    )
