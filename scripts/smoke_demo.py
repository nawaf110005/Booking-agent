"""Headless end-to-end demo of the booking core loop (no API key, no network).

Spins up an in-memory DB, seeds the catalog, then runs:
search -> member lookup -> categories -> quote -> seat map -> atomic hold ->
HITL confirmation summary. Mirrors the proposal's worked example.

Run:  python scripts/smoke_demo.py   (or: uv run python scripts/smoke_demo.py)
"""

from __future__ import annotations

import contextlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from booking_agent.db import models  # noqa: F401
from booking_agent.db.base import Base
from booking_agent.db.seed import seed_demo
from booking_agent.tools.events import search_events
from booking_agent.tools.holds import place_seat_hold
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing
from booking_agent.tools.seatmap import render_seat_map


def main() -> None:
    engine = create_engine(
        "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    seed_demo(session)
    session.commit()

    print("=== Booking-Agent smoke demo ===\n")

    print('User: "I want a ticket for the Coldplay show in Riyadh."')
    events = search_events(session, "Coldplay", city="Riyadh")
    event = events[0]
    print(f"Agent: Found → {event.title} · {event.venue}, {event.city} · {event.starts_at:%d %b %Y}\n")

    email = "nawaf@example.com"
    member = lookup_member_by_email(session, email)
    print(f'User: "My email is {email}."')
    print(
        f"Agent: You're a {member.tier.value.title()} member — {member.discount_label} off, "
        f"up to {member.ticket_cap} tickets.\n"
    )

    print("Agent: Categories:")
    for c in get_categories_with_pricing(session, event.id, member.tier):
        arrow = "" if c.discounted_price == c.base_price else f" → {c.discounted_sar}"
        print(f"   • {c.category.value.title():9} {c.base_sar}{arrow}   ({c.available} available)")
    print()

    print('User: "4 Gold seats, please."')
    quote = compute_quote(session, event.id, "gold", 4, member.tier)
    for line in quote.summary_lines():
        print(f"   {line}")
    print()

    png = render_seat_map(session, event.id, "gold")
    print(f"Agent: [rendered Gold seat map — {len(png):,} byte PNG]")

    seats = ["G3", "G4", "G5", "G6"]
    print(f'User: "I\'ll take {", ".join(seats)}."')
    hold = place_seat_hold(session, event.id, seats, email)
    session.commit()
    print(f"Agent: Holding {', '.join(hold.seat_ids)} until {hold.expires_at:%H:%M:%S} UTC (10 min).\n")

    print("Agent: Please confirm before payment (HITL — Constitution I):")
    print(f"   {quote.event_title}")
    print(f"   Seats: {', '.join(hold.seat_ids)}")
    print(f"   Total: {sar_str(quote.total)}  (incl. VAT {sar_str(quote.vat)})")
    print("   → On 'yes', the agent creates a Moyasar session (F003) and emails a signed ticket.\n")
    print("=== demo complete ===")

    session.close()


if __name__ == "__main__":
    main()
