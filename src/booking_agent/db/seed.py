"""Deterministic demo seed.

Builds a multi-event Saudi catalog (concert, sports, conference, festival),
the five membership tiers, and a fully-seated layout for the headline Coldplay
Riyadh show so the seat map, quote, and hold flows all have real data.

Idempotent: safe to re-run; no-ops once events exist.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from booking_agent.db.enums import (
    TIER_CAP,
    TIER_DISCOUNT_BPS,
    Category,
    EventStatus,
    MemberTier,
    SeatStatus,
)
from booking_agent.db.models import Event, Member, Seat, SeatLayout, Venue
from booking_agent.temporal import weekend_range

SAR = 100  # halalas per SAR

# (category, row letters, seats per row, price in halalas)
FULL_LAYOUT: list[tuple[Category, list[str], int, int]] = [
    (Category.VIP, ["A", "B"], 10, 1500 * SAR),
    (Category.GOLD, ["G", "H"], 12, 800 * SAR),
    (Category.SILVER, ["S", "T"], 14, 400 * SAR),
    (Category.STANDING, ["Z"], 20, 150 * SAR),
]

# A lighter layout for the secondary events (still bookable).
LIGHT_LAYOUT: list[tuple[Category, list[str], int, int]] = [
    (Category.GOLD, ["G"], 8, 600 * SAR),
    (Category.SILVER, ["S"], 10, 250 * SAR),
]


def _make_seats(event: Event, layout: list[tuple[Category, list[str], int, int]]) -> list[Seat]:
    seats: list[Seat] = []
    for category, rows, per_row, price in layout:
        for row in rows:
            for n in range(1, per_row + 1):
                seats.append(
                    Seat(
                        event_id=event.id,
                        seat_id=f"{row}{n}",
                        section=category.value.upper(),
                        row=row,
                        number=n,
                        category=category,
                        base_price=price,
                        status=SeatStatus.AVAILABLE,
                    )
                )
    return seats


def seed_demo(session: Session) -> None:
    if session.query(Event).count() > 0:
        return

    now = datetime.now(tz=UTC)

    def _showtime(days: int, hour: int = 20) -> datetime:
        """A believable, stable showtime: today + ``days`` pinned to a fixed hour."""
        d = now + timedelta(days=days)
        return datetime(d.year, d.month, d.day, hour, 0, tzinfo=UTC)

    # --- Venues ---
    kingdom = Venue(name="Kingdom Arena", city="Riyadh", capacity=22000)
    superdome = Venue(name="Jeddah Superdome", city="Jeddah", capacity=12000)
    bujairi = Venue(name="Bujairi Terrace", city="Riyadh", capacity=5000)
    session.add_all([kingdom, superdome, bujairi])
    session.flush()

    # --- Members (one per tier; economics come from the tier tables) ---
    def member(email: str, name: str, tier: MemberTier) -> Member:
        return Member(
            email=email,
            name=name,
            tier=tier,
            discount_bps=TIER_DISCOUNT_BPS[tier],
            ticket_cap=TIER_CAP[tier],
        )

    session.add_all(
        [
            member("nawaf@example.com", "Nawaf Almufarej", MemberTier.PLATINUM),
            member("dana@example.com", "Dana", MemberTier.GOLD),
            member("hessa@example.com", "Hessa", MemberTier.SILVER),
            member("refal@example.com", "Refal", MemberTier.BRONZE),
            member("omar@example.com", "Omar", MemberTier.GOLD),
        ]
    )

    # --- Events ---
    coldplay_ry = Event(
        title="Coldplay — Music of the Spheres",
        description=(
            "Coldplay bring their Music of the Spheres World Tour to Riyadh — a "
            "full stadium production with the band's signature LED wristbands, "
            "fireworks, and hits like Yellow, Viva la Vida, and My Universe. "
            "Gates open two hours before show time."
        ),
        starts_at=_showtime(30),
        venue_id=kingdom.id,
        image_url="https://example.com/img/coldplay.jpg",
        detail_url="https://example.com/events/coldplay-riyadh",
        status=EventStatus.SCHEDULED,
    )
    coldplay_jd = Event(
        title="Coldplay — Music of the Spheres",
        description=(
            "Coldplay's Music of the Spheres World Tour comes to Jeddah — the same "
            "spectacular live show on the Red Sea coast, with full lights, fireworks, "
            "and the band's biggest anthems."
        ),
        starts_at=_showtime(45),
        venue_id=superdome.id,
        image_url="https://example.com/img/coldplay.jpg",
        detail_url="https://example.com/events/coldplay-jeddah",
        status=EventStatus.SCHEDULED,
    )
    derby = Event(
        title="Al-Hilal vs Al-Nassr — Riyadh Derby",
        description=(
            "The Riyadh Derby — Al-Hilal vs Al-Nassr in the Saudi Pro League. The "
            "Kingdom's fiercest rivalry, packed with world-class stars and an "
            "electric crowd at Kingdom Arena."
        ),
        starts_at=_showtime(10, hour=19),
        venue_id=kingdom.id,
        image_url="https://example.com/img/derby.jpg",
        detail_url="https://example.com/events/riyadh-derby",
        status=EventStatus.SCHEDULED,
    )
    leap = Event(
        title="LEAP Tech Conference",
        description=(
            "LEAP is one of the world's largest tech events — keynotes from global "
            "leaders, startups, AI, robotics, and future-tech across multiple stages."
        ),
        starts_at=_showtime(20, hour=9),
        venue_id=bujairi.id,
        image_url="https://example.com/img/leap.jpg",
        detail_url="https://example.com/events/leap",
        status=EventStatus.SCHEDULED,
    )
    soundstorm = Event(
        title="MDLBEAST Soundstorm",
        description=(
            "MDLBEAST Soundstorm — the region's biggest music festival, with top "
            "global DJs and artists across multiple stages over several nights."
        ),
        starts_at=_showtime(60, hour=21),
        venue_id=kingdom.id,
        image_url="https://example.com/img/soundstorm.jpg",
        detail_url="https://example.com/events/soundstorm",
        status=EventStatus.SCHEDULED,
    )
    # An event that always lands on the upcoming Saudi weekend (Fri 9 PM), so
    # "what's on this weekend?" returns a real result.
    friday, _saturday = weekend_range(now)
    comedy = Event(
        title="Riyadh Comedy Night",
        description=(
            "An open-air stand-up comedy night under the Riyadh stars at Bujairi "
            "Terrace, with a line-up of regional and international comedians."
        ),
        starts_at=datetime(friday.year, friday.month, friday.day, 21, 0, tzinfo=UTC),
        venue_id=bujairi.id,
        image_url="https://example.com/img/comedy.jpg",
        detail_url="https://example.com/events/comedy-night",
        status=EventStatus.SCHEDULED,
    )
    session.add_all([coldplay_ry, coldplay_jd, derby, leap, soundstorm, comedy])
    session.flush()

    # --- Seats ---
    seats = _make_seats(coldplay_ry, FULL_LAYOUT)
    for ev in (coldplay_jd, derby, leap, soundstorm, comedy):
        seats += _make_seats(ev, LIGHT_LAYOUT)
    session.add_all(seats)
    session.flush()

    # Mark a few headline-event seats SOLD so the seat map shows greyed cells.
    for s in seats:
        if s.event_id == coldplay_ry.id and s.seat_id in {"G1", "G2", "A1", "S5"}:
            s.status = SeatStatus.SOLD

    # --- Seat layouts (for the renderer / completeness) ---
    session.add_all(
        [
            SeatLayout(venue_id=kingdom.id, section="VIP", category=Category.VIP, rows=2, seats_per_row=10),
            SeatLayout(venue_id=kingdom.id, section="GOLD", category=Category.GOLD, rows=2, seats_per_row=12),
            SeatLayout(venue_id=kingdom.id, section="SILVER", category=Category.SILVER, rows=2, seats_per_row=14),
            SeatLayout(venue_id=kingdom.id, section="STANDING", category=Category.STANDING, rows=1, seats_per_row=20),
        ]
    )
    session.flush()
