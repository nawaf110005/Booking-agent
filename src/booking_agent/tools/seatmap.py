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
from booking_agent.tools.money import sar_str

# Seating tiers ordered by distance from the stage (front → back).
_TIER_ORDER = (Category.VIP, Category.GOLD, Category.SILVER, Category.STANDING)

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


def seat_map_data(session: Session, event_id: int, category: Category | str) -> dict:
    """Structured, live seat layout for one category — for interactive (clickable)
    seat maps in the frontends. Mirrors `render_seat_map`'s grouping but as JSON.

    Shape: ``{event_id, category, rows: [{row, seats: [{id, number, status}]}],
    counts: {available, held, sold}}``. Raises NotFoundError if there are no seats.
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
    counts = {"available": 0, "held": 0, "sold": 0}
    for s in seats:
        rows.setdefault(s.row, []).append(s)

    out_rows = []
    for row in sorted(rows):
        row_seats = []
        for seat in sorted(rows[row], key=lambda s: s.number):
            status = seat.status.value
            counts[status] = counts.get(status, 0) + 1
            row_seats.append({"id": seat.seat_id, "number": seat.number, "status": status})
        out_rows.append({"row": row, "seats": row_seats})

    return {"event_id": event_id, "category": cat.value, "rows": out_rows, "counts": counts}


def venue_layout(session: Session, event_id: int) -> dict:
    """All seating sections for an event, ordered by distance from the stage
    (VIP front → Standing back), each with availability + from-price. Powers the
    venue-overview seat map so the user sees every section and where they'd sit.

    Shape: ``{event_id, sections: [{category, tier_rank, available, total,
    price_from_sar}]}``. Raises NotFoundError if the event has no seats.
    """
    _expire_event_holds(session, event_id, utcnow())
    seats = session.execute(
        select(Seat).where(Seat.event_id == event_id)
    ).scalars().all()
    if not seats:
        raise NotFoundError(f"event {event_id} has no seats")

    by_cat: dict[Category, list[Seat]] = {}
    for s in seats:
        by_cat.setdefault(s.category, []).append(s)

    sections = []
    ordered = [c for c in _TIER_ORDER if c in by_cat]
    ordered += [c for c in by_cat if c not in _TIER_ORDER]  # any extras, last
    for rank, cat in enumerate(ordered):
        cseats = by_cat[cat]
        sections.append({
            "category": cat.value,
            "tier_rank": rank,
            "available": sum(1 for s in cseats if s.status == SeatStatus.AVAILABLE),
            "total": len(cseats),
            "price_from_sar": sar_str(min(s.base_price for s in cseats)),
        })
    return {"event_id": event_id, "sections": sections}


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
