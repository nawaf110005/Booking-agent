"""Pricing tools: category price lists and the exact, itemised quote.

Money is computed server-side as integer halalas (Constitution IV). The member
discount and ticket cap are derived from the tier — never supplied by the caller.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from booking_agent.config import settings
from booking_agent.db.enums import (
    Category,
    MemberTier,
    SeatStatus,
    cap_for,
    discount_bps_for,
)
from booking_agent.db.models import Event, Seat
from booking_agent.tools.errors import CapExceededError, NotFoundError, ValidationToolError
from booking_agent.tools.money import pct_bps
from booking_agent.tools.schemas import CategoryPrice, Quote


def _coerce_category(category: Category | str) -> Category:
    if isinstance(category, Category):
        return category
    try:
        return Category(str(category).strip().lower())
    except ValueError as exc:
        raise NotFoundError(f"unknown category: {category!r}") from exc


def _require_event(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise NotFoundError(f"event {event_id} not found")
    return event


def get_categories_with_pricing(
    session: Session,
    event_id: int,
    tier: MemberTier | None = None,
) -> list[CategoryPrice]:
    """List each category for an event with base + (tier-)discounted price and
    availability counts, ordered most-expensive first."""

    _require_event(session, event_id)
    discount_bps = discount_bps_for(tier)

    rows = session.execute(
        select(
            Seat.category,
            func.min(Seat.base_price),
            func.count(Seat.id),
            func.sum(case((Seat.status == SeatStatus.AVAILABLE, 1), else_=0)),
        )
        .where(Seat.event_id == event_id)
        .group_by(Seat.category)
    ).all()

    prices: list[CategoryPrice] = []
    for category, base_price, total, available in rows:
        base = int(base_price)
        prices.append(
            CategoryPrice(
                category=category,
                base_price=base,
                discounted_price=base - pct_bps(base, discount_bps),
                available=int(available or 0),
                total=int(total),
                currency=settings.currency,
            )
        )
    prices.sort(key=lambda p: p.base_price, reverse=True)
    return prices


def compute_quote(
    session: Session,
    event_id: int,
    category: Category | str,
    quantity: int,
    tier: MemberTier | None = None,
) -> Quote:
    """Return an exact, itemised quote: base, member discount, VAT 15%, total.

    Raises ValidationToolError for non-positive quantity, CapExceededError when
    quantity exceeds the tier cap, and NotFoundError for an unknown event/category.
    """

    if quantity <= 0:
        raise ValidationToolError("quantity must be a positive integer")

    cap = cap_for(tier)
    if quantity > cap:
        raise CapExceededError(
            f"quantity {quantity} exceeds the {('member' if tier else 'standard')} cap of {cap}",
            cap=cap,
        )

    event = _require_event(session, event_id)
    cat = _coerce_category(category)

    unit_price = session.execute(
        select(func.min(Seat.base_price)).where(
            Seat.event_id == event_id, Seat.category == cat
        )
    ).scalar_one_or_none()
    if unit_price is None:
        raise NotFoundError(f"event {event_id} has no '{cat.value}' category")
    unit_price = int(unit_price)

    discount_bps = discount_bps_for(tier)
    unit_discount = pct_bps(unit_price, discount_bps)
    net_unit_price = unit_price - unit_discount

    subtotal = unit_price * quantity
    discount_total = unit_discount * quantity
    net_subtotal = net_unit_price * quantity
    vat = pct_bps(net_subtotal, settings.vat_bps)
    total = net_subtotal + vat

    return Quote(
        event_id=event_id,
        event_title=event.title,
        category=cat,
        quantity=quantity,
        tier=tier,
        unit_price=unit_price,
        unit_discount=unit_discount,
        net_unit_price=net_unit_price,
        subtotal=subtotal,
        discount_total=discount_total,
        net_subtotal=net_subtotal,
        vat=vat,
        total=total,
        currency=settings.currency,
    )
