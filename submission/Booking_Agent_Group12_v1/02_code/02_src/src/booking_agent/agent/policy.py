"""The booking agent's orchestrator: one turn in, one structured reply out.

A deterministic state machine over the F001 tools. It advances as far as the
user's message allows and asks for the first missing slot. The payment URL is
issued ONLY after an explicit confirm from AWAITING_CONFIRMATION — the
non-negotiable HITL gate (Constitution I).
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.answer import answer_question
from booking_agent.agent.extract import heuristic_extract
from booking_agent.agent.llm import llm_available, llm_extract
from booking_agent.agent import guardrails, observability
from booking_agent.agent.compose import compose_reply
from booking_agent.agent.interests import detect_interest, filter_by_interest
from booking_agent.agent.profiles import PREFERENCES
from booking_agent.agent.sentiment import classify_sentiment
from booking_agent.agent.responses import infer_response_type
from booking_agent.agent.memory import MEMORY
from booking_agent.agent.state import ConversationState
from booking_agent.db.base import ensure_aware, utcnow
from booking_agent.db.enums import BookingStatus, Category, MemberTier, SeatStatus
from booking_agent.db.models import Booking, Seat
from booking_agent.temporal import when_label, when_range
from booking_agent.tools.booking import create_booking_from_hold
from booking_agent.tools.errors import CapExceededError, SeatUnavailableError, ToolError
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.holds import place_seat_hold, release_seat_hold
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing

GREETING_TEXT = (
    "Hi! I'm your booking assistant 🎫\n"
    "Tell me what you'd like to see — e.g. \"Coldplay in Riyadh\" — or pick one below."
)


# --------------------------------------------------------------------------- #
# Reply + payload builders
# --------------------------------------------------------------------------- #

def _reply(state: ConversationState, text: str, *, suggestions: list[str] | None = None, **extra) -> dict:
    text = compose_reply(text)  # warmer wording when dynamic replies are on; else unchanged
    state.record("agent", text)
    payload = {
        "session_id": state.session_id,
        "reply": text,
        "step": state.step,
        "suggestions": suggestions or [],
        "events": None,
        "member": None,
        "categories": None,
        "quote": None,
        "seatmap_url": None,
        "hold": None,
        "confirmation": None,
        "payment": None,
    }
    payload.update(extra)
    payload["response_type"] = infer_response_type(payload)
    return payload


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %d %b %Y, %H:%M")


def _price_from(db: Session, event_id: int) -> str:
    cents = db.execute(
        select(func.min(Seat.base_price)).where(Seat.event_id == event_id)
    ).scalar_one_or_none()
    return sar_str(int(cents)) if cents is not None else "—"


def _event_cards(db: Session, events) -> list[dict]:
    return [
        {
            "id": e.id,
            "title": e.title,
            "venue": e.venue,
            "city": e.city,
            "starts_at": e.starts_at.isoformat(),
            "price_from_sar": _price_from(db, e.id),
        }
        for e in events
    ]


def _member_obj(member) -> dict:
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


def _categories_payload(db: Session, event_id: int, tier: MemberTier | None) -> list[dict]:
    out = []
    for c in get_categories_with_pricing(db, event_id, tier):
        out.append(
            {
                "category": c.category.value,
                "base_sar": c.base_sar,
                "discounted_sar": c.discounted_sar,
                "available": c.available,
            }
        )
    return out


def _quote_payload(quote) -> dict:
    return {
        "category": quote.category.value,
        "quantity": quote.quantity,
        "lines": quote.summary_lines(),
        "total_sar": sar_str(quote.total, quote.currency),
    }


def _seatmap_url(state: ConversationState) -> str:
    bust = state.hold_token or state.turn
    return f"/v1/events/{state.event_id}/seatmap.png?category={state.category}&v={bust}"


def _tier_enum(state: ConversationState) -> MemberTier | None:
    return MemberTier(state.tier) if state.tier else None


def _available_seats(db: Session, event_id: int, category: str, n: int = 6) -> list[str]:
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


def _first_name(email: str | None, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    if not email or "@" not in email:
        return None
    token = re.split(r"[._\-+0-9]+", email.split("@", 1)[0])[0]
    return (token[:1].upper() + token[1:].lower()) if token else None


def _next_need(state: ConversationState) -> str:
    if state.event_id is None:
        return "help them choose an event"
    if not state.email:
        return "ask for their email to apply any member discount"
    if not state.category:
        return "ask which seat category they'd like"
    if not state.quantity:
        return "ask how many tickets"
    if not state.hold_token:
        return "ask them to pick seats"
    if state.step == S.AWAITING_CONFIRMATION:
        return "ask them to confirm the summary before payment"
    return "continue the booking"


def _step_suggestions(state: ConversationState) -> list[str]:
    if state.event_id is None:
        return ["What's on this weekend?", "Coldplay in Riyadh", "Is there a discount?"]
    if not state.email:
        return ["nawaf@example.com", "How do discounts work?"]
    if not state.category:
        return ["VIP", "Gold", "Silver", "Standing"]
    if not state.quantity:
        return [str(n) for n in dict.fromkeys((2, 4, state.ticket_cap)) if n <= state.ticket_cap]
    if state.step == S.AWAITING_CONFIRMATION:
        return ["confirm", "cancel"]
    return ["Pick my seats", "What's the total?", "cancel"]


def _context(state: ConversationState) -> dict:
    if state.is_member and state.tier:
        tier_label = f"{state.tier.title()} member"
    elif state.email:
        tier_label = "guest (standard pricing)"
    else:
        tier_label = None
    return {"name": state.name, "tier_label": tier_label,
            "step": state.step, "needs": _next_need(state)}


def _converse(db: Session, state: ConversationState, message: str) -> dict:
    """Answer a question / chit-chat at any step (personalised), keeping state."""
    reply = answer_question(db, message, state.event_id, context=_context(state))
    return _reply(state, reply, suggestions=_step_suggestions(state))


# Steps where we're waiting on one specific slot from the user (used by the anti-loop guard).
_SLOT_STEPS = (S.NEED_EMAIL, S.CATEGORY_SELECTION, S.NEED_QUANTITY, S.SEAT_SELECTION)


def _stall_help(db: Session, state: ConversationState) -> dict:
    """Escalated, bilingual prompt when the user is stuck at a slot step and we
    couldn't parse their last couple of messages — avoids repeating verbatim."""
    if state.step == S.NEED_EMAIL:
        return _reply(
            state,
            "I just need your email to check for a member discount — type it like "
            "name@example.com.\nأرسل بريدك الإلكتروني (مثل name@example.com) لأطبّق خصم العضوية.",
            suggestions=["nawaf@example.com", "guest@example.com"],
        )
    if state.step == S.CATEGORY_SELECTION:
        tier = _tier_enum(state)
        return _reply(
            state,
            "Which seat category would you like — VIP, Gold, Silver, or Standing?\n"
            "أي فئة تفضّل: VIP أو ذهبي أو فضي أو واقف؟",
            categories=_categories_payload(db, state.event_id, tier),
            suggestions=[c.category.value for c in get_categories_with_pricing(db, state.event_id, tier)],
        )
    if state.step == S.NEED_QUANTITY:
        return _reply(
            state,
            f"How many tickets? Just send a number (up to {state.ticket_cap}).\n"
            f"كم تذكرة تريد؟ أرسل رقمًا (حتى {state.ticket_cap}).",
            suggestions=[str(n) for n in dict.fromkeys((2, 4, state.ticket_cap)) if n <= state.ticket_cap],
        )
    # SEAT_SELECTION
    seats = _available_seats(db, state.event_id, state.category, state.quantity) if state.category else []
    example = ", ".join(seats) if seats else "G3"
    return _reply(
        state,
        f"Pick {state.quantity} seat(s) by typing their IDs, e.g. {example}.\n"
        f"اختر {state.quantity} مقعدًا بكتابة الرموز، مثل {example}.",
        seatmap_url=_seatmap_url(state),
        suggestions=[", ".join(seats)] if seats else [],
    )


# --------------------------------------------------------------------------- #
# Main turn handler
# --------------------------------------------------------------------------- #

def respond(db: Session, state: ConversationState, message: str) -> dict:
    state.turn += 1
    state.record("user", message)
    entry_step = state.step

    params = heuristic_extract(message, state.step)
    heuristic_intent = params.intent
    if llm_available():
        llm_params = llm_extract(message)
        if llm_params is not None:
            params = params.merge(llm_params)
    # The heuristic's strong intents (ask/cancel/confirm) are reliable signals;
    # don't let the LLM's classification downgrade a question into a booking turn.
    if heuristic_intent in ("ask", "cancel", "confirm"):
        params.intent = heuristic_intent
    state.sentiment = classify_sentiment(message)
    observability.log_tool(
        state.session_id, "nlu_extract", turn=state.turn,
        intent=params.intent, event_query=params.event_query,
        sentiment=state.sentiment, used_llm=llm_available(),
    )

    # --- Cancel: release any hold and step back to seat selection ---------- #
    if params.intent == "cancel" and state.step in (S.AWAITING_CONFIRMATION, S.SEAT_SELECTION, S.PAYMENT):
        if state.hold_token:
            release_seat_hold(db, state.hold_token)
        state.hold_token = state.hold_expires = None
        state.seat_ids = []
        state.booking_id = None
        state.step = S.SEAT_SELECTION
        return _reply(
            state,
            "No problem — I released those seats. Pick different seats, or say 'cancel' again to start over.",
            seatmap_url=_seatmap_url(state),
            suggestions=_available_seats(db, state.event_id, state.category, 4) if state.event_id and state.category else [],
        )

    # --- Conversational layer: answer questions / chit-chat at ANY step, then keep
    #     going. Personalised; broadened to greetings/small talk when the LLM is on. #
    if params.intent == "ask" or (llm_available() and params.intent in ("greet", "smalltalk")):
        return _converse(db, state, message)

    # --- Anti-loop: if we're mid-booking at a slot step and couldn't parse anything
    #     usable two turns running, escalate to a clearer bilingual hint instead of
    #     repeating the identical question. ------------------------------------ #
    nothing_parsed = params.intent is None and not any([
        params.email, params.category, params.quantity, params.seat_ids,
        params.event_id, params.event_query, params.when, params.city,
    ])
    if nothing_parsed and entry_step in _SLOT_STEPS:
        state.stall_count += 1
    else:
        state.stall_count = 0
    if state.stall_count >= 2 and entry_step in _SLOT_STEPS:
        return _stall_help(db, state)

    # --- Post-completion: a finished booking can start over or just chat. -- #
    if state.step == S.CONFIRMED:
        low = message.lower()
        wants_new = bool(
            params.event_id or params.event_query or params.when
            or params.intent == "browse" or "book" in low or "another" in low
        )
        if wants_new:
            kept_email = state.email
            state.event_id = state.category = state.quantity = None
            state.seat_ids = []
            state.hold_token = state.hold_expires = state.booking_id = None
            state.last_query = None
            state.step = S.GREETING
            state.email = kept_email
            # fall through to resolve the new request
        else:
            return _reply(
                state,
                "🎫 Enjoy the show! I can book you another event or answer questions — just ask.",
                suggestions=["What's on this weekend?", "Book another event", "Is there a discount?"],
            )

    # --- Discovery / browse the catalog (optionally filtered by time) ------ #
    if state.event_id is None and params.intent == "browse":
        state.step = S.EVENT_SELECTION
        # Learn what they're into (this turn or from their saved profile) and use it.
        interest = detect_interest(message)
        if interest and interest not in state.interests:
            state.interests.append(interest)
            PREFERENCES.add(state.email, interest)
        known = state.interests or PREFERENCES.get(state.email)
        has_filter = bool(params.when or params.city or params.event_query or known)
        if not has_filter:
            # Don't dump the whole catalog — find out what they like first.
            return _reply(
                state,
                "Happy to help you find something! What are you into — concerts, sports, "
                "comedy, or tech conferences? Any city or date in mind?",
                suggestions=["Concerts", "Sports", "Comedy", "This weekend"],
            )
        if params.when:
            rng = when_range(params.when, utcnow()) or (None, None)
            date_from, date_to = rng
            results = filter_by_interest(
                search_events(db, params.event_query, params.city, date_from=date_from, date_to=date_to),
                known,
            )
            label = when_label(params.when)
            if results:
                return _reply(
                    state,
                    f"Here's what's on {label} ({date_from:%a %d %b}–{date_to:%a %d %b}):",
                    events=_event_cards(db, results),
                    suggestions=[r.title.split(" — ")[0] for r in results[:3]],
                )
            if params.event_query:
                nearest = search_events(db, params.event_query, params.city)
                if nearest:
                    return _reply(
                        state,
                        f"Nothing matching that {label}. The nearest is "
                        f"{nearest[0].title} on {nearest[0].starts_at:%a %d %b}:",
                        events=_event_cards(db, nearest[:3]),
                        suggestions=[r.title.split(" — ")[0] for r in nearest[:3]],
                    )
            return _reply(
                state,
                f"I don't have anything {label} — here's what's coming up instead:",
                events=_event_cards(db, search_events(db)[:6]),
                suggestions=["Coldplay", "Riyadh Derby", "Soundstorm"],
            )
        # Filtered by interest / city / query (no time window).
        results = filter_by_interest(
            search_events(db, params.event_query, params.city) or search_events(db), known
        )
        headline = f"Some {known[0]} picks for you:" if known else "Here's what's on:"
        return _reply(
            state,
            headline,
            events=_event_cards(db, results[:6]),
            suggestions=[r.title.split(" — ")[0] for r in results[:3]],
        )

    # --- 1. Resolve the event -------------------------------------------- #
    if state.event_id is None:
        if params.event_id is not None:
            try:
                ev = get_event_details(db, params.event_id)
                state.event_id = ev.id
            except ToolError:
                pass

        if state.event_id is None:
            query = params.event_query or state.last_query
            browse = params.intent == "browse"
            if query or browse:
                results = [] if browse and not query else search_events(db, query or "", params.city)
                if browse and not query:
                    results = search_events(db)
                if query:
                    state.last_query = query
                if len(results) == 1:
                    state.event_id = results[0].id
                elif len(results) == 0:
                    catalog = search_events(db)
                    state.step = S.EVENT_SELECTION
                    return _reply(
                        state,
                        (f"I couldn't find anything for “{query}”. Here's what's on right now:"
                         if query else "I couldn't find that one. Here's what's on right now:"),
                        events=_event_cards(db, catalog),
                        suggestions=["Coldplay", "Riyadh Derby", "Soundstorm"],
                    )
                else:
                    state.step = S.EVENT_SELECTION
                    cities = sorted({e.city for e in results})
                    return _reply(
                        state,
                        "I found a few matches — which one?",
                        events=_event_cards(db, results),
                        suggestions=cities,
                    )

    if state.event_id is None:
        # With the LLM on, anything we couldn't turn into a booking action — including
        # off-topic requests like "write me code" — gets a clear, in-character reply
        # instead of a canned greeting that ignores the user.
        if llm_available():
            return _converse(db, state, message)
        # Offline: greeting / discovery with event cards.
        catalog = search_events(db)[:4]
        state.step = S.EVENT_SELECTION
        return _reply(
            state,
            GREETING_TEXT,
            events=_event_cards(db, catalog),
            suggestions=["Coldplay in Riyadh", "Riyadh Derby", "What's on this weekend?"],
        )

    ev = get_event_details(db, state.event_id)

    # --- 2. Identify the buyer (email -> membership) --------------------- #
    if params.email:
        member = lookup_member_by_email(db, params.email)
        state.email = member.email
        state.name = _first_name(member.email, state.name)
        state.tier = member.tier.value if member.tier else None
        state.is_member = member.is_member
        state.ticket_cap = member.ticket_cap
        observability.log_tool(
            state.session_id, "lookup_member", turn=state.turn,
            email=member.email, tier=state.tier, is_member=member.is_member,
        )

    if not state.email:
        state.step = S.NEED_EMAIL
        return _reply(
            state,
            f"Great — **{ev.title}** at {ev.venue}, {ev.city} ({_fmt_dt(ev.starts_at)}).\n"
            "What's your email? I'll check for a member discount.",
            suggestions=["nawaf@example.com", "guest@example.com"],
        )

    member = lookup_member_by_email(db, state.email)
    tier = _tier_enum(state)

    # --- 3. Category ----------------------------------------------------- #
    if params.category:
        state.category = params.category

    if not state.category:
        state.step = S.CATEGORY_SELECTION
        who = f"{state.name}, you" if state.name else "You"
        member_line = (
            f"{who}'re a **{member.tier.value.title()}** member — {member.discount_label} off, up to {member.ticket_cap} tickets.\n"
            if member.is_member
            else f"{who}'re booking as a guest (standard pricing, up to 4 tickets).\n"
        )
        return _reply(
            state,
            member_line + "Which category would you like?",
            member=_member_obj(member),
            categories=_categories_payload(db, state.event_id, tier),
            suggestions=[c.category.value for c in get_categories_with_pricing(db, state.event_id, tier)],
        )

    # --- 4. Quantity (enforce the tier cap) ------------------------------ #
    if params.quantity is not None:
        if guardrails.exceeds_cap(params.quantity, state.ticket_cap):
            state.step = S.NEED_QUANTITY
            return _reply(
                state,
                f"As {'a ' + member.tier.value.title() + ' member' if member.is_member else 'a guest'} you can book up to "
                f"**{state.ticket_cap}** tickets per booking. How many would you like (max {state.ticket_cap})?",
                suggestions=[str(n) for n in (2, 4, state.ticket_cap) if n <= state.ticket_cap],
            )
        state.quantity = params.quantity

    if not state.quantity:
        state.step = S.NEED_QUANTITY
        return _reply(
            state,
            f"How many **{state.category.title()}** tickets? (up to {state.ticket_cap})",
            suggestions=[str(n) for n in dict.fromkeys((2, 4, state.ticket_cap)) if n <= state.ticket_cap],
        )

    # We now have event + email + category + quantity → quote.
    try:
        quote = compute_quote(db, state.event_id, state.category, state.quantity, tier)
    except CapExceededError as exc:
        state.quantity = None
        state.step = S.NEED_QUANTITY
        return _reply(state, str(exc) + " How many would you like?")
    observability.log_tool(
        state.session_id, "compute_quote", turn=state.turn, category=state.category,
        quantity=state.quantity, total_sar=sar_str(quote.total, quote.currency),
    )

    # --- 5. Seats + atomic hold ----------------------------------------- #
    if not state.hold_token:
        if params.seat_ids and len(params.seat_ids) == state.quantity:
            try:
                hold = place_seat_hold(db, state.event_id, params.seat_ids, state.email)
            except (SeatUnavailableError, ToolError) as exc:
                state.step = S.SEAT_SELECTION
                return _reply(
                    state,
                    f"Sorry — {exc} Please pick {state.quantity} other seat(s).",
                    quote=_quote_payload(quote),
                    seatmap_url=_seatmap_url(state),
                    suggestions=_available_seats(db, state.event_id, state.category, 4),
                )
            state.seat_ids = list(hold.seat_ids)
            state.hold_token = hold.token
            state.hold_expires = hold.expires_at.isoformat()
            state.step = S.AWAITING_CONFIRMATION
            observability.log_tool(state.session_id, "place_seat_hold", turn=state.turn, seats=state.seat_ids)
            observability.log_transition(state.session_id, entry_step, S.AWAITING_CONFIRMATION, turn=state.turn)
            return _confirmation_reply(db, state, ev, quote)

        # Need seats: show the map.
        if params.seat_ids and len(params.seat_ids) != state.quantity:
            note = f"Please pick exactly **{state.quantity}** seat(s) — you gave {len(params.seat_ids)}.\n"
        else:
            note = ""
        state.step = S.SEAT_SELECTION
        return _reply(
            state,
            note
            + f"Here's the **{state.category.title()}** seat map. Type {state.quantity} seat ID(s) like "
            + ", ".join(_available_seats(db, state.event_id, state.category, state.quantity) or ["G3"])
            + ".",
            quote=_quote_payload(quote),
            seatmap_url=_seatmap_url(state),
            suggestions=[", ".join(_available_seats(db, state.event_id, state.category, state.quantity))]
            if _available_seats(db, state.event_id, state.category, state.quantity)
            else [],
        )

    # --- 6. HITL confirmation ------------------------------------------- #
    if state.step == S.AWAITING_CONFIRMATION:
        # Has the hold expired?
        if state.hold_expires and ensure_aware(datetime.fromisoformat(state.hold_expires)) <= utcnow():
            state.hold_token = state.hold_expires = None
            state.seat_ids = []
            state.step = S.SEAT_SELECTION
            return _reply(
                state,
                "⏰ Your 10-minute hold expired. Let's pick seats again.",
                seatmap_url=_seatmap_url(state),
                suggestions=_available_seats(db, state.event_id, state.category, state.quantity),
            )

        if params.intent == "confirm":
            assert guardrails.can_issue_payment(state.step)  # HITL gate (Constitution I)
            booking = create_booking_from_hold(
                db,
                email=state.email,
                event_id=state.event_id,
                category=state.category,
                quantity=state.quantity,
                seat_ids=state.seat_ids,
                hold_token=state.hold_token,
                tier=tier,
            )
            state.booking_id = booking.id
            state.step = S.PAYMENT
            observability.log_tool(state.session_id, "create_booking", turn=state.turn,
                                   booking_id=booking.id, total_sar=sar_str(booking.total, booking.currency))
            observability.log_transition(state.session_id, entry_step, S.PAYMENT, turn=state.turn)
            MEMORY.record(state.email, f"{ev.title} — {state.quantity}× {state.category}")
            return _reply(
                state,
                "Confirmed! ✅ Complete your payment to get your ticket.",
                payment={"booking_id": booking.id, "total_sar": sar_str(booking.total, booking.currency)},
            )

        # Re-show the summary until they confirm.
        return _confirmation_reply(db, state, ev, quote)

    # --- 7. Payment pending / completed --------------------------------- #
    if state.step == S.PAYMENT and state.booking_id:
        booking = db.get(Booking, state.booking_id)
        if booking is not None and booking.status == BookingStatus.PAID:
            state.step = S.CONFIRMED
            return _reply(
                state,
                f"You're all set — your booking for {ev.title} is paid and your ticket "
                "is issued 🎫. Want to book anything else?",
                suggestions=["What's on this weekend?", "Book another event"],
            )
        return _reply(
            state,
            "Tap **Pay now** to complete your booking (sandbox).",
            payment={"booking_id": state.booking_id, "total_sar": sar_str(quote.total, quote.currency)},
        )

    # Fallback: chat naturally when the LLM is on; else ask them to rephrase.
    if llm_available():
        return _converse(db, state, message)
    return _reply(state, "Could you rephrase that?")


def _confirmation_reply(db: Session, state: ConversationState, ev, quote) -> dict:
    return _reply(
        state,
        "Please review and confirm before payment:",
        quote=_quote_payload(quote),
        hold={
            "seat_ids": state.seat_ids,
            "expires_at": state.hold_expires,
            "ttl_minutes": 10,
        },
        confirmation={
            "event_title": ev.title,
            "when": _fmt_dt(ev.starts_at),
            "venue": f"{ev.venue}, {ev.city}",
            "seats": state.seat_ids,
            "subtotal_sar": sar_str(quote.net_subtotal, quote.currency),
            "vat_sar": sar_str(quote.vat, quote.currency),
            "total_sar": sar_str(quote.total, quote.currency),
            "expires_at": state.hold_expires,
        },
        suggestions=["confirm", "cancel"],
    )
