# Implementation Plan: Foundation — Database Schema & Core Booking Tools

**Branch**: `001-foundation-db-tools` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-foundation-db-tools/spec.md`

## Summary

Build the persistence layer and the pre-payment tool surface the booking agent
depends on. Thirteen SQLAlchemy models, an Alembic migration, a deterministic
seed (multi-event catalog + members + seats), and the typed Python tools for
search, membership, pricing, seat availability, seat-map rendering, and atomic
seat holds. Money is exact (integer minor units) and every money/seat tool is
unit-tested before any agent wiring (Constitution VI).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings, Pillow, qrcode, typer, rich

**Storage**: SQLite (dev/test/demo) via `DATABASE_URL`; PostgreSQL-compatible

**Testing**: pytest, pytest-cov, freezegun (TTL/expiry tests)

**Target Platform**: Local backend (Windows/macOS/Linux); offline-capable

**Project Type**: Single Python project (`src/booking_agent/`)

**Performance Goals**: Tool calls < 50ms on SQLite; seat-map render < 300ms

**Constraints**: No network for tools; holds atomic under concurrency; money exact (no float)

**Scale/Scope**: Demo catalog (~5 events, 1–2 venues, a few hundred seats); single-writer SQLite assumption documented, Postgres path uses row locks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | No payment tools here; this slice stops at the hold. Confirmation gate lives in F002. ✅ |
| II. Atomic, Time-Bounded Holds | `place_seat_hold` is all-or-nothing with 10-min TTL + `release_expired_holds` sweeper. **Core of this slice.** ✅ |
| III. Tools Are Python Functions | All tools are in-repo typed functions; no external ticketing API. ✅ |
| IV. Exact, Auditable Money | Money stored as integer halalas; `compute_quote` itemises base/discount/VAT; discount derived from member tier. ✅ |
| V. Tamper-Evident Tickets | `payments`/`tickets` tables defined here; HMAC/idempotency behaviour deferred to F003. ✅ |
| VI. Test-First | Every money/seat tool ships with unit tests before F002 wires it. **Enforced here.** ✅ |
| VII. Observable Reasoning | Seat/booking state changes write `audit_log` rows. ✅ |
| VIII. MVP First | Pure single-agent foundation; no multi-agent code. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation-db-tools/
├── plan.md              # This file
├── spec.md              # Feature spec
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── config.py                 # Pydantic Settings (DATABASE_URL, HOLD_TTL, VAT_RATE, keys)
├── cli.py                    # init-db | seed | search | quote | sweep
├── db/
│   ├── __init__.py
│   ├── base.py               # DeclarativeBase + created_at/updated_at + utcnow
│   ├── session.py            # engine + SessionLocal + get_session
│   ├── enums.py              # Category, SeatStatus, BookingStatus, MemberTier, HoldStatus
│   ├── models.py             # 13 ORM models
│   └── seed.py               # deterministic demo catalog + members + seats
├── tools/
│   ├── __init__.py
│   ├── errors.py             # ToolError hierarchy
│   ├── schemas.py            # Pydantic DTOs (EventOut, MemberOut, Quote, ...)
│   ├── money.py              # exact minor-unit helpers + VAT
│   ├── events.py             # search_events, get_event_details
│   ├── members.py            # lookup_member_by_email, get_ticket_cap
│   ├── pricing.py            # get_categories_with_pricing, compute_quote
│   ├── seatmap.py            # render_seat_map (Pillow)
│   └── holds.py              # check_seat_availability, place_seat_hold, release_seat_hold, release_expired_holds

migrations/                   # Alembic (env.py, versions/0001_initial.py)
tests/
├── conftest.py               # in-memory SQLite fixture + seed
├── test_models.py
└── test_tools/
    ├── test_pricing.py       # quote math table, all tiers × qty, VAT, cap
    ├── test_holds.py         # atomic hold, all-or-nothing, expiry, concurrency
    ├── test_events.py
    └── test_members.py
```

**Structure Decision**: Single-project `src/booking_agent/` layout mirroring the
CRM-Agent reference, with `db/`, `tools/`, `tests/` as the F001 surface. Later
slices add `agent/`, `api/`, `ui/`, `fulfilment/`, `rag/` siblings.

## Phase 0 — Research / Decisions

- **Money representation**: integer minor units (halalas) + a `money.py` helper.
  Rejected float (rounding drift) and Decimal-everywhere (heavier, still needs a
  rounding policy). VAT = round_half_up(net * 15%).
- **Atomic holds on SQLite**: a `UNIQUE(event_id, seat_id)` partial guard via an
  active-hold uniqueness check inside a single transaction; on Postgres use
  `SELECT ... FOR UPDATE`. Document the single-writer SQLite assumption; the
  concurrency test uses two sessions to prove all-or-nothing.
- **TTL/expiry**: store `expires_at`; `release_expired_holds()` is called by the
  sweeper (F002/F004) and is unit-tested with `freezegun`.
- **Seat-map render**: Pillow draws a grid from the seat rows, colouring
  available=green / held=yellow / sold=grey, labelled by seat id → PNG bytes.

## Phase 1 — Design Artifacts

- ORM models + enums finalised (see Project Structure).
- Pydantic DTOs in `tools/schemas.py` are the stable contract F002+ depend on.
- Seed produces a Coldplay-in-Riyadh + multi-event catalog, the 5 membership
  tiers, and a fully-seated Gold/Silver/VIP/Standing layout for one event.

## Complexity Tracking

No constitution violations — table intentionally empty.
