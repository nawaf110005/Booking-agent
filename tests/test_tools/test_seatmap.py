from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.seatmap import render_seat_map, seat_map_data

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_render_returns_png_bytes(coldplay_riyadh_id: int, seeded: Session) -> None:
    png = render_seat_map(seeded, coldplay_riyadh_id, "gold")
    assert png[:8] == _PNG_MAGIC
    assert len(png) > 500


def test_render_each_category(coldplay_riyadh_id: int, seeded: Session) -> None:
    for category in ("vip", "gold", "silver", "standing"):
        png = render_seat_map(seeded, coldplay_riyadh_id, category)
        assert png[:8] == _PNG_MAGIC


def test_render_unknown_category(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        render_seat_map(seeded, coldplay_riyadh_id, "balcony")


def test_seat_map_data_shape(coldplay_riyadh_id: int, seeded: Session) -> None:
    data = seat_map_data(seeded, coldplay_riyadh_id, "gold")
    assert data["event_id"] == coldplay_riyadh_id
    assert data["category"] == "gold"
    assert data["rows"], "expected at least one row of seats"
    # Every seat carries an id, number, and a valid status.
    seat = data["rows"][0]["seats"][0]
    assert set(seat) == {"id", "number", "status"}
    assert seat["status"] in {"available", "held", "sold"}
    # Counts tally with the rendered seats.
    total = sum(len(r["seats"]) for r in data["rows"])
    assert total == sum(data["counts"].values())


def test_seat_map_data_unknown_category(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        seat_map_data(seeded, coldplay_riyadh_id, "balcony")


def test_venue_layout_ordered_by_tier(coldplay_riyadh_id: int, seeded: Session) -> None:
    from booking_agent.tools.seatmap import venue_layout

    v = venue_layout(seeded, coldplay_riyadh_id)
    cats = [s["category"] for s in v["sections"]]
    assert cats == ["vip", "gold", "silver", "standing"]  # front → back of venue
    for s in v["sections"]:
        assert s["total"] >= s["available"] >= 0
        assert "SAR" in s["price_from_sar"]
