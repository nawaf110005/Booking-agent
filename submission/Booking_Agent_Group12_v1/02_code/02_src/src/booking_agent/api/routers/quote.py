from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from booking_agent.api.deps import get_db
from booking_agent.api.schemas import QuoteRequest
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing
from booking_agent.tools.schemas import CategoryPrice, Quote

router = APIRouter()


@router.get("/events/{event_id}/categories", response_model=list[CategoryPrice])
def categories(
    event_id: int,
    email: str | None = None,
    db: Session = Depends(get_db),
) -> list[CategoryPrice]:
    tier = lookup_member_by_email(db, email).tier if email else None
    return get_categories_with_pricing(db, event_id, tier)


@router.post("/quote", response_model=Quote)
def quote(req: QuoteRequest, db: Session = Depends(get_db)) -> Quote:
    tier = lookup_member_by_email(db, req.email).tier if req.email else None
    return compute_quote(db, req.event_id, req.category, req.quantity, tier)
