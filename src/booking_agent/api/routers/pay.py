from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from booking_agent.api.deps import get_db
from booking_agent.fulfilment.qr import make_qr_png
from booking_agent.tools.errors import NotFoundError
from booking_agent.tools.payments import get_ticket_token, pay_booking

router = APIRouter()


@router.post("/pay/{booking_id}")
def pay(booking_id: int, db: Session = Depends(get_db)) -> dict:
    """Fake-gateway payment (sandbox). Idempotent — returns the issued ticket."""

    return {"ticket": pay_booking(db, booking_id)}


@router.get("/tickets/{booking_id}/qr.png")
def ticket_qr(booking_id: int, db: Session = Depends(get_db)) -> Response:
    token = get_ticket_token(db, booking_id)
    if not token:
        raise NotFoundError(f"no ticket for booking {booking_id}")
    return Response(content=make_qr_png(token), media_type="image/png")
