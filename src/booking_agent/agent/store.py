from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from booking_agent.agent.state import ConversationState
from booking_agent.config import PROJECT_ROOT, settings

logger = logging.getLogger("booking_agent.agent")


class SessionStore:
    """Session store keyed by id, with best-effort JSON persistence.

    Two properties matter for a chat that holds its place in the booking flow:

    * **Honour the client's id.** ``get_or_create("abc")`` for an unknown ``abc``
      creates the session *under that id*, so the next turn with the same id reuses
      it — the conversation keeps accumulating instead of starting over each message.
    * **Survive restarts.** The in-memory dict is wiped when the process restarts;
      persisting each turn to ``<root>/.sessions/<id>.json`` lets an in-progress
      booking resume seamlessly. Best-effort: any IO error is swallowed so it can
      never break a turn. Disabled in tests via ``booking_agent_persist_sessions``.
    """

    def __init__(self, persist_dir: Path | None = None) -> None:
        self._sessions: dict[str, ConversationState] = {}
        self._dir = persist_dir

    # --- persistence (best-effort) ----------------------------------------- #
    def _persist_on(self) -> bool:
        return self._dir is not None and bool(getattr(settings, "booking_agent_persist_sessions", True))

    def _load(self, sid: str) -> ConversationState | None:
        if not self._persist_on():
            return None
        path = self._dir / f"{sid}.json"  # type: ignore[union-attr]
        if not path.exists():
            return None
        try:
            return ConversationState(**json.loads(path.read_text()))
        except Exception:
            return None

    def save(self, state: ConversationState) -> None:
        if not self._persist_on():
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
            (self._dir / f"{state.session_id}.json").write_text(  # type: ignore[union-attr]
                json.dumps(asdict(state), default=str)
            )
        except Exception:
            logger.warning("could not persist session %s", state.session_id)

    # --- API ---------------------------------------------------------------- #
    def create(self) -> ConversationState:
        sid = uuid4().hex
        state = ConversationState(session_id=sid)
        self._sessions[sid] = state
        return state

    def get(self, session_id: str) -> ConversationState | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        loaded = self._load(session_id)
        if loaded is not None:
            self._sessions[session_id] = loaded
        return loaded

    def get_or_create(self, session_id: str | None) -> ConversationState:
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
            # Honour the client's id so the next turn reuses this session.
            state = ConversationState(session_id=session_id)
            self._sessions[session_id] = state
            return state
        return self.create()


SESSION_STORE = SessionStore(persist_dir=PROJECT_ROOT / ".sessions")
