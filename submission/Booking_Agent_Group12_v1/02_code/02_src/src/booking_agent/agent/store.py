from __future__ import annotations

from uuid import uuid4

from booking_agent.agent.state import ConversationState


class SessionStore:
    """In-memory session store (Redis is the documented upgrade)."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}

    def create(self) -> ConversationState:
        sid = uuid4().hex
        state = ConversationState(session_id=sid)
        self._sessions[sid] = state
        return state

    def get(self, session_id: str) -> ConversationState | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> ConversationState:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create()


SESSION_STORE = SessionStore()
