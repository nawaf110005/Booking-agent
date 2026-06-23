from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking_agent.db.enums import Category, SeatStatus
from booking_agent.db.models import Event, Member, Seat, Venue


def test_seed_is_idempotent(session: Session) -> None:
    from booking_agent.db.seed import seed_demo

    seed_demo(session)
    session.commit()
    n_events = session.query(Event).count()
    seed_demo(session)  # second call should no-op
    session.commit()
    assert session.query(Event).count() == n_events


def test_seed_catalog_shape(seeded: Session) -> None:
    assert seeded.query(Venue).count() >= 3
    assert seeded.query(Event).count() == 6  # 5 + a weekend event
    assert seeded.query(Member).count() == 5


def test_event_venue_relationship(coldplay_riyadh_id: int, seeded: Session) -> None:
    event = seeded.get(Event, coldplay_riyadh_id)
    assert event is not None
    assert event.venue.city == "Riyadh"
    assert event.seats  # has seats


def test_full_layout_categories_and_prices(coldplay_riyadh_id: int, seeded: Session) -> None:
    seats = seeded.execute(
        select(Seat).where(Seat.event_id == coldplay_riyadh_id)
    ).scalars().all()
    cats = {s.category for s in seats}
    assert cats == {Category.VIP, Category.GOLD, Category.SILVER, Category.STANDING}

    gold = next(s for s in seats if s.category == Category.GOLD)
    assert gold.base_price == 80_000  # 800 SAR in halalas


def test_some_seats_sold_for_demo(coldplay_riyadh_id: int, seeded: Session) -> None:
    sold = seeded.execute(
        select(Seat).where(
            Seat.event_id == coldplay_riyadh_id, Seat.status == SeatStatus.SOLD
        )
    ).scalars().all()
    assert {s.seat_id for s in sold} >= {"G1", "G2"}
