from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from booking_agent.api.deps import get_db
from booking_agent.api.schemas import HoldRequest
from booking_agent.tools.holds import (
    check_seat_availability,
    place_seat_hold,
    release_expired_holds,
    release_seat_hold,
)
from booking_agent.tools.schemas import HoldResult, SeatInfo

router = APIRouter()


@router.get("/events/{event_id}/seats", response_model=list[SeatInfo])
def seat_status(event_id: int, seat_ids: str, db: Session = Depends(get_db)) -> list[SeatInfo]:
    """Comma-separated seat ids, e.g. ?seat_ids=G12,G13."""

    ids = [s.strip() for s in seat_ids.split(",") if s.strip()]
    return check_seat_availability(db, event_id, ids)


@router.post("/holds", response_model=HoldResult)
def create_hold(req: HoldRequest, db: Session = Depends(get_db)) -> HoldResult:
    return place_seat_hold(db, req.event_id, req.seat_ids, req.email)


@router.delete("/holds/{token}")
def delete_hold(token: str, db: Session = Depends(get_db)) -> dict[str, int]:
    return {"released": release_seat_hold(db, token)}


@router.post("/holds/sweep")
def sweep(db: Session = Depends(get_db)) -> dict[str, int]:
    return {"released": release_expired_holds(db)}
