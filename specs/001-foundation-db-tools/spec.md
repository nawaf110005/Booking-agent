# Feature Specification: Foundation — Database Schema & Core Booking Tools

**Feature Branch**: `001-foundation-db-tools`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "Lay the foundation for Booking-Agent: the SQLAlchemy schema (venues, events, seat_layouts, seats, members, bookings, booking_items, holds, payments, tickets, audit_log, user_preferences, interaction_log) plus the core Python tools the agent calls before payment — search events, look up membership, quote a price (base + discount + VAT), render seat availability, and place/release atomic time-bounded seat holds. Every money- and seat-mutating tool fully unit-tested before any agent code is written."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Quote a booking exactly, with member discount and VAT (Priority: P1)

As a downstream agent caller, I can call `compute_quote(event_id, category, qty, tier)` and get back an itemised quote: unit base price, per-unit discount for the tier, subtotal, discount total, VAT at 15%, and grand total — with money represented exactly.

**Why this priority.** Pricing is the highest-risk correctness item (graded as "discount correctness across all tiers and quantities"). Every downstream step (confirmation, payment) depends on a trustworthy quote.

**Independent test.** Call `compute_quote` for each tier × several quantities against the seeded catalog; assert the math matches a hand-computed table including the 15% VAT line.

**Acceptance scenarios.**

1. **Given** a Gold category at 800 SAR and a Platinum member (15%), **When** `compute_quote(event, "Gold", qty=4, tier="platinum")` is called, **Then** unit_price=800, unit_discount=120, subtotal=3200, discount_total=480, net=2720, vat=408, total=3128 (SAR).
2. **Given** a non-member, **When** `compute_quote(event, "Silver", qty=2, tier=None)` is called, **Then** discount_total=0 and VAT is 15% of the subtotal.
3. **Given** a quantity above the tier cap, **When** `compute_quote(..., qty=cap+1)` is called, **Then** a `CapExceededError` is raised (no partial quote).

### User Story 2 — Place an atomic, time-bounded seat hold (Priority: P1)

As a downstream agent caller, I can call `place_seat_hold(event_id, seat_ids, email)` and either hold ALL requested seats (returning a hold token + `expires_at` 10 minutes out) or hold NONE if any seat is unavailable — and no second caller can ever hold the same seat.

**Why this priority.** Double-selling a seat is the worst unrecoverable failure; concurrency safety is an explicit evaluation criterion.

**Independent test.** Hold `["G12","G13"]`; assert both seats become `held` with an `expires_at`. Then attempt to hold `["G13","G14"]` and assert the whole call fails (G14 not held either) because G13 is taken.

**Acceptance scenarios.**

1. **Given** seats G12–G15 are `available`, **When** `place_seat_hold(event, ["G12","G13"], email)` is called, **Then** a `holds` row exists per seat, the seats read `held`, and the result carries `expires_at = now + 10min`.
2. **Given** G13 is already held, **When** `place_seat_hold(event, ["G13","G14"], email)` is called, **Then** the call raises `SeatUnavailableError` and G14 remains `available` (all-or-nothing).
3. **Given** a hold exists with `expires_at` in the past, **When** the sweeper runs (or `release_expired_holds()` is called), **Then** those seats return to `available` and the hold is marked expired.

### User Story 3 — Search events and resolve membership (Priority: P1)

As a downstream agent caller, I can call `search_events(query, city?, date?)` to find matching events, and `lookup_member_by_email(email)` to resolve a buyer's tier, discount, and ticket cap.

**Independent test.** Seed events for "Coldplay" in Riyadh and Jeddah; `search_events("coldplay")` returns both; `search_events("coldplay", city="Riyadh")` returns one. `lookup_member_by_email` returns the seeded Platinum member's tier/discount/cap, and a non-member sentinel for unknown emails.

**Acceptance scenarios.**

1. **Given** two Coldplay events, **When** `search_events("coldplay")` is called, **Then** both are returned with id, title, datetime, venue, city.
2. **Given** an unknown email, **When** `lookup_member_by_email("nobody@x.com")` is called, **Then** a non-member result is returned (discount 0%, cap 4) — not an exception.

### User Story 4 — Category pricing & seat-availability snapshot (Priority: P2)

As a downstream agent caller, I can call `get_categories_with_pricing(event_id, tier?)` to list each category with base and (if a tier is given) discounted price, and `check_seat_availability(event_id, seat_ids)` / `render_seat_map(event_id, category)` to inspect current seat states.

**Independent test.** For the seeded event, assert categories return VIP/Gold/Silver/Standing with correct base and discounted prices; `check_seat_availability` reports per-seat status; `render_seat_map` returns PNG bytes.

### Edge Cases

- Unknown `event_id` / `category`: tools raise `NotFoundError`, never silently return empty money.
- Empty `seat_ids` to `place_seat_hold`: raises `ValidationToolError`.
- Quantity ≤ 0: rejected by Pydantic validation.
- Re-holding seats already held by the SAME email/booking: idempotent (returns existing hold), not an error.
- Currency: MVP is SAR everywhere; money stored as integer halalas (minor units) internally, surfaced as SAR.
- Unicode/Arabic event titles and venue names: stored as `Text`/`Unicode`; tested with Arabic input.
- SQLite drops tz on read: datetimes normalised to UTC-aware on the way out.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define SQLAlchemy ORM models for `venues`, `events`, `seat_layouts`, `seats`, `members`, `bookings`, `booking_items`, `holds`, `payments`, `tickets`, `audit_log`, `user_preferences`, and `interaction_log` with foreign keys linking them.
- **FR-002**: System MUST provide an Alembic migration that builds the full schema from an empty database, and an idempotent `init-db` for dev convenience.
- **FR-003**: System MUST expose typed Python tools: `search_events`, `get_event_details`, `lookup_member_by_email`, `get_ticket_cap`, `get_categories_with_pricing`, `compute_quote`, `check_seat_availability`, `render_seat_map`, `place_seat_hold`, `release_seat_hold`, and `release_expired_holds`.
- **FR-004**: Every write/money tool MUST validate input via Pydantic before touching the DB.
- **FR-005**: `compute_quote` MUST compute money server-side as exact minor units, itemise base/discount/VAT(15%)/total, and derive the discount + cap from the member tier — never from caller-supplied amounts.
- **FR-006**: `place_seat_hold` MUST be atomic (all-or-nothing) and MUST guarantee no two holds/bookings cover the same `(event_id, seat_id)` while active; an expired hold's seats MUST be reclaimable.
- **FR-007**: `place_seat_hold` MUST set `expires_at = now + HOLD_TTL` (default 10 minutes) and return it to the caller.
- **FR-008**: Tools MUST raise typed domain errors (`NotFoundError`, `SeatUnavailableError`, `CapExceededError`, `ValidationToolError`) rather than generic exceptions.
- **FR-009**: Every seat-state and booking-state change MUST be recorded in `audit_log` in the same transaction.
- **FR-010**: Each money- or seat-mutating tool MUST have unit tests (happy path + at least one error path) passing against an in-memory SQLite fixture.

### Key Entities *(include if feature involves data)*

- **Venue.** name, city, capacity, layout reference.
- **Event.** title, datetime, venue_id, image_url, detail_url, status.
- **SeatLayout.** per-venue grid (sections, rows, seats per row).
- **Seat.** per-event instance: event_id, seat_id (e.g. "G12"), category, base_price (minor units), status (available/held/sold).
- **Member.** email (key), tier, discount_pct, ticket_cap.
- **Booking.** buyer_email, event_id, status, subtotal, discount_total, vat, total, currency.
- **BookingItem.** booking_id, seat_id, unit_price, discount_applied, vat.
- **Hold.** booking_id?, event_id, seat_id, email, expires_at, status.
- **Payment / Ticket.** (schema defined here; behaviour in F003).
- **AuditLog.** append-only state transitions.
- **UserPreferences / InteractionLog.** (schema defined here; behaviour in F006).

## Success Criteria *(mandatory)*

- **SC-001**: All foundation tools exist, are typed, have docstrings, and pass unit tests.
- **SC-002**: `pytest` runs green on a fresh clone in under 30 seconds.
- **SC-003**: `alembic upgrade head` (or `init-db`) against an empty SQLite file produces all 13 tables.
- **SC-004**: Quote math is correct for every tier × {1,2,4,cap} quantity against a hand-computed table, including VAT.
- **SC-005**: A concurrency test proves two overlapping `place_seat_hold` calls cannot both hold the same seat.
- **SC-006**: Coverage on `src/booking_agent/tools/` and `src/booking_agent/db/` ≥ 85% (`pytest-cov`).

## Assumptions

- SQLite in-memory for tests; SQLite file (`booking.db`) for local dev; Postgres URL accepted via `DATABASE_URL`.
- Money is stored as integer minor units (halalas); SAR is the only currency in the MVP.
- VAT is a flat 15% applied to the discounted subtotal.
- Membership tiers and caps follow the defaults in `Requirements.md` §10.
- Pydantic v2, Python 3.11+, SQLAlchemy 2.
- Seat-map rendering uses Pillow; no network or model download required.
- The agent (F002) wraps these tools; tools never call an LLM directly.
