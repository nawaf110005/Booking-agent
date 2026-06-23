"""Generate submission data exports and visual assets from the project's own code.

Builds a fresh, deterministic seeded SQLite database, exports the seeded catalog
as CSV "datasets" (events / members / seats / tier pricing), and renders real
visual assets (seat-map PNGs + a signed-QR ticket sample) using the same tools
the agent calls at runtime. Run with: `uv run python scripts/gen_submission_assets.py`.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from booking_agent.db.base import Base
from booking_agent.db.enums import (
    NON_MEMBER_CAP,
    NON_MEMBER_DISCOUNT_BPS,
    TIER_CAP,
    TIER_DISCOUNT_BPS,
    MemberTier,
)
from booking_agent.db.models import Event, Member, Seat, Venue
from booking_agent.db.seed import seed_demo
from booking_agent.fulfilment.qr import make_qr_png, sign_qr_token
from booking_agent.tools.seatmap import render_seat_map

SUB = Path("submission/Booking_Agent_Group12_v1/02_code")
DATA = SUB / "01_data"
ASSETS = SUB / "03_assets"
DATA.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)


def _sar(halalas: int) -> str:
    return f"{halalas / 100:.2f}"


def main() -> None:
    # Fresh, deterministic seeded DB (separate file so we never touch booking.db).
    db_path = DATA / "booking_seed.db"
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        seed_demo(s)
        s.commit()

        venues = {v.id: v for v in s.execute(select(Venue)).scalars()}
        events = s.execute(select(Event).order_by(Event.starts_at)).scalars().all()
        members = s.execute(select(Member).order_by(Member.tier)).scalars().all()

        # --- events.csv ---
        with (DATA / "catalog_events.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "title", "starts_at", "venue", "city", "capacity", "status", "detail_url"])
            for e in events:
                v = venues[e.venue_id]
                w.writerow([e.id, e.title, e.starts_at.isoformat(), v.name, v.city, v.capacity, e.status.value, e.detail_url])

        # --- members.csv ---
        with (DATA / "catalog_members.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "name", "tier", "discount_bps", "discount_pct", "ticket_cap"])
            for m in members:
                w.writerow([m.email, m.name, m.tier.value, m.discount_bps, f"{m.discount_bps / 100:.0f}%", m.ticket_cap])

        # --- tier_pricing.csv (reference dataset incl. non-member row) ---
        with (DATA / "tier_pricing.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tier", "discount_bps", "discount_pct", "max_tickets_per_booking"])
            w.writerow(["(non-member)", NON_MEMBER_DISCOUNT_BPS, "0%", NON_MEMBER_CAP])
            for tier in (MemberTier.BRONZE, MemberTier.SILVER, MemberTier.GOLD, MemberTier.PLATINUM):
                bps = TIER_DISCOUNT_BPS[tier]
                w.writerow([tier.value, bps, f"{bps / 100:.0f}%", TIER_CAP[tier]])

        # --- seats.csv for the headline Coldplay Riyadh show ---
        coldplay = next(e for e in events if "Coldplay" in e.title and venues[e.venue_id].city == "Riyadh")
        seats = s.execute(
            select(Seat).where(Seat.event_id == coldplay.id).order_by(Seat.category, Seat.row, Seat.number)
        ).scalars().all()
        with (DATA / "catalog_seats_coldplay_riyadh.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["event_id", "seat_id", "section", "row", "number", "category", "base_price_halalas", "base_price_sar", "status"])
            for st in seats:
                w.writerow([st.event_id, st.seat_id, st.section, st.row, st.number, st.category.value, st.base_price, _sar(st.base_price), st.status.value])

        # --- Visual assets: seat maps (real renderer) ---
        for cat in ("gold", "vip"):
            png = render_seat_map(s, coldplay.id, cat)
            (ASSETS / f"seatmap_coldplay_{cat}.png").write_bytes(png)

        # --- Visual asset: a signed-QR ticket sample ---
        token = sign_qr_token(booking_id=1001, seat_ids=["G12", "G13", "G14", "G15"], nonce="demo1234")
        (ASSETS / "ticket_qr_sample.png").write_bytes(make_qr_png(token))

    print("Wrote data exports to", DATA)
    for p in sorted(DATA.glob("*")):
        print("  ", p.name, f"({p.stat().st_size} bytes)")
    print("Wrote assets to", ASSETS)
    for p in sorted(ASSETS.glob("*")):
        print("  ", p.name, f"({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
