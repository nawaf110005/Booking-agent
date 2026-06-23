"""Tiny per-user preference memory (personalisation).

Remembers a buyer's inferred interests across sessions, keyed by email — the
"profile" the agent consults so it doesn't re-ask what you like every time. In
memory for the demo, mirroring SESSION_STORE.
"""

from __future__ import annotations


class PreferenceStore:
    def __init__(self) -> None:
        self._prefs: dict[str, list[str]] = {}

    def get(self, email: str | None) -> list[str]:
        return list(self._prefs.get((email or "").lower(), []))

    def add(self, email: str | None, interest: str | None) -> None:
        if not email or not interest:
            return
        bucket = self._prefs.setdefault(email.lower(), [])
        if interest not in bucket:
            bucket.append(interest)


PREFERENCES = PreferenceStore()
