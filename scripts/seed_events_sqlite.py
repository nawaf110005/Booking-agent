#!/usr/bin/env python3
"""Standalone dummy-event seeder for a SQLite database.

Creates a self-contained SQLite DB with realistic dummy event data so you can
bootstrap another project. Pure standard library — no installs, no frameworks.

Tables created:
    venues            (id, name, city, capacity)
    events            (id, title, type, description, venue_id, city, starts_at,
                       doors_open, status, currency, min_price_sar, image_url)
    event_categories  (id, event_id, category, base_price_sar, total_seats,
                       available_seats)
    seats             (optional, with --with-seats) per-seat rows for each category

Usage:
    python seed_events_sqlite.py                      # 50 events -> events.db
    python seed_events_sqlite.py --count 50 --db my.db
    python seed_events_sqlite.py --with-seats         # also generate seat rows
    python seed_events_sqlite.py --seed 7             # different deterministic set

Notes:
    * Prices are whole SAR integers (round ticket prices) — easy to consume.
    * Dates are ISO-8601 strings spread over the next ~6 months.
    * Deterministic: same --seed + --count always produces the same data.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta

# --------------------------------------------------------------------------- #
# Reference data pools
# --------------------------------------------------------------------------- #

VENUES_BY_CITY = {
    "Riyadh": ["Kingdom Arena", "King Fahd Stadium", "ANB Arena", "Mayadeen", "Boulevard Hall"],
    "Jeddah": ["Jeddah Superdome", "King Abdullah Sports City", "Jeddah Season Waterfront"],
    "Dammam": ["Dhahran Expo", "Dammam Corniche Arena"],
    "Khobar": ["Al-Khobar Corniche Arena", "Ajdan Walk Stage"],
    "AlUla": ["Maraya Concert Hall", "AlUla Amphitheatre"],
    "Abha": ["Abha Amphitheatre"],
    "Taif": ["Taif Season Park"],
    "NEOM": ["NEOM Bay Arena"],
}

# Each event "type" carries the building blocks to make a varied, realistic title.
EVENT_TYPES = {
    "concert": {
        "names": ["Coldplay", "Bruno Mars", "Maroon 5", "Tamer Hosny", "Amr Diab",
                  "Mohammed Abdu", "Rashed Al-Majed", "Marshmello", "David Guetta",
                  "Calvin Harris", "The Weeknd", "Imagine Dragons", "OneRepublic",
                  "Post Malone", "Ed Sheeran", "Alicia Keys", "Andrea Bocelli"],
        "titles": ["{name} — Live in {city}", "{name} World Tour", "{name} Live"],
        "blurb": "An unforgettable live concert experience.",
        "tier": 1.6,
    },
    "football": {
        "teams": ["Al-Hilal", "Al-Nassr", "Al-Ahli", "Al-Ittihad", "Al-Shabab",
                  "Al-Ettifaq", "Al-Taawoun", "Al-Fateh"],
        "leagues": ["Saudi Pro League", "King's Cup", "Saudi Super Cup"],
        "titles": ["{a} vs {b} — {league}"],
        "blurb": "A top-flight Saudi football fixture.",
        "tier": 1.1,
    },
    "comedy": {
        "names": ["Trevor Noah", "Kevin Hart", "Russell Peters", "Bassem Youssef",
                  "Gad Elmaleh", "Michael McIntyre"],
        "titles": ["{name} — Stand-Up Night", "{name} Live in {city}"],
        "blurb": "A night of world-class stand-up comedy.",
        "tier": 0.9,
    },
    "theatre": {
        "names": ["The Phantom of the Opera", "Les Misérables", "Swan Lake Ballet",
                  "Cinderella on Ice", "The Lion King Musical"],
        "titles": ["{name}", "{name} — {city}"],
        "blurb": "A spectacular theatre and stage production.",
        "tier": 1.2,
    },
    "festival": {
        "names": ["MDLBEAST Soundstorm", "XP Music Festival", "AlUla Moments",
                  "Riyadh Season Festival", "Jeddah Season Nights"],
        "titles": ["{name} {year}", "{name}"],
        "blurb": "A multi-day music and culture festival.",
        "tier": 1.4,
    },
    "conference": {
        "names": ["LEAP Tech Conference", "Black Hat MEA", "24 Fintech",
                  "Misk Global Forum", "Web Summit Qiddiya"],
        "titles": ["{name} {year}", "{name}"],
        "blurb": "A leading technology and business conference.",
        "tier": 1.0,
    },
    "esports": {
        "names": ["EA FC", "Valorant", "League of Legends", "Fortnite", "Rocket League"],
        "titles": ["{name} Championship — {city}", "Gamers8: {name} Finals"],
        "blurb": "Live competitive esports finals.",
        "tier": 0.8,
    },
    "family": {
        "names": ["Disney on Ice", "Monster Jam", "Cirque du Soleil", "PAW Patrol Live",
                  "Hot Wheels Monster Trucks"],
        "titles": ["{name}", "{name} Live in {city}"],
        "blurb": "A family-friendly live show for all ages.",
        "tier": 0.9,
    },
}

CATEGORIES = ["vip", "gold", "silver", "standing"]
# Base price bands (whole SAR) per category before the per-event tier multiplier.
PRICE_BANDS = {"vip": (700, 1500), "gold": (350, 800), "silver": (180, 400), "standing": (90, 250)}

SCHEMA = """
DROP TABLE IF EXISTS seats;
DROP TABLE IF EXISTS event_categories;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS venues;

CREATE TABLE venues (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL,
    city     TEXT    NOT NULL,
    capacity INTEGER NOT NULL
);

CREATE TABLE events (
    id            INTEGER PRIMARY KEY,
    title         TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    description   TEXT,
    venue_id      INTEGER NOT NULL REFERENCES venues(id),
    city          TEXT    NOT NULL,
    starts_at     TEXT    NOT NULL,
    doors_open    TEXT,
    status        TEXT    NOT NULL DEFAULT 'scheduled',
    currency      TEXT    NOT NULL DEFAULT 'SAR',
    min_price_sar INTEGER NOT NULL,
    image_url     TEXT
);

CREATE TABLE event_categories (
    id              INTEGER PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES events(id),
    category        TEXT    NOT NULL,
    base_price_sar  INTEGER NOT NULL,
    total_seats     INTEGER NOT NULL,
    available_seats INTEGER NOT NULL
);

CREATE TABLE seats (
    id        INTEGER PRIMARY KEY,
    event_id  INTEGER NOT NULL REFERENCES events(id),
    category  TEXT    NOT NULL,
    seat_id   TEXT    NOT NULL,
    row       TEXT    NOT NULL,
    number    INTEGER NOT NULL,
    status    TEXT    NOT NULL DEFAULT 'available'
);

CREATE INDEX ix_events_city ON events(city);
CREATE INDEX ix_events_type ON events(type);
CREATE INDEX ix_cat_event   ON event_categories(event_id);
CREATE INDEX ix_seats_event ON seats(event_id);
"""


def _make_title(etype: str, spec: dict, city: str, rng: random.Random, year: int) -> tuple[str, str]:
    pattern = rng.choice(spec["titles"])
    if etype == "football":
        a, b = rng.sample(spec["teams"], 2)
        title = pattern.format(a=a, b=b, league=rng.choice(spec["leagues"]))
    else:
        name = rng.choice(spec["names"])
        title = pattern.format(name=name, city=city, year=year)
    return title, spec["blurb"]


def seed(db_path: str, count: int, seed_value: int, with_seats: bool) -> None:
    rng = random.Random(seed_value)
    # A fixed "now" so dates are reproducible (override if you want live dates).
    now = datetime(2026, 6, 23, 12, 0, 0)

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    # 1) Venues
    venue_ids: dict[tuple[str, str], int] = {}
    vid = 0
    for city, names in VENUES_BY_CITY.items():
        for name in names:
            vid += 1
            cur.execute(
                "INSERT INTO venues (id, name, city, capacity) VALUES (?, ?, ?, ?)",
                (vid, name, city, rng.choice([3000, 5000, 8000, 12000, 20000, 35000])),
            )
            venue_ids[(city, name)] = vid

    cities = list(VENUES_BY_CITY)
    types = list(EVENT_TYPES)

    # 2) Events + categories (+ optional seats)
    seat_pk = 0
    for eid in range(1, count + 1):
        etype = rng.choice(types)
        spec = EVENT_TYPES[etype]
        city = rng.choice(cities)
        venue = rng.choice(VENUES_BY_CITY[city])
        starts = now + timedelta(days=rng.randint(3, 180), hours=rng.choice([-3, 0, 2, 5]))
        starts = starts.replace(minute=rng.choice([0, 30]), second=0, microsecond=0)
        title, blurb = _make_title(etype, spec, city, rng, year=starts.year)

        # how many categories this event offers (2..4)
        cats = CATEGORIES[: rng.randint(2, 4)]
        prices = {}
        for cat in cats:
            lo, hi = PRICE_BANDS[cat]
            prices[cat] = int(round(rng.randint(lo, hi) * spec["tier"] / 10.0) * 10)  # round to 10 SAR

        status = rng.choices(["scheduled", "sold_out", "cancelled"], weights=[88, 8, 4])[0]
        cur.execute(
            """INSERT INTO events
               (id, title, type, description, venue_id, city, starts_at, doors_open,
                status, currency, min_price_sar, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, title, etype, blurb, venue_ids[(city, venue)], city,
             starts.isoformat(), (starts - timedelta(hours=2)).isoformat(),
             status, "SAR", min(prices.values()),
             f"https://picsum.photos/seed/event{eid}/640/360"),
        )

        for cat in cats:
            total = rng.choice([40, 60, 80, 120, 200, 300])
            sold = 0 if status == "scheduled" else (total if status == "sold_out" else rng.randint(0, total))
            sold = rng.randint(0, int(total * 0.6)) if status == "scheduled" else sold
            available = max(0, total - sold)
            cur.execute(
                """INSERT INTO event_categories
                   (event_id, category, base_price_sar, total_seats, available_seats)
                   VALUES (?, ?, ?, ?, ?)""",
                (eid, cat, prices[cat], total, available),
            )

            if with_seats:
                per_row = 12
                for i in range(total):
                    seat_pk += 1
                    row_letter = chr(ord("A") + i // per_row)
                    number = (i % per_row) + 1
                    st = "available" if i >= sold else "sold"
                    cur.execute(
                        """INSERT INTO seats (id, event_id, category, seat_id, row, number, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (seat_pk, eid, cat, f"{cat[:1].upper()}{row_letter}{number}",
                         row_letter, number, st),
                    )

    conn.commit()

    # Summary
    n_ev = cur.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    n_ven = cur.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    n_cat = cur.execute("SELECT COUNT(*) FROM event_categories").fetchone()[0]
    n_seat = cur.execute("SELECT COUNT(*) FROM seats").fetchone()[0]
    conn.close()
    print(f"Seeded {db_path}: {n_ev} events, {n_ven} venues, {n_cat} category rows, {n_seat} seats.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a SQLite DB with dummy events.")
    ap.add_argument("--db", default="events.db", help="output SQLite file (default: events.db)")
    ap.add_argument("--count", type=int, default=50, help="number of events (default: 50)")
    ap.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    ap.add_argument("--with-seats", action="store_true", help="also generate per-seat rows")
    args = ap.parse_args()
    seed(args.db, args.count, args.seed, args.with_seats)


if __name__ == "__main__":
    main()
