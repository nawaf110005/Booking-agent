"""Conversational booking agent (F002).

A single agent that carries a user from natural-language intent to a paid,
ticketed booking — search → member → quote → seat map → atomic hold →
**HITL confirmation** → payment → ticket. LLM-driven NLU when a key is
configured (see `llm.py`), with a deterministic rule-based fallback
(`extract.py`) so the demo works offline.
"""

from booking_agent.agent.policy import respond
from booking_agent.agent.schemas import BookingParams
from booking_agent.agent.store import SESSION_STORE

__all__ = ["SESSION_STORE", "BookingParams", "respond"]
