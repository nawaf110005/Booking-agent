from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.seatmap import render_seat_map

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
