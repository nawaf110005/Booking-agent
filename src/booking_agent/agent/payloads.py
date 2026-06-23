"""Presentation layer — turns conversation state into the structured `AgentResponse`
payloads the UI consumes (event cards, category list, quote, seat map, confirmation).

The agents decide and act (call tools, mutate state); this module only renders the
result and asks for the next missing detail, so the orchestrator and specialists
share one source of truth for what a turn returns.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.compose import compose_reply
from booking_agent.agent.responses import infer_response_type
from booking_agent.agent.state import ConversationState
from booking_agent.db.enums import Category, MemberTier, SeatStatus
from booking_agent.db.models import Seat
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %d %b %Y, %H:%M")


def tier_enum(state: ConversationState) -> MemberTier | None:
    return MemberTier(state.tier) if state.tier else None


def first_name(email: str | None, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    if not email or "@" not in email:
        return None
    token = re.split(r"[._\-+0-9]+", email.split("@", 1)[0])[0]
    return (token[:1].upper() + token[1:].lower()) if token else None


def price_from(db: Session, event_id: int) -> str:
    cents = db.execute(
        select(func.min(Seat.base_price)).where(Seat.event_id == event_id)
    ).scalar_one_or_none()
    return sar_str(int(cents)) if cents is not None else "—"


def event_cards(db: Session, events) -> list[dict]:
    return [
        {
            "id": e.id,
            "title": e.title,
            "venue": e.venue,
            "city": e.city,
            "starts_at": e.starts_at.isoformat(),
            "when": fmt_dt(e.starts_at),  # human-readable date + time for the card
            "price_from_sar": price_from(db, e.id),
        }
        for e in events
    ]


def member_obj(member) -> dict:
    if member.is_member:
        label = f"{member.tier.value.title()} member · {member.discount_label} off · up to {member.ticket_cap}"
    else:
        label = "Guest · standard pricing · up to 4 tickets"
    return {
        "tier": member.tier.value if member.tier else None,
        "discount_label": member.discount_label,
        "ticket_cap": member.ticket_cap,
        "is_member": member.is_member,
        "label": label,
    }


def categories_payload(db: Session, event_id: int, tier: MemberTier | None) -> list[dict]:
    return [
        {
            "category": c.category.value,
            "base_sar": c.base_sar,
            "discounted_sar": c.discounted_sar,
            "available": c.available,
        }
        for c in get_categories_with_pricing(db, event_id, tier)
    ]


def quote_payload(quote) -> dict:
    return {
        "category": quote.category.value,
        "quantity": quote.quantity,
        "lines": quote.summary_lines(),
        "total_sar": sar_str(quote.total, quote.currency),
    }


def seatmap_url(state: ConversationState) -> str:
    bust = state.hold_token or state.turn
    return f"/v1/events/{state.event_id}/seatmap.png?category={state.category}&v={bust}"


def available_seats(db: Session, event_id: int, category: str, n: int = 6) -> list[str]:
    return list(
        db.execute(
            select(Seat.seat_id)
            .where(
                Seat.event_id == event_id,
                Seat.category == Category(category),
                Seat.status == SeatStatus.AVAILABLE,
            )
            .order_by(Seat.row, Seat.number)
            .limit(n)
        ).scalars().all()
    )


def blank_payload(state: ConversationState) -> dict:
    return {
        "session_id": state.session_id,
        "reply": "",
        "step": state.step,
        "suggestions": [],
        "events": None,
        "member": None,
        "categories": None,
        "quote": None,
        "seatmap_url": None,
        "hold": None,
        "confirmation": None,
        "payment": None,
    }


# Payload keys whose facts live in the structured card, not the reply text. When any
# is present the reply is a thin label, so the LLM rephraser must NOT touch it — given
# only "Please review and confirm" it would invent a whole booking (wrong seats, price,
# email). These replies stay deterministic; only plain conversational text is rephrased.
_STRUCTURED_KEYS = ("events", "member", "categories", "quote", "seatmap_url", "hold", "confirmation", "payment")


def make_payload(state: ConversationState, text: str, *, suggestions: list[str] | None = None, **extra) -> dict:
    """Build a structured turn payload (recorded to history, with the response_type
    discriminator inferred). Plain conversational replies get warmer wording via
    `compose_reply`; replies carrying structured booking data are left exact."""
    if not any(extra.get(k) for k in _STRUCTURED_KEYS):
        text = compose_reply(text)
    state.record("agent", text)
    payload = blank_payload(state)
    payload["reply"] = text
    payload["suggestions"] = suggestions or []
    payload.update(extra)
    payload["response_type"] = infer_response_type(payload)
    return payload


def booking_summary_line(event_title: str, quantity: int, category: str, seat_ids: list[str], total_str: str) -> str:
    """A deterministic, grounded one-liner built ONLY from real values (no LLM, so
    no hallucination risk) — e.g. '1× VIP (A4) for Coldplay — Music of the Spheres · 1,466.25 SAR'."""
    seats = ", ".join(seat_ids) if seat_ids else "—"
    return f"{quantity}× {str(category).title()} ({seats}) for {event_title} · {total_str}"


def confirmation_payload(db: Session, state: ConversationState, ev, quote) -> dict:
    summary = booking_summary_line(
        ev.title, quote.quantity, quote.category.value, state.seat_ids, sar_str(quote.total, quote.currency)
    )
    return make_payload(
        state,
        f"{summary}\nReview and confirm before payment:",
        quote=quote_payload(quote),
        hold={"seat_ids": state.seat_ids, "expires_at": state.hold_expires, "ttl_minutes": 10},
        confirmation={
            "event_title": ev.title,
            "when": fmt_dt(ev.starts_at),
            "venue": f"{ev.venue}, {ev.city}",
            "seats": state.seat_ids,
            "subtotal_sar": sar_str(quote.net_subtotal, quote.currency),
            "vat_sar": sar_str(quote.vat, quote.currency),
            "total_sar": sar_str(quote.total, quote.currency),
            "expires_at": state.hold_expires,
        },
        suggestions=["confirm", "cancel"],
    )


def present_next(db: Session, state: ConversationState, ev, member) -> dict:
    """Render the card that asks for the first still-missing booking detail.

    Called by the orchestrator after the specialists have acted: whatever they
    couldn't fill (because the user hasn't said it yet) becomes the next ask.
    """
    tier = tier_enum(state)

    # Email / identity.
    if not state.email:
        state.step = S.NEED_EMAIL
        return make_payload(
            state,
            f"Great — **{ev.title}** at {ev.venue}, {ev.city} ({fmt_dt(ev.starts_at)}).\n"
            "What's your email? I'll check for a member discount.",
            suggestions=["nawaf@example.com", "guest@example.com"],
        )

    # Category.
    if not state.category:
        state.step = S.CATEGORY_SELECTION
        who = f"{state.name}, you" if state.name else "You"
        member_line = (
            f"{who}'re a **{member.tier.value.title()}** member — {member.discount_label} off, "
            f"up to {member.ticket_cap} tickets.\n"
            if member.is_member
            else f"{who}'re booking as a guest (standard pricing, up to 4 tickets).\n"
        )
        return make_payload(
            state,
            member_line + "Which category would you like?",
            member=member_obj(member),
            categories=categories_payload(db, state.event_id, tier),
            suggestions=[c.category.value for c in get_categories_with_pricing(db, state.event_id, tier)],
        )

    # Quantity.
    if not state.quantity:
        state.step = S.NEED_QUANTITY
        return make_payload(
            state,
            f"How many **{state.category.title()}** tickets? (up to {state.ticket_cap})",
            suggestions=[str(n) for n in dict.fromkeys((2, 4, state.ticket_cap)) if n <= state.ticket_cap],
        )

    # Seats (quote is ready; show the map).
    quote = compute_quote(db, state.event_id, state.category, state.quantity, tier)
    if not state.hold_token:
        state.step = S.SEAT_SELECTION
        seats = available_seats(db, state.event_id, state.category, state.quantity)
        return make_payload(
            state,
            f"Here's the **{state.category.title()}** seat map. Type {state.quantity} seat ID(s) like "
            + ", ".join(seats or ["G3"])
            + ".",
            quote=quote_payload(quote),
            seatmap_url=seatmap_url(state),
            suggestions=[", ".join(seats)] if seats else [],
        )

    # Seats held → confirmation gate.
    return confirmation_payload(db, state, ev, quote)
