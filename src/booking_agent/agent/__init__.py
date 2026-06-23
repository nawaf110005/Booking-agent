"""Conversational booking agent.

A multi-agent team that carries a user from natural-language intent to a paid,
ticketed booking — search → member → quote → seat map → atomic hold →
**HITL confirmation** → payment → ticket. An orchestrator routes each turn through
role-based specialists (catalog / membership / pricing / seating), each an LLM
tool-calling loop over its own tools. The specialists' brain is the real LLM when a
key is configured, else a deterministic offline brain (`offline_brain.py`) so the
demo and the tests run with no network. The dangerous action (booking/payment) is
kept in code behind an explicit human confirm (Constitution I).
"""

from booking_agent.agent import orchestrator
from booking_agent.agent.orchestrator import respond
from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.state import ConversationState
from booking_agent.agent.store import SESSION_STORE
from booking_agent.config import settings


def handle(db, state: ConversationState, message: str) -> dict:
    """Route one turn to the configured agent.

    Default ``multi_agent`` runs the orchestrator + specialist team
    (`orchestrator.respond`). Set ``BOOKING_AGENT_MODE=tool_agent`` for the
    single tool-calling agent instead; with no provider key both paths fall back
    to the deterministic offline brain, so the demo never breaks.
    """
    if settings.booking_agent_mode.lower() == "tool_agent":
        from booking_agent.agent import tool_agent  # deferred (imports openai lazily)

        if tool_agent.tool_mode_available():
            return tool_agent.respond_with_tools(db, state, message, complete=tool_agent.default_complete)
    return orchestrator.respond(db, state, message)


__all__ = ["SESSION_STORE", "BookingParams", "ConversationState", "handle", "respond"]
