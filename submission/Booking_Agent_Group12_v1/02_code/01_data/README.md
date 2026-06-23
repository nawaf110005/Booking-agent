# 01_data — Datasets

Booking-Agent is an operational system, so its "dataset" is a **deterministic
seeded catalog**, not a training corpus. These files are exported from the
project's own seed (`02_src/src/booking_agent/db/seed.py`) by
`scripts/gen_submission_assets.py`, and mirror exactly what the running app uses.

| File | What it is |
| --- | --- |
| `booking_seed.db` | A fresh, fully-seeded SQLite database (events, venues, seats, members, layouts) — the live operational store. |
| `catalog_events.csv` | The seeded Saudi event catalog (Coldplay Riyadh/Jeddah, Riyadh Derby, LEAP, Soundstorm, Comedy Night). |
| `catalog_members.csv` | The seeded members, one per tier, with discount (basis points) and ticket cap. |
| `catalog_seats_coldplay_riyadh.csv` | Full seat inventory for the headline Coldplay Riyadh show (VIP/Gold/Silver/Standing), with prices in halalas and SAR and seat status. |
| `tier_pricing.csv` | The membership economics: discount % and max-tickets-per-booking per tier, including the non-member baseline. |

**Money convention:** prices are stored as integer **halalas** (1 SAR = 100
halalas) and discounts as integer **basis points** (1500 = 15%) so all arithmetic
is exact. The `_sar` columns are display-only conversions.

These files were generated from the seed by
`02_src/scripts/gen_submission_assets.py`, which builds a fresh database with
`seed_demo()` and exports it — the same data the running app serves.
