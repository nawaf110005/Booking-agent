"""Long-term agent memory.

Remembers a buyer's past bookings across sessions, keyed by email, so the agent
can recall history ("welcome back — last time you saw Coldplay"). In-memory for
the demo.
"""

from __future__ import annotations


class BookingMemory:
    def __init__(self) -> None:
        self._by_email: dict[str, list[str]] = {}

    def record(self, email: str | None, summary: str) -> None:
        if not email or not summary:
            return
        self._by_email.setdefault(email.lower(), []).append(summary)

    def recall(self, email: str | None) -> list[str]:
        return list(self._by_email.get((email or "").lower(), []))


MEMORY = BookingMemory()
