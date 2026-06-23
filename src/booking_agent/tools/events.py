"""Event catalog tools: search and detail lookup."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking_agent.db.base import utcnow
from booking_agent.db.models import Event, Venue
from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.schemas import EventOut


def _to_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        title=event.title,
        starts_at=event.starts_at,
        venue=event.venue.name,
        city=event.venue.city,
        image_url=event.image_url,
        detail_url=event.detail_url,
        status=event.status.value,
        description=event.description,
    )


def search_events(
    session: Session,
    query: str | None = None,
    city: str | None = None,
    on_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_past: bool = False,
) -> list[EventOut]:
    """Find events matching a free-text query, optionally filtered by city and
    by an exact date or an inclusive [date_from, date_to] window.

    Expired events (whose date is before today) are excluded by default — we don't
    surface or sell tickets to shows that have already happened. Pass
    ``include_past=True`` for an admin/history view.

    Returns an empty list (never raises) when nothing matches.
    """

    stmt = select(Event).join(Venue).order_by(Event.starts_at)
    if not include_past:
        stmt = stmt.where(func.date(Event.starts_at) >= utcnow().date().isoformat())
    if query:
        stmt = stmt.where(Event.title.ilike(f"%{query.strip()}%"))
    if city:
        stmt = stmt.where(Venue.city.ilike(f"%{city.strip()}%"))
    if on_date:
        stmt = stmt.where(func.date(Event.starts_at) == on_date.isoformat())
    if date_from:
        stmt = stmt.where(func.date(Event.starts_at) >= date_from.isoformat())
    if date_to:
        stmt = stmt.where(func.date(Event.starts_at) <= date_to.isoformat())
    return [_to_out(e) for e in session.execute(stmt).scalars().all()]


def get_event_details(session: Session, event_id: int) -> EventOut:
    """Full event record. Raises NotFoundError if the event does not exist."""

    event = session.get(Event, event_id)
    if event is None:
        raise NotFoundError(f"event {event_id} not found")
    return _to_out(event)
