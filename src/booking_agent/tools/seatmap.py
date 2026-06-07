"""Seat-map image renderer.

Draws the current availability of a category as a labelled grid PNG:
available = green, held = amber, sold = grey. Regenerated per request so it
always reflects live state (Constitution VII). Pure Pillow — no fonts to ship,
no network.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking_agent.db.base import utcnow
from booking_agent.db.enums import Category, SeatStatus
from booking_agent.db.models import Seat
from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.holds import _expire_event_holds

_COLORS = {
    SeatStatus.AVAILABLE: (46, 160, 67),    # green
    SeatStatus.HELD: (210, 153, 34),        # amber
    SeatStatus.SOLD: (130, 130, 130),       # grey
}
_BG = (250, 250, 250)
_INK = (30, 30, 30)

_CELL_W, _CELL_H, _GAP, _MARGIN = 46, 34, 8, 24
_TITLE_H, _LEGEND_H = 40, 34


def _coerce_category(category: Category | str) -> Category:
    if isinstance(category, Category):
        return category
    try:
        return Category(str(category).strip().lower())
    except ValueError as exc:
        raise NotFoundError(f"unknown category: {category!r}") from exc


def render_seat_map(session: Session, event_id: int, category: Category | str) -> bytes:
    """Return PNG bytes of the seat map for one category of an event.

    Raises NotFoundError if the event/category has no seats.
    """

    cat = _coerce_category(category)
    _expire_event_holds(session, event_id, utcnow())

    seats = session.execute(
        select(Seat)
        .where(Seat.event_id == event_id, Seat.category == cat)
        .order_by(Seat.row, Seat.number)
    ).scalars().all()
    if not seats:
        raise NotFoundError(f"event {event_id} has no '{cat.value}' seats")

    rows: dict[str, list[Seat]] = {}
    for s in seats:
        rows.setdefault(s.row, []).append(s)
    ordered_rows = sorted(rows)
    max_per_row = max(len(v) for v in rows.values())

    width = _MARGIN * 2 + max_per_row * (_CELL_W + _GAP)
    height = _TITLE_H + _MARGIN + len(ordered_rows) * (_CELL_H + _GAP) + _LEGEND_H

    img = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    draw.text((_MARGIN, 12), f"{cat.value.title()} — seat map", fill=_INK)

    y = _TITLE_H
    for row in ordered_rows:
        x = _MARGIN
        for seat in sorted(rows[row], key=lambda s: s.number):
            color = _COLORS.get(seat.status, _BG)
            draw.rectangle([x, y, x + _CELL_W, y + _CELL_H], fill=color, outline=_INK)
            draw.text((x + 6, y + 10), seat.seat_id, fill=(255, 255, 255))
            x += _CELL_W + _GAP
        y += _CELL_H + _GAP

    # Legend
    lx = _MARGIN
    for status, label in (
        (SeatStatus.AVAILABLE, "available"),
        (SeatStatus.HELD, "held"),
        (SeatStatus.SOLD, "sold"),
    ):
        draw.rectangle([lx, y + 6, lx + 18, y + 24], fill=_COLORS[status], outline=_INK)
        draw.text((lx + 24, y + 10), label, fill=_INK)
        lx += 130

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
