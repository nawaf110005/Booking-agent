"""Observable reasoning (Constitution VII / FR-011; Week 4 *Debugging and
Controlling Agents*, Week 6 *Failure Diagnosis Workflow*).

Every tool call and key state transition is recorded as a structured,
PII-redacted event — emitted through stdlib logging AND kept in a bounded
in-memory ring buffer so the UI, tests, and a debugger can answer "what did the
agent just do, and why?". Email addresses are masked so PII never lands in logs
(PDPL).
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Any

logger = logging.getLogger("booking_agent.agent")

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+)")
_EVENTS: deque[dict] = deque(maxlen=500)


def redact_pii(value: Any) -> Any:
    """Mask the local-part of any email in a string; pass other values through."""
    if isinstance(value, str):
        return _EMAIL_RE.sub(lambda m: m.group(1) + "***" + m.group(2), value)
    return value


def _emit(event: dict) -> None:
    _EVENTS.append(event)
    logger.info("agent_event %s", event)


def log_tool(session_id: str, tool: str, *, turn: int | None = None, **fields: Any) -> None:
    """Record a tool invocation with its (redacted) arguments/outputs."""
    clean = {k: redact_pii(v) for k, v in fields.items()}
    _emit({"ts": time.time(), "kind": "tool_call", "session_id": session_id,
           "turn": turn, "tool": tool, **clean})


def log_transition(session_id: str, frm: str, to: str, *, turn: int | None = None) -> None:
    """Record a conversation state transition."""
    _emit({"ts": time.time(), "kind": "transition", "session_id": session_id,
           "turn": turn, "from": frm, "to": to})


def events(session_id: str | None = None) -> list[dict]:
    """All recorded events, optionally filtered to one session."""
    if session_id is None:
        return list(_EVENTS)
    return [e for e in _EVENTS if e.get("session_id") == session_id]


def reset() -> None:
    """Clear the buffer (used by tests)."""
    _EVENTS.clear()
