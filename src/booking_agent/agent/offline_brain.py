"""Deterministic offline "brain" — a drop-in for the LLM `complete` interface.

When no provider key is configured, the specialists still need *something* to
choose their tool calls. This module supplies a rule-based `complete(messages,
tools)` built from the heuristic slot extractor: given what the user said (parsed
into `BookingParams`) and which tools a specialist is offering, it emits the one
appropriate tool call — or no call, signalling "ask the user".

This is how the FSM's deterministic logic survives the FSM's deletion: instead of
a hand-coded state machine *being* the agent, it now plays the role of a stand-in
*model* that the real agent loop calls. Same agent, swappable brain.
"""

from __future__ import annotations

from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.state import ConversationState

Message = dict


def _call(name: str, **arguments) -> dict:
    return {"content": "", "tool_calls": [{"id": f"off_{name}", "name": name, "arguments": arguments}]}


_NOOP = {"content": "", "tool_calls": []}


def make_offline_brain(state: ConversationState, params: BookingParams):
    """Return a `complete(messages, tools)` that deterministically picks the next
    tool call from the parsed slots. One closure per user turn (it remembers which
    tools it already fired so it never loops)."""
    applied: set[str] = set()

    def complete(messages: list[Message], tools: list[dict]) -> dict:
        names = {t["function"]["name"] for t in tools}

        # Catalog: resolve the event from an id (card click) or a search query.
        if state.event_id is None:
            if "select_event" in names and params.event_id is not None and "select_event" not in applied:
                applied.add("select_event")
                return _call("select_event", event_id=params.event_id)
            if "search_events" in names and "search_events" not in applied:
                query = params.event_query or state.last_query
                if query:
                    applied.add("search_events")
                    args = {"query": query}
                    if params.city:
                        args["city"] = params.city
                    return _call("search_events", **args)

        # Membership: look up the tier from the email.
        if "lookup_member" in names and params.email and "lookup_member" not in applied:
            applied.add("lookup_member")
            return _call("lookup_member", email=params.email)

        # Pricing: quote once a category + quantity are both known (the orchestrator
        # captures those slots into state, so this fires on the turn they complete).
        if ("quote_price" in names and state.category and state.quantity is not None
                and "quote_price" not in applied):
            applied.add("quote_price")
            return _call("quote_price", category=state.category, quantity=state.quantity)

        # Seating: hold the seats when the count matches the quantity.
        if ("hold_seats" in names and params.seat_ids and "hold_seats" not in applied
                and (state.quantity is None or len(params.seat_ids) == state.quantity)):
            applied.add("hold_seats")
            return _call("hold_seats", seat_ids=params.seat_ids)

        return dict(_NOOP)

    return complete
