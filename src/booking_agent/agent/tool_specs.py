"""Tool schemas + dispatcher for the tool-calling agent (Week 4: *Designing Tool
Systems*, *Tool Schema and Structured Arguments*, *Tool Dispatcher Architecture*).

The model is given these JSON function schemas and decides which to call; the
dispatcher runs the *real* F001 Python tools and updates the conversation state.
Two safety properties (Week 4 *Autonomy Limits and Guardrails*; Constitution I):

  * payment/booking is **not** a tool here — the model can never trigger a charge;
  * any unknown/forbidden tool name returns an error result, not an action.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from booking_agent.agent import guardrails
from booking_agent.agent import state as S
from booking_agent.agent.state import ConversationState
from booking_agent.db.enums import MemberTier
from booking_agent.tools.errors import CapExceededError, SeatUnavailableError, ToolError
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.holds import place_seat_hold
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing

# OpenAI-compatible function schemas advertised to the model.
TOOL_SCHEMAS: list[dict] = [
    {"type": "function", "function": {
        "name": "search_events",
        "description": "Search the events catalog. Auto-selects when exactly one event matches; otherwise returns candidates to disambiguate.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "e.g. 'coldplay', 'derby'"},
            "city": {"type": "string", "enum": ["Riyadh", "Jeddah"]},
        }, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "select_event",
        "description": "Select a specific event by id (use after search_events returns candidates).",
        "parameters": {"type": "object", "properties": {
            "event_id": {"type": "integer"}}, "required": ["event_id"]}}},
    {"type": "function", "function": {
        "name": "lookup_member",
        "description": "Look up membership by email to apply the tier discount and ticket cap.",
        "parameters": {"type": "object", "properties": {
            "email": {"type": "string"}}, "required": ["email"]}}},
    {"type": "function", "function": {
        "name": "list_categories",
        "description": "List seat categories with member pricing and availability for the selected event.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "quote_price",
        "description": "Compute an exact itemised quote (base, discount, VAT, total) for a category + quantity.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["vip", "gold", "silver", "standing"]},
            "quantity": {"type": "integer"}}, "required": ["category", "quantity"]}}},
    {"type": "function", "function": {
        "name": "hold_seats",
        "description": "Atomically hold specific seats for 10 minutes (requires a prior quote). Moves to the confirmation gate.",
        "parameters": {"type": "object", "properties": {
            "seat_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["seat_ids"]}}},
]


def _event_brief(e: Any) -> dict:
    return {"id": e.id, "title": e.title, "city": e.city, "starts_at": e.starts_at.isoformat()}


def _tier(state: ConversationState) -> MemberTier | None:
    return MemberTier(state.tier) if state.tier else None


def _t_search_events(db: Session, state: ConversationState, args: dict) -> dict:
    results = search_events(db, args.get("query") or "", args.get("city"))
    if len(results) == 1:
        state.event_id = results[0].id
        return {"selected": _event_brief(results[0])}
    state.last_query = args.get("query")
    return {"candidates": [_event_brief(e) for e in results[:6]]}


def _t_select_event(db: Session, state: ConversationState, args: dict) -> dict:
    ev = get_event_details(db, int(args["event_id"]))  # ToolError if missing
    state.event_id = ev.id
    return {"selected": _event_brief(ev)}


def _t_lookup_member(db: Session, state: ConversationState, args: dict) -> dict:
    m = lookup_member_by_email(db, args["email"])
    state.email = m.email
    state.name = (m.email.split("@", 1)[0].split(".")[0] or "").title() or None
    state.tier = m.tier.value if m.tier else None
    state.is_member = m.is_member
    state.ticket_cap = m.ticket_cap
    return {"email": m.email, "tier": state.tier, "is_member": m.is_member,
            "ticket_cap": m.ticket_cap, "discount": m.discount_label}


def _t_list_categories(db: Session, state: ConversationState, args: dict) -> dict:
    if not state.event_id:
        return {"error": "no event selected yet — call search_events/select_event first"}
    cats = get_categories_with_pricing(db, state.event_id, _tier(state))
    return {"categories": [{"category": c.category.value, "base_sar": c.base_sar,
                            "discounted_sar": c.discounted_sar, "available": c.available} for c in cats]}


def _t_quote_price(db: Session, state: ConversationState, args: dict) -> dict:
    if not state.event_id:
        return {"error": "no event selected yet"}
    category = str(args["category"]).lower()
    quantity = int(args["quantity"])
    if not guardrails.is_valid_quantity(quantity):
        return {"error": "quantity must be a positive integer"}
    if guardrails.exceeds_cap(quantity, state.ticket_cap):
        return {"error": f"quantity {quantity} exceeds the ticket cap of {state.ticket_cap}"}
    quote = compute_quote(db, state.event_id, category, quantity, _tier(state))  # CapExceededError
    state.category = category
    state.quantity = quantity
    return {"category": category, "quantity": quantity, "lines": quote.summary_lines(),
            "total_sar": sar_str(quote.total, quote.currency)}


def _t_hold_seats(db: Session, state: ConversationState, args: dict) -> dict:
    if not (state.event_id and state.email):
        return {"error": "need a selected event and the buyer's email first"}
    if not state.quantity:
        return {"error": "get a quote (category + quantity) before holding seats"}
    seat_ids = [str(s).upper() for s in args.get("seat_ids", [])]
    if len(seat_ids) != state.quantity:
        return {"error": f"need exactly {state.quantity} seat id(s), got {len(seat_ids)}"}
    hold = place_seat_hold(db, state.event_id, seat_ids, state.email)  # SeatUnavailableError
    state.seat_ids = list(hold.seat_ids)
    state.hold_token = hold.token
    state.hold_expires = hold.expires_at.isoformat()
    state.step = S.AWAITING_CONFIRMATION
    return {"held": state.seat_ids, "expires_at": state.hold_expires,
            "status": "AWAITING_CONFIRMATION — summarise the order and ask the user to confirm; "
                      "do NOT claim payment is done."}


_ALLOWED: dict[str, Callable[[Session, ConversationState, dict], dict]] = {
    "search_events": _t_search_events,
    "select_event": _t_select_event,
    "lookup_member": _t_lookup_member,
    "list_categories": _t_list_categories,
    "quote_price": _t_quote_price,
    "hold_seats": _t_hold_seats,
}


def dispatch(db: Session, state: ConversationState, name: str, args: dict) -> dict:
    """Run a model-requested tool by name. Forbidden/unknown names are refused;
    payment/booking is intentionally NOT dispatchable (HITL gate stays in code)."""
    fn = _ALLOWED.get(name)
    if fn is None:
        return {"error": f"forbidden or unknown tool '{name}' — payment/booking cannot be called as a tool"}
    try:
        return fn(db, state, args or {})
    except (CapExceededError, SeatUnavailableError, ToolError) as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
