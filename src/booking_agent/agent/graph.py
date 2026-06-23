"""LangGraph-style adapter (FR-014) + a tiny planner (Week 5: planning / task
decomposition).

The MVP is a single agent. This wraps it as a one-node graph so the multi-agent
stretch (Catalog / Pricing / Hold / Payment / Fulfilment nodes) can be grafted in
later WITHOUT changing the MVP (Constitution VIII). If `langgraph` is installed we
could build a real StateGraph; the dependency-free shim below has the same
`invoke()` surface so nothing else has to change.
"""

from __future__ import annotations

from collections.abc import Callable

from booking_agent.agent import handle

# The ordered sub-tasks a full booking decomposes into (role-based view).
BOOKING_PLAN = [
    "search_catalog", "identify_member", "quote_price", "select_seats",
    "place_hold", "confirm_hitl", "take_payment", "fulfil_ticket",
]


def plan_booking(message: str | None = None) -> list[str]:
    """Decompose a booking request into its ordered steps (a planning stub the
    multi-agent orchestrator can route across specialised agents)."""
    return list(BOOKING_PLAN)


class AgentGraph:
    """Minimal single-node graph: node 'agent' is the whole booking agent."""

    def __init__(self, node: Callable = handle) -> None:
        self.nodes: dict[str, Callable] = {"agent": node}
        self.entry = "agent"

    def invoke(self, db, state, message: str) -> dict:
        return self.nodes[self.entry](db, state, message)


def build_graph() -> AgentGraph:
    return AgentGraph()


# --- Multi-agent stretch (Week 5): a tiny router over specialised agents ----- #

def recommend_events(db, interests: list[str], k: int = 3):
    """The recommender agent's core: rank the catalog by the user's interests."""
    from booking_agent.agent.interests import filter_by_interest
    from booking_agent.tools.events import search_events

    return filter_by_interest(search_events(db), interests or [])[:k]


class RecommenderAgent:
    """A specialised agent that only suggests events (no booking authority)."""

    name = "recommender"

    def __call__(self, db, state, message: str) -> dict:
        from booking_agent.agent.profiles import PREFERENCES

        interests = state.interests or PREFERENCES.get(getattr(state, "email", None))
        events = recommend_events(db, interests)
        return {"agent": self.name, "recommendations": [e.title for e in events]}


def route_intent(intent: str | None) -> str:
    """Pick which specialised agent should handle the turn."""
    return "recommender" if intent in ("recommend", "discover") else "booking"


class MultiAgentGraph:
    """Two-node demo: a router sends the turn to the recommender or the booking
    agent. The booking agent stays authoritative for anything touching money/holds
    (Constitution VIII — multi-agent must not regress the MVP)."""

    def __init__(self) -> None:
        self.nodes = {"booking": handle, "recommender": RecommenderAgent()}

    def invoke(self, db, state, message: str, intent: str = "booking") -> dict:
        return self.nodes[route_intent(intent)](db, state, message)
