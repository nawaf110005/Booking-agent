"""Interest inference + personalised discovery (don't dump the whole catalog)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.interests import detect_interest, event_genre, filter_by_interest
from booking_agent.agent.policy import respond
from booking_agent.agent.profiles import PREFERENCES
from booking_agent.agent.state import ConversationState


def test_event_genre_inference() -> None:
    assert event_genre("Coldplay — Music of the Spheres", "a live concert") == "concert"
    assert event_genre("Al-Hilal vs Al-Nassr — Riyadh Derby") == "sports"
    assert event_genre("LEAP Tech Conference") == "conference"
    assert event_genre("Riyadh Comedy Night") == "comedy"


def test_detect_interest() -> None:
    assert detect_interest("show me concerts") == "concert"
    assert detect_interest("any football matches?") == "sports"
    assert detect_interest("something funny, comedy maybe") == "comedy"
    assert detect_interest("hello there") is None


def test_filter_by_interest_falls_back_when_empty() -> None:
    class E:
        def __init__(self, t):
            self.title = t
            self.description = None

    events = [E("Coldplay concert"), E("Riyadh Derby")]
    assert [e.title for e in filter_by_interest(events, ["sports"])] == ["Riyadh Derby"]
    # No theatre in the list → fall back to all rather than show nothing.
    assert len(filter_by_interest(events, ["theatre"])) == 2


def test_bare_browse_asks_for_interest_instead_of_listing(seeded: Session) -> None:
    st = ConversationState(session_id="i1")
    r = respond(seeded, st, "what's on?")
    assert r["events"] is None                       # did NOT dump the catalog
    assert "into" in r["reply"].lower() or "concerts" in r["reply"].lower()


def test_stated_interest_filters_the_catalog(seeded: Session) -> None:
    st = ConversationState(session_id="i2")
    r = respond(seeded, st, "show me concerts")
    titles = [e["title"] for e in r["events"]]
    assert any("Coldplay" in t for t in titles)
    assert not any("Derby" in t for t in titles)
    assert not any("Comedy" in t for t in titles)


def test_profile_preferences_used_when_known(seeded: Session) -> None:
    PREFERENCES.add("sporty@example.com", "sports")
    st = ConversationState(session_id="i3", email="sporty@example.com")
    r = respond(seeded, st, "what's on?")           # no interest stated this turn
    titles = [e["title"] for e in r["events"]]
    assert any("Derby" in t for t in titles)         # pulled from their profile
    assert not any("Coldplay" in t for t in titles)
