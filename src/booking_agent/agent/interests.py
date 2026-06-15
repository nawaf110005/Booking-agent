"""Lightweight interest/genre inference (personalised discovery).

Events have no genre column, so we infer one from the title + description, and we
detect what the user is into from their words. Discovery uses this to show
*relevant* events instead of dumping the whole catalog. Pure + dependency-free,
so it runs offline and is fully unit-testable.
"""

from __future__ import annotations

from typing import Any

# Order matters: more specific genres are checked before the broad "concert".
GENRES: dict[str, list[str]] = {
    "sports": ["sport", "football", "soccer", "match", "derby", " vs ", "vs.", "hilal",
               "nassr", "league", "cup", "tournament"],
    "comedy": ["comedy", "comedian", "stand-up", "standup", "laugh"],
    "conference": ["conference", "tech ", "summit", "expo", "leap", "keynote", "networking"],
    "concert": ["concert", "music", "band", "singer", "gig", "festival", "coldplay",
                "soundstorm", "mdlbeast", "tour", "live show"],
    "theatre": ["theatre", "theater", "play", "musical", "opera", "ballet"],
}


def event_genre(title: str, description: str | None = None) -> str:
    text = f"{title} {description or ''}".lower()
    for genre, keywords in GENRES.items():
        if any(k in text for k in keywords):
            return genre
    return "other"


def detect_interest(message: str | None) -> str | None:
    """Map a user message to a genre, if one is clearly implied."""
    text = (message or "").lower()
    for genre, keywords in GENRES.items():
        if any(k in text for k in keywords):
            return genre
    for genre in GENRES:  # bare genre word ("concerts", "sports")
        if genre in text:
            return genre
    return None


def filter_by_interest(events: list[Any], interests: list[str]) -> list[Any]:
    """Keep only events matching the user's interests; fall back to all if the
    filter would empty the list (better to show something than nothing)."""
    if not interests:
        return events
    picked = [e for e in events if event_genre(e.title, getattr(e, "description", None)) in interests]
    return picked or events
