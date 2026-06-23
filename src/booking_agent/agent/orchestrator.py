"""Multi-agent orchestrator — the coordinator that drives the booking team.

Replaces the old hand-coded state machine. One turn in, one structured reply out.
The orchestrator:

  * parses intent, records sentiment, logs the NLU step (observability);
  * routes questions/chit-chat to the **concierge** (grounded Q&A);
  * handles discovery (browse the catalog by interest/time);
  * runs the booking team — **catalog → membership → pricing → seating
    specialists** (`specialists.py`), each an LLM tool loop over its own tools —
    handing off as each phase completes;
  * keeps the dangerous action in code: booking/payment happens ONLY after an
    explicit user "confirm" at the human-in-the-loop gate (Constitution I).

The specialists' "brain" is injected: the real LLM (`tool_agent.default_complete`)
when a key is configured, else the deterministic `offline_brain` so the demo and
the test-suite run with no network. Same agents, swappable brain.
"""

from __future__ import annotations

import contextlib
from datetime import datetime

from sqlalchemy.orm import Session

from booking_agent.agent import guardrails, observability
from booking_agent.agent import state as S
from booking_agent.agent.answer import answer_question
from booking_agent.agent.extract import heuristic_extract
from booking_agent.agent.interests import (
    GENRE_LABELS,
    detect_interest,
    events_in_genre,
    filter_by_interest,
)
from booking_agent.agent.llm import infer_genre, llm_available, llm_extract
from booking_agent.agent.memory import MEMORY
from booking_agent.agent.offline_brain import make_offline_brain
from booking_agent.agent.payloads import (
    booking_summary_line,
    confirmation_payload,
    event_cards,
    make_payload,
    present_next,
    seatmap_url,
    tier_enum,
)
from booking_agent.agent.profiles import PREFERENCES
from booking_agent.agent.sentiment import classify_sentiment
from booking_agent.agent.specialists import CATALOG, MEMBERSHIP, PRICING, SEATING, run_specialist
from booking_agent.agent.state import ConversationState
from booking_agent.db.base import ensure_aware, utcnow
from booking_agent.db.enums import BookingStatus
from booking_agent.db.models import Booking
from booking_agent.temporal import when_label, when_range
from booking_agent.tools.booking import create_booking_from_hold
from booking_agent.tools.errors import ToolError
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.holds import release_seat_hold
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote

GREETING_TEXT = (
    "Hi! I'm your booking assistant 🎫\n"
    "Tell me what you'd like to see — e.g. \"Coldplay in Riyadh\" — or pick one below."
)


# --------------------------------------------------------------------------- #
# Brain selection + small context helpers
# --------------------------------------------------------------------------- #

def _brain(state: ConversationState, params):
    """The `complete` the specialists call: the real LLM when keyed, else the
    deterministic offline brain (so no-key demos and tests still book)."""
    if llm_available():
        from booking_agent.agent import tool_agent  # deferred (imports openai lazily)

        return tool_agent.default_complete
    return make_offline_brain(state, params)


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
    if state.step == S.PAYMENT:
        return ["What's the total?", "cancel"]
    if state.step == S.CONFIRMED:                       # already booked — offer what's next
        return ["What's on this weekend?", "Book another event", "Is there a discount?"]
    return ["What's the total?", "cancel"]              # seat selection


def _context(state: ConversationState) -> dict:
    if state.is_member and state.tier:
        tier_label = f"{state.tier.title()} member"
    elif state.email:
        tier_label = "guest (standard pricing)"
    else:
        tier_label = None
    return {"name": state.name, "tier_label": tier_label, "step": state.step,
            "needs": _next_need(state), "turn": state.turn}


def _converse(db: Session, state: ConversationState, message: str) -> dict:
    """Concierge: answer a question / chit-chat at any step, personalised, keeping state."""
    reply = answer_question(db, message, state.event_id, context=_context(state))
    return make_payload(state, reply, suggestions=_step_suggestions(state))


def _reset_booking(state: ConversationState) -> None:
    state.event_id = state.category = state.quantity = None
    state.seat_ids = []
    state.hold_token = state.hold_expires = state.booking_id = None
    state.last_query = None
    state.step = S.GREETING


_CHANGE_WORDS = ("change", "edit", "modify", "different", "switch", "amend", "redo",
                 "wrong", "mistake", "instead", "swap", "adjust", "update")


def _is_change_request(message: str) -> bool:
    """True if the user is asking to alter the current order (e.g. 'can I change it?')."""
    low = (message or "").lower()
    return any(w in low for w in _CHANGE_WORDS)


def _is_delivery_request(message: str, step: str) -> bool:
    """True if the user is asking us to deliver/send the ticket to a channel we don't
    support (email, SMS, WhatsApp) — e.g. 'can you send it to my email'. We answer
    honestly rather than dodging. Email *entry* (just typing an address) is excluded."""
    low = (message or "").lower()
    channel = any(w in low for w in ("email", "e-mail", "gmail", "whatsapp", "sms", "inbox")) or "text me" in low
    sendish = any(w in low for w in ("send", "mail", "forward", "deliver"))
    ticket_noun = any(w in low for w in ("ticket", "qr", "receipt", "confirmation", "copy", "pdf"))
    return (channel and (sendish or ticket_noun or step in (S.PAYMENT, S.CONFIRMED))) or (sendish and ticket_noun)


def _wants_new_booking(params, message: str) -> bool:
    """The user is asking to book a different/another event (used after completion)."""
    low = (message or "").lower()
    return bool(params.event_id or params.event_query or params.when
                or params.intent == "browse" or "book" in low or "another" in low)


def _switch_to(state: ConversationState, event_id: int, params) -> None:
    """Point the booking at a new event, clearing the downstream slots (keep identity)."""
    state.event_id = event_id
    state.category = state.quantity = None
    state.seat_ids = []
    state.last_query = params.event_query


def _maybe_switch_event(db: Session, state: ConversationState, params) -> dict | None:
    """Before any seats are held, a newly named *different* event replaces the current
    selection (e.g. "nvm, I want the derby"). Returns a disambiguation payload if the
    new name is ambiguous, else None (caller continues the flow with the switched event)."""
    if state.event_id is None or state.hold_token or not (params.event_id or params.event_query):
        return None
    if params.event_id is not None:
        if params.event_id != state.event_id:
            with contextlib.suppress(ToolError):
                _switch_to(state, get_event_details(db, params.event_id).id, params)
        return None
    matches = search_events(db, params.event_query, params.city)
    if not matches or state.event_id in [m.id for m in matches]:
        return None  # nothing found, or they re-named the current event → no switch
    if len(matches) == 1:
        _switch_to(state, matches[0].id, params)
        return None
    # Ambiguous *different* event → reset and let them pick.
    state.event_id = state.category = state.quantity = None
    state.seat_ids = []
    state.last_query = params.event_query
    return _present_event_choice(db, state, params)


# --------------------------------------------------------------------------- #
# Discovery (browse the catalog) — deterministic presentation
# --------------------------------------------------------------------------- #

def _discover(db: Session, state: ConversationState, params, message: str) -> dict:
    state.step = S.EVENT_SELECTION
    interest = detect_interest(message)
    if interest and interest not in state.interests:
        state.interests.append(interest)
        PREFERENCES.add(state.email, interest)
    known = state.interests or PREFERENCES.get(state.email)
    # A named act/event we don't carry (e.g. "dua lipa events?") — offer a similar
    # genre instead of dumping the whole catalog, same as the unknown-event flow.
    if params.event_query and not search_events(db, params.event_query, params.city):
        offer = _offer_similar(db, state, params.event_query)
        if offer is not None:
            return offer
    has_filter = bool(params.when or params.city or params.event_query or known)
    if not has_filter:
        return make_payload(
            state,
            "Happy to help you find something! What are you into — concerts, sports, "
            "comedy, or tech conferences? Any city or date in mind?",
            suggestions=["Concerts", "Sports", "Comedy", "This weekend"],
        )
    if params.when:
        rng = when_range(params.when, utcnow()) or (None, None)
        date_from, date_to = rng
        results = filter_by_interest(
            search_events(db, params.event_query, params.city, date_from=date_from, date_to=date_to), known
        )
        label = when_label(params.when)
        if results:
            return make_payload(
                state, f"Here's what's on {label} ({date_from:%a %d %b}–{date_to:%a %d %b}):",
                events=event_cards(db, results),
                suggestions=[r.title.split(" — ")[0] for r in results[:3]],
            )
        if params.event_query:
            nearest = search_events(db, params.event_query, params.city)
            if nearest:
                return make_payload(
                    state, f"Nothing matching that {label}. The nearest is "
                    f"{nearest[0].title} on {nearest[0].starts_at:%a %d %b}:",
                    events=event_cards(db, nearest[:3]),
                    suggestions=[r.title.split(" — ")[0] for r in nearest[:3]],
                )
        return make_payload(
            state, f"I don't have anything {label} — here's what's coming up instead:",
            events=event_cards(db, search_events(db)[:6]),
            suggestions=["Coldplay", "Riyadh Derby", "Soundstorm"],
        )
    results = filter_by_interest(search_events(db, params.event_query, params.city) or search_events(db), known)
    headline = f"Some {known[0]} picks for you:" if known else "Here's what's on:"
    return make_payload(
        state, headline, events=event_cards(db, results[:6]),
        suggestions=[r.title.split(" — ")[0] for r in results[:3]],
    )


# --------------------------------------------------------------------------- #
# Booking team — run the specialists phase by phase, present where stuck
# --------------------------------------------------------------------------- #

def _offer_similar(db: Session, state: ConversationState, query: str) -> dict | None:
    """Unknown event → infer its genre and OFFER matching events (gated on a yes),
    instead of dumping the whole catalog. Returns None if we can't place the genre
    or have nothing in it, so the caller falls back to the plain catalog."""
    genre = infer_genre(query) or detect_interest(query)
    if not genre or not events_in_genre(search_events(db), genre):
        return None
    state.pending_suggestion = genre
    state.step = S.EVENT_SELECTION
    label = GENRE_LABELS.get(genre, f"{genre} events")
    return make_payload(
        state,
        f"We don't have “{query}” on the bill right now — but we've got some great "
        f"{label} coming up. Want me to show you?",
        suggestions=["Yes, show me", "No thanks"],
    )


def _present_event_choice(db: Session, state: ConversationState, params) -> dict | None:
    """Catalog couldn't auto-resolve the event: disambiguate, acknowledge an
    unknown name, or greet. Returns None if it resolved to a single match."""
    query = params.event_query or state.last_query
    results = search_events(db, query, params.city) if query else []
    if len(results) == 1:
        state.event_id = results[0].id
        return None
    state.step = S.EVENT_SELECTION
    if not query:
        return make_payload(
            state, GREETING_TEXT, events=event_cards(db, search_events(db)[:4]),
            suggestions=["Coldplay in Riyadh", "Riyadh Derby", "What's on this weekend?"],
        )
    if not results:
        offer = _offer_similar(db, state, query)
        if offer is not None:
            return offer
        return make_payload(
            state, f"I couldn't find anything for “{query}”. Here's what's on right now:",
            events=event_cards(db, search_events(db)),
            suggestions=["Coldplay", "Riyadh Derby", "Soundstorm"],
        )
    cities = sorted({e.city for e in results})
    return make_payload(
        state, "I found a few matches — which one?",
        events=event_cards(db, results), suggestions=cities,
    )


def _run_booking(db: Session, state: ConversationState, params, message: str, complete) -> dict:
    entry_step = state.step

    # Pre-hold event switch: "nvm, I want the derby" replaces the current selection.
    switched = _maybe_switch_event(db, state, params)
    if switched is not None:
        return switched

    # Phase 1 — Catalog: resolve the event.
    # A card click sends "#<id>" — resolve it deterministically here, never depending
    # on the LLM to interpret a direct UI selection.
    if state.event_id is None and params.event_id is not None:
        with contextlib.suppress(ToolError):
            state.event_id = get_event_details(db, params.event_id).id
    # Otherwise let the catalog specialist search (only if there's a query to run on).
    if state.event_id is None:
        has_query = bool(params.event_query or state.last_query)
        if has_query:
            run_specialist(db, state, message, complete, CATALOG)
        if state.event_id is None:
            if not has_query and llm_available():
                return _converse(db, state, message)  # off-topic / chit-chat when keyed
            choice = _present_event_choice(db, state, params)
            if choice is not None:
                return choice
    ev = get_event_details(db, state.event_id)

    # Phase 2 — Membership: tier + cap from the email.
    if not state.email:
        run_specialist(db, state, message, complete, MEMBERSHIP)
    if not state.email:
        return present_next(db, state, ev, None)
    member = lookup_member_by_email(db, state.email)
    if not state.name:
        from booking_agent.agent.payloads import first_name

        state.name = first_name(state.email)

    # Phase 3 — Pricing: capture the category/quantity slots (NLU), enforce the
    # member cap, then quote. The user may CHANGE category/quantity any time before
    # seats are held (e.g. "actually, make it one ticket") — we accept the new value
    # while state.hold_token is None; once seats are held the order is locked.
    if params.category and params.category != state.category and not state.hold_token:
        state.category = params.category
    if params.quantity is not None and params.quantity != state.quantity and not state.hold_token:
        if guardrails.exceeds_cap(params.quantity, state.ticket_cap):
            state.step = S.NEED_QUANTITY
            return present_next(db, state, ev, member)
        state.quantity = params.quantity
    if not state.category or not state.quantity:
        return present_next(db, state, ev, member)
    if not state.hold_token and not params.seat_ids:
        run_specialist(db, state, message, complete, PRICING)

    # Phase 4 — Seating: atomically hold the chosen seats.
    executed: list[dict] = []
    if not state.hold_token:
        executed = run_specialist(db, state, message, complete, SEATING)
    if not state.hold_token:
        # If a hold was attempted but failed (seats taken / wrong count), say so
        # clearly instead of silently re-showing the map.
        err = next(
            (c["result"].get("error") for c in executed
             if c.get("name") == "hold_seats" and isinstance(c.get("result"), dict) and c["result"].get("error")),
            None,
        )
        if err:
            state.step = S.SEAT_SELECTION
            return make_payload(
                state, f"Sorry — {err} Please pick {state.quantity} other seat(s).",
                seatmap_url=seatmap_url(state), suggestions=_available_seats(db, state),
            )
        return present_next(db, state, ev, member)

    # Seats held → human-in-the-loop confirmation gate.
    observability.log_transition(state.session_id, entry_step, S.AWAITING_CONFIRMATION, turn=state.turn)
    quote = compute_quote(db, state.event_id, state.category, state.quantity, tier_enum(state))
    return confirmation_payload(db, state, ev, quote)


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
    # The heuristic's strong intents (ask/cancel/confirm) are reliable; don't let the
    # LLM downgrade a question into a booking turn.
    if heuristic_intent in ("ask", "cancel", "confirm"):
        params.intent = heuristic_intent
    state.sentiment = classify_sentiment(message)
    observability.log_tool(
        state.session_id, "nlu_extract", turn=state.turn, intent=params.intent,
        event_query=params.event_query, sentiment=state.sentiment, used_llm=llm_available(),
    )

    # --- Resolve a pending "want similar events?" offer (unknown-event flow) - #
    if state.pending_suggestion:
        genre = state.pending_suggestion
        state.pending_suggestion = None
        if params.intent == "cancel":
            state.step = S.GREETING
            return make_payload(
                state,
                "No worries! Tell me what you're into — concerts, sports, comedy — or name an event.",
                suggestions=["What's on this weekend?", "Concerts", "Sports"],
            )
        if params.intent in ("confirm", "browse"):
            results = events_in_genre(search_events(db), genre)
            state.step = S.EVENT_SELECTION
            label = GENRE_LABELS.get(genre, f"{genre} events")
            return make_payload(
                state, f"Here are the {label} we've got coming up:",
                events=event_cards(db, results),
                suggestions=[r.title.split(" — ")[0] for r in results[:3]],
            )
        # Neither a yes nor a no → treat this turn as a fresh request (fall through).

    # --- Cancel: release any hold and step back to seat selection ----------- #
    if params.intent == "cancel" and state.step in (S.AWAITING_CONFIRMATION, S.SEAT_SELECTION, S.PAYMENT):
        if state.hold_token:
            release_seat_hold(db, state.hold_token)
        state.hold_token = state.hold_expires = None
        state.seat_ids = []
        state.booking_id = None
        state.step = S.SEAT_SELECTION
        seats = _available_seats(db, state) if state.event_id and state.category else []
        return make_payload(
            state,
            "No problem — I released those seats. Pick different seats, or say 'cancel' again to start over.",
            seatmap_url=seatmap_url(state), suggestions=seats,
        )

    # --- Flow words with no active booking → say so plainly ----------------- #
    if params.intent in ("confirm", "cancel") and not state.hold_token and not state.event_id:
        state.step = S.GREETING
        return make_payload(
            state,
            "I don't have an active booking for you yet — tell me an event "
            '(e.g. "Coldplay in Riyadh") and I\'ll get you set up.',
            suggestions=["Coldplay in Riyadh", "What's on this weekend?", "Is there a discount?"],
        )

    # --- Change request AT the confirmation gate: give accurate, deterministic
    #     guidance (seats are held → cancel to edit) instead of free-form Q&A that
    #     might wrongly claim "changes aren't possible". ----------------------- #
    if state.step == S.AWAITING_CONFIRMATION and params.intent not in ("confirm", "cancel") and (
        _is_change_request(message)
        or (params.category and params.category != state.category)
        or (params.quantity is not None and params.quantity != state.quantity)
    ):
        return make_payload(
            state,
            "Sure — these seats are held for you, so tap **cancel** to release them; then you can "
            "pick different seats or tell me a new quantity/category and I'll re-quote. Otherwise "
            "tap **confirm** to pay.",
            suggestions=["confirm", "cancel"],
        )

    # --- Ticket delivery (email/SMS) — be honest: we don't do it in this demo. - #
    if _is_delivery_request(message, state.step):
        return make_payload(
            state,
            "This demo doesn't email or text tickets yet — but your ticket is ready right here: "
            "tap **Download QR** to save it (or just screenshot it). It's HMAC-signed and tied to "
            "your booking, so that QR *is* your ticket.",
            suggestions=["What's on this weekend?", "Book another event"],
        )

    # --- Concierge: questions / chit-chat at ANY step, keeping state -------- #
    if params.intent == "ask" or (llm_available() and params.intent in ("greet", "smalltalk")):
        return _converse(db, state, message)

    # --- HITL gate: confirm at the confirmation step, executed in code ------ #
    if state.step == S.AWAITING_CONFIRMATION:
        if state.hold_expires and ensure_aware(datetime.fromisoformat(state.hold_expires)) <= utcnow():
            state.hold_token = state.hold_expires = None
            state.seat_ids = []
            state.step = S.SEAT_SELECTION
            return make_payload(
                state, "⏰ Your 10-minute hold expired. Let's pick seats again.",
                seatmap_url=seatmap_url(state), suggestions=_available_seats(db, state),
            )
        if params.intent == "confirm":
            assert guardrails.can_issue_payment(state.step)  # Constitution I
            ev = get_event_details(db, state.event_id)
            booking = create_booking_from_hold(
                db, email=state.email, event_id=state.event_id, category=state.category,
                quantity=state.quantity, seat_ids=state.seat_ids,
                hold_token=state.hold_token, tier=tier_enum(state),
            )
            state.booking_id = booking.id
            state.step = S.PAYMENT
            observability.log_tool(state.session_id, "create_booking", turn=state.turn,
                                   booking_id=booking.id, total_sar=sar_str(booking.total, booking.currency))
            observability.log_transition(state.session_id, entry_step, S.PAYMENT, turn=state.turn)
            MEMORY.record(state.email, f"{ev.title} — {state.quantity}× {state.category}")
            summary = booking_summary_line(
                ev.title, state.quantity, state.category, state.seat_ids,
                sar_str(booking.total, booking.currency),
            )
            return make_payload(
                state, f"Confirmed! ✅ {summary}\nComplete your payment to get your ticket.",
                payment={"booking_id": booking.id, "total_sar": sar_str(booking.total, booking.currency)},
            )
        # Any other message → re-show the summary until they confirm.
        ev = get_event_details(db, state.event_id)
        quote = compute_quote(db, state.event_id, state.category, state.quantity, tier_enum(state))
        return confirmation_payload(db, state, ev, quote)

    # --- Payment pending / completed ---------------------------------------- #
    if state.step == S.PAYMENT and state.booking_id:
        ev = get_event_details(db, state.event_id)
        booking = db.get(Booking, state.booking_id)
        if booking is not None and booking.status == BookingStatus.PAID:
            state.step = S.CONFIRMED
            # If they're asking for a different event in the same breath, don't just
            # announce completion — fall through to start that new booking.
            if not _wants_new_booking(params, message):
                return make_payload(
                    state,
                    f"You're all set — your booking for {ev.title} is paid and your ticket is issued 🎫. "
                    "Want to book anything else?",
                    suggestions=["What's on this weekend?", "Book another event"],
                )
        else:
            quote = compute_quote(db, state.event_id, state.category, state.quantity, tier_enum(state))
            summary = booking_summary_line(
                ev.title, state.quantity, state.category, state.seat_ids, sar_str(quote.total, quote.currency)
            )
            return make_payload(
                state, f"{summary}\nTap **Pay now** to complete your booking (sandbox).",
                payment={"booking_id": state.booking_id, "total_sar": sar_str(quote.total, quote.currency)},
            )

    # --- Post-completion: a finished booking can start over or just chat ---- #
    if state.step == S.CONFIRMED:
        if _wants_new_booking(params, message):
            kept_email, kept_name = state.email, state.name
            _reset_booking(state)
            state.email, state.name = kept_email, kept_name
            # fall through to handle the new request
        else:
            return make_payload(
                state, "🎫 Enjoy the show! I can book you another event or answer questions — just ask.",
                suggestions=["What's on this weekend?", "Book another event", "Is there a discount?"],
            )

    # --- Discovery / browse — also drops a pre-hold event when they change their
    #     mind toward a genre ("nvm, I want musical events"), not just a named event. #
    interest = detect_interest(message)
    has_slot = bool(params.email or params.category or params.quantity is not None
                    or params.seat_ids or params.event_id)
    named_event = bool(params.event_query) and bool(search_events(db, params.event_query, params.city))
    browse_like = params.intent == "browse" or (interest is not None and not has_slot and not named_event)
    if browse_like and not state.hold_token:
        if state.event_id is not None:               # changed their mind → drop it, keep identity
            state.event_id = state.category = state.quantity = None
            state.seat_ids = []
            state.last_query = None
        return _discover(db, state, params, message)

    # --- Booking team (catalog → membership → pricing → seating) ------------ #
    complete = _brain(state, params)
    return _run_booking(db, state, params, message, complete)


def _available_seats(db: Session, state: ConversationState, n: int = 4) -> list[str]:
    from booking_agent.agent.payloads import available_seats

    if not (state.event_id and state.category):
        return []
    return available_seats(db, state.event_id, state.category, state.quantity or n)
