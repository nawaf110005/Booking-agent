"""Role-based specialist agents (Week 5: *Role-Based Agents*, *Multi-Agent
Orchestration*).

The booking task is decomposed across four narrow specialists, each an LLM
tool-calling loop restricted to *only* the tools for its role. The orchestrator
(`orchestrator.py`) routes the turn through them in order and hands off as each
phase completes. Splitting the tools per role keeps every agent focused and makes
the system legible — you can see which agent did what in the observability trace.

The dangerous action (booking/payment) is **no** specialist's tool — it stays in
code behind the human-in-the-loop gate (Constitution I).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from booking_agent.agent import observability
from booking_agent.agent import state as S
from booking_agent.agent.state import ConversationState
from booking_agent.agent.tool_specs import TOOL_SCHEMAS, dispatch

# Loop-prevention cap on tool round-trips within a single specialist (Week 5).
MAX_SPECIALIST_STEPS = 4

_BASE = (
    "You are the {role} specialist on a Saudi event-ticketing team. Do ONLY your "
    "job, using your tools, then stop so the next specialist can take over. Never "
    "invent events, prices, or seats; if a detail is missing, stop and let the team "
    "ask the user. You cannot take payment — that is handled by the system after the "
    "user confirms."
)


@dataclass(frozen=True)
class Specialist:
    name: str
    role: str
    tools: tuple[str, ...]

    @property
    def system_prompt(self) -> str:
        return _BASE.format(role=self.role)


# The roster, in booking order. Payment is deliberately absent.
CATALOG = Specialist("catalog", "catalog/search", ("search_events", "select_event"))
MEMBERSHIP = Specialist("membership", "membership", ("lookup_member",))
PRICING = Specialist("pricing", "pricing", ("list_categories", "quote_price"))
SEATING = Specialist("seating", "seating", ("hold_seats",))

ROSTER = (CATALOG, MEMBERSHIP, PRICING, SEATING)


def _schemas_for(names: tuple[str, ...]) -> list[dict]:
    wanted = set(names)
    return [t for t in TOOL_SCHEMAS if t["function"]["name"] in wanted]


def _state_summary(state: ConversationState) -> str:
    # Privacy: first name + whether an email is known, never the address itself.
    return (
        f"name={state.name or 'unknown'}, event_selected={bool(state.event_id)}, "
        f"email_known={bool(state.email)}, member_tier={state.tier or 'none'}, "
        f"ticket_cap={state.ticket_cap}, category={state.category}, "
        f"quantity={state.quantity}, seats_held={bool(state.hold_token)}, step={state.step}"
    )


def run_specialist(
    db: Session,
    state: ConversationState,
    message: str,
    complete,
    specialist: Specialist,
    max_steps: int = MAX_SPECIALIST_STEPS,
) -> list[dict]:
    """Run one specialist's Reason–Act–Observe loop over its restricted tools.

    `complete(messages, tools) -> {content, tool_calls}` is injected — the real
    LLM in production, a deterministic offline brain with no key, or a scripted
    fake in tests. Returns the list of executed tool calls (name/args/result) so
    the orchestrator can render candidates/errors; state mutation is the real
    output (the dispatched tools update `state`).
    """
    tools = _schemas_for(specialist.tools)
    messages: list[dict] = [
        {"role": "system", "content": specialist.system_prompt},
        {"role": "system", "content": "Current booking state: " + _state_summary(state)},
        {"role": "user", "content": message},
    ]
    executed: list[dict] = []
    for _ in range(max_steps):
        try:
            resp = complete(messages, tools)
        except Exception:
            break
        calls = resp.get("tool_calls") or []
        if not calls:
            break
        messages.append({"role": "assistant", "content": resp.get("content") or "", "tool_calls": calls})
        for call in calls:
            args = call.get("arguments") or {}
            result = dispatch(db, state, call["name"], args)
            observability.log_tool(
                state.session_id, call["name"], turn=state.turn,
                agent=specialist.name, args=json.dumps(args, default=str),
            )
            executed.append({"name": call["name"], "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "name": call["name"], "content": json.dumps(result, default=str)})
        # Seats just held → the seating specialist's job is done; hand to the HITL gate.
        if state.step == S.AWAITING_CONFIRMATION:
            break
    return executed
