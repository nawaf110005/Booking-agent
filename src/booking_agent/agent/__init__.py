"""Conversational booking agent (F002).

A single agent that carries a user from natural-language intent to a paid,
ticketed booking — search → member → quote → seat map → atomic hold →
**HITL confirmation** → payment → ticket. LLM-driven NLU when a key is
configured (see `llm.py`), with a deterministic rule-based fallback
(`extract.py`) so the demo works offline.
"""

from booking_agent.agent.policy import respond
from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.state import ConversationState
from booking_agent.agent.store import SESSION_STORE
from booking_agent.config import settings


def handle(db, state: ConversationState, message: str) -> dict:
    """Route one turn to the configured agent mode.

    Default ``fsm`` runs the deterministic ``policy.respond`` (the MVP). Set
    ``BOOKING_AGENT_MODE=tool_agent`` (with a provider key) to use the LLM
    tool-calling loop; it falls back to the FSM if no key is configured so the
    demo never breaks.
    """
    if settings.booking_agent_mode.lower() == "tool_agent":
        from booking_agent.agent import tool_agent  # deferred (imports openai lazily)

        if tool_agent.tool_mode_available():
            return tool_agent.respond_with_tools(db, state, message, complete=tool_agent.default_complete)
    return respond(db, state, message)


__all__ = ["SESSION_STORE", "BookingParams", "ConversationState", "handle", "respond"]
