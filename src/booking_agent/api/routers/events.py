from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from booking_agent.api.deps import get_db
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.schemas import EventOut
from booking_agent.tools.seatmap import render_seat_map, seat_map_data, venue_layout

router = APIRouter()


@router.get("/events", response_model=list[EventOut])
def list_events(
    query: str | None = None,
    city: str | None = None,
    db: Session = Depends(get_db),
) -> list[EventOut]:
    return search_events(db, query=query, city=city)


@router.get("/events/{event_id}", response_model=EventOut)
def event_detail(event_id: int, db: Session = Depends(get_db)) -> EventOut:
    return get_event_details(db, event_id)


@router.get("/events/{event_id}/seatmap.png")
def event_seatmap(event_id: int, category: str, db: Session = Depends(get_db)) -> Response:
    png = render_seat_map(db, event_id, category)
    return Response(content=png, media_type="image/png")


@router.get("/events/{event_id}/seats")
def event_seats(event_id: int, category: str, db: Session = Depends(get_db)) -> dict:
    """Live seat layout as JSON for the interactive (clickable) seat map."""
    return seat_map_data(db, event_id, category)


@router.get("/events/{event_id}/venue")
def event_venue(event_id: int, db: Session = Depends(get_db)) -> dict:
    """All sections (VIP→Standing) with availability + from-price for the venue map."""
    return venue_layout(db, event_id)
