from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.events import get_event_details, search_events


def test_search_returns_both_coldplay_events(seeded: Session) -> None:
    results = search_events(seeded, "Coldplay")
    assert len(results) == 2
    assert {e.city for e in results} == {"Riyadh", "Jeddah"}


def test_search_filters_by_city(seeded: Session) -> None:
    results = search_events(seeded, "Coldplay", city="Riyadh")
    assert len(results) == 1
    assert results[0].city == "Riyadh"


def test_search_no_match_returns_empty(seeded: Session) -> None:
    assert search_events(seeded, "Taylor Swift") == []


def test_search_empty_query_lists_catalog(seeded: Session) -> None:
    assert len(search_events(seeded)) == 6


def test_search_filters_by_weekend_range(seeded: Session) -> None:
    from booking_agent.db.base import utcnow
    from booking_agent.temporal import weekend_range

    fri, sat = weekend_range(utcnow())
    results = search_events(seeded, date_from=fri, date_to=sat)
    assert any(e.title == "Riyadh Comedy Night" for e in results)
    # The far-future Coldplay show must NOT be in this weekend.
    assert all("Coldplay" not in e.title for e in results)


def test_get_event_details_ok(coldplay_riyadh_id: int, seeded: Session) -> None:
    event = get_event_details(seeded, coldplay_riyadh_id)
    assert event.title.startswith("Coldplay")
    assert event.venue == "Kingdom Arena"


def test_get_event_details_missing(seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        get_event_details(seeded, 99999)


def _add_past_event(db: Session, title: str = "Yesterday's Gig") -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from booking_agent.db.base import utcnow
    from booking_agent.db.enums import EventStatus
    from booking_agent.db.models import Event, Venue

    venue = db.execute(select(Venue)).scalars().first()
    db.add(Event(title=title, description="already happened",
                 starts_at=utcnow() - timedelta(days=5), venue_id=venue.id,
                 status=EventStatus.SCHEDULED))
    db.commit()


def test_search_hides_expired_events(seeded: Session) -> None:
    _add_past_event(seeded)
    titles = [e.title for e in search_events(seeded)]
    assert "Yesterday's Gig" not in titles          # a past show never surfaces
    assert titles                                    # upcoming ones still do


def test_include_past_opt_in(seeded: Session) -> None:
    _add_past_event(seeded)
    assert "Yesterday's Gig" in [e.title for e in search_events(seeded, include_past=True)]


def test_closest_event_is_in_the_future(seeded: Session) -> None:
    from booking_agent.db.base import utcnow

    _add_past_event(seeded)
    upcoming = search_events(seeded)                 # ordered by starts_at
    assert upcoming[0].starts_at.date() >= utcnow().date()


def test_event_cards_include_a_human_date(seeded: Session) -> None:
    from booking_agent.agent.payloads import event_cards

    cards = event_cards(seeded, search_events(seeded)[:2])
    assert cards and all(c["when"] for c in cards)   # date+time present for the UI
