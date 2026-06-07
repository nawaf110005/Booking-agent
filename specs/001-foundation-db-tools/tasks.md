---
description: "Task list for Foundation — Database Schema & Core Booking Tools"
---

# Tasks: Foundation — Database Schema & Core Booking Tools

**Input**: Design documents from `/specs/001-foundation-db-tools/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Included — Constitution VI makes tests mandatory for money/seat tools.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (quote), US2 (holds), US3 (search/member), US4 (categories/seatmap)

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `src/booking_agent/` package tree + `pyproject.toml` (deps: sqlalchemy, alembic, pydantic, pydantic-settings, pillow, qrcode, typer, rich; extras: api, ui, agent, dev)
- [X] T002 [P] Configure ruff + pytest + coverage gate (85%) in `pyproject.toml`
- [X] T003 [P] `src/booking_agent/config.py` — Settings (DATABASE_URL, HOLD_TTL_MINUTES=10, VAT_RATE=0.15, CURRENCY=SAR, signing/keys)

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No tool work can begin until the schema exists.

- [X] T004 `db/base.py` (DeclarativeBase + timestamps) and `db/session.py` (engine, SessionLocal, get_session)
- [X] T005 [P] `db/enums.py` — Category, SeatStatus, BookingStatus, HoldStatus, MemberTier, PaymentStatus
- [X] T006 `db/models.py` — 13 models (venues, events, seat_layouts, seats, members, bookings, booking_items, holds, payments, tickets, audit_log, user_preferences, interaction_log) with FKs + indexes
- [X] T007 [P] `tools/errors.py` — ToolError, NotFoundError, SeatUnavailableError, CapExceededError, ValidationToolError
- [X] T008 [P] `tools/schemas.py` — Pydantic DTOs (EventOut, MemberOut, CategoryPrice, Quote, SeatInfo, HoldResult)
- [X] T009 `db/seed.py` — deterministic catalog (Coldplay Riyadh + Jeddah, ≥3 other events), 5 members, fully-seated layout
- [X] T010 Alembic migration `migrations/versions/0001_initial.py` building all tables; `cli init-db` for dev
- [X] T011 `tests/conftest.py` — in-memory SQLite fixture + optional seed

**Checkpoint**: Schema + DTOs + seed ready — tools can now be built in parallel.

## Phase 3: User Story 1 — Exact quote (Priority: P1) 🎯 MVP

**Goal**: `compute_quote` returns itemised, exact money for any tier × quantity.

- [X] T012 [P] [US1] `tools/money.py` — minor-unit helpers + `apply_vat` (round-half-up)
- [X] T013 [P] [US1] Write `tests/test_tools/test_pricing.py` FIRST (hand-computed table, all tiers × {1,2,4,cap}, VAT, cap-exceeded) — must fail
- [X] T014 [US1] `tools/pricing.py` — `get_categories_with_pricing`, `compute_quote` (derive discount+cap from tier; raise `CapExceededError`)
- [X] T015 [US1] Make `test_pricing.py` green

**Checkpoint**: Quote math correct and tested independently.

## Phase 4: User Story 2 — Atomic seat holds (Priority: P1)

**Goal**: All-or-nothing 10-minute holds; no double-held seat; expiry reclaims seats.

- [X] T016 [P] [US2] Write `tests/test_tools/test_holds.py` FIRST (atomic all-or-nothing, double-hold blocked, expiry via freezegun, two-session concurrency) — must fail
- [X] T017 [US2] `tools/holds.py` — `check_seat_availability`, `place_seat_hold` (atomic + TTL + audit), `release_seat_hold`, `release_expired_holds`
- [X] T018 [US2] Make `test_holds.py` green; document SQLite single-writer assumption + Postgres `FOR UPDATE` path

**Checkpoint**: Concurrency safety proven by test (SC-005).

## Phase 5: User Story 3 — Search & membership (Priority: P1)

**Goal**: Find events; resolve buyer tier/discount/cap.

- [X] T019 [P] [US3] `tools/events.py` — `search_events(query, city?, date?)`, `get_event_details`
- [X] T020 [P] [US3] `tools/members.py` — `lookup_member_by_email` (non-member sentinel), `get_ticket_cap`
- [X] T021 [P] [US3] `tests/test_tools/test_events.py` + `test_members.py`

## Phase 6: User Story 4 — Categories & seat map (Priority: P2)

- [X] T022 [P] [US4] `tools/seatmap.py` — `render_seat_map(event_id, category)` → PNG bytes (available/held/sold colours)
- [X] T023 [US4] `tests/test_models.py` — model integrity + relationships + seed sanity

## Phase 7: Polish & Cross-Cutting

- [X] T024 [P] `cli.py` — `init-db`, `seed`, `search`, `quote`, `sweep`
- [X] T025 [P] `scripts/smoke_demo.py` — headless search → quote → hold demo (no API key)
- [X] T026 Run full suite + coverage ≥ 85%; ruff clean

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** blocks all stories.
- After P2: **US1**, **US2**, **US3**, **US4** can proceed in parallel (different files).
- **Polish (P7)** after the stories.

## Implementation Strategy

MVP-first: Setup → Foundational → US1 (quote) → US2 (holds) are the critical
path the rest of the agent depends on. US3/US4 add discovery and visualisation.
This whole feature is the "runnable slice" delivered in the initial pass.

## Notes

- [X] marks are complete in the initial scaffold pass; remaining slices (F002–F008) extend this foundation.
- Verify tests fail before implementing money/seat tools (Constitution VI).
