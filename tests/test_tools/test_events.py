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
