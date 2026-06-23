---
description: "Task list for Payment & Ticket Fulfilment"
---

# Tasks: Payment & Ticket Fulfilment

**Input**: Design documents from `/specs/003-payment-fulfilment/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), F001 complete (schema + tools in place)

**Tests**: Included — Constitution VI makes tests mandatory for all DB-writing and security-critical tools in this slice.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (payment round-trip), US2 (idempotency), US3 (QR fraud prevention), US4 (PDF + email), US5 (hold expiry)

## Phase 0: Setup (Shared Infrastructure)

- [ ] T001 Extend `src/booking_agent/config.py` with `PAYMENT_GATEWAY`, `MOYASAR_SECRET_KEY`, `MOYASAR_PUBLISHABLE_KEY`, `MOYASAR_WEBHOOK_SECRET`, `MOYASAR_CALLBACK_URL`, `QR_HMAC_KEY`, `EMAIL_ADAPTER`, `TICKET_PDF_DIR`; add `ConfigurationError` guard at startup for missing secrets
- [ ] T002 [P] Create package skeletons `src/booking_agent/payments/__init__.py` and `src/booking_agent/fulfilment/__init__.py`
- [ ] T003 [P] Extend `tools/errors.py` with `WebhookSignatureError`, `WebhookBookingNotFoundError`, `BookingStateError`, `TicketNotReadyError`, `InvalidQRTokenError`, `ConfigurationError`
- [ ] T004 [P] Alembic migration `migrations/versions/0002_payments_raw_payload.py` — add `payments.raw_webhook_payload (LargeBinary, nullable)` and `payments.idempotency_key (String, nullable, index)` if not already present from F001
- [ ] T005 [P] Extend `tests/conftest.py` with `held_booking` fixture, `pending_payment_booking` fixture, `paid_booking` fixture, and `fake_gateway` fixture (uses `FakeGateway` + `TEST_WEBHOOK_SECRET`)

**Checkpoint**: Config, errors, migration, and test fixtures ready — all user stories can begin.

---

## Phase 1: User Story 1 — Sandbox payment round-trip, signature-verified webhook (Priority: P1) MVP

**Goal**: `create_payment_session` advances booking to `pending_payment`; `handle_payment_webhook` with valid signature advances it to `paid`; both write `audit_log`.

**Independent Test**: Using the `FakeGateway` and `paid_booking` fixture, verify `payments` row exists with `signature_verified=True` and `audit_log` contains both transitions.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T006 [P] [US1] Write `tests/test_payment/test_session.py` FIRST — `create_payment_session` on `held` booking → `pending_payment` + `payments` row + checkout URL; on `paid` booking → `BookingStateError`; on `expired` booking → `BookingStateError` — must fail
- [ ] T007 [P] [US1] Write `tests/test_payment/test_webhook.py` FIRST — valid sig → booking `paid` + `signature_verified=True` + `audit_log` row; invalid sig → `WebhookSignatureError` + booking unchanged; unknown session id → `WebhookBookingNotFoundError` — must fail

### Implementation for User Story 1

- [ ] T008 [P] [US1] `src/booking_agent/payments/gateway.py` — `PaymentGateway` Protocol (`create_session`); `PaymentSession` Pydantic model; `MoyasarGateway` (httpx POST to sandbox `https://api.moyasar.com/v1/payments`); `FakeGateway` (in-memory, no network, `simulate_webhook(booking_id) -> (bytes, str)` helper)
- [ ] T009 [US1] `src/booking_agent/payments/session.py` — `create_payment_session(booking_id, session: Session) -> PaymentSession`: verify booking is `held`, read `bookings.total` for amount (never accepts caller amount), call active gateway, insert `payments` row (`session_id`, `gateway`, `status=pending`), advance booking to `pending_payment`, write `audit_log` row (`held → pending_payment`)
- [ ] T010 [US1] `src/booking_agent/payments/webhook.py` — `handle_payment_webhook(payload: bytes, signature: str, session: Session)`: verify HMAC-SHA256 over `payload` using `MOYASAR_WEBHOOK_SECRET` with `hmac.compare_digest`; raise `WebhookSignatureError` on mismatch; delegate to idempotency check (T011); on first-time delivery advance booking to `paid`, set `signature_verified=True`, store `raw_webhook_payload`, write `audit_log` row (`pending_payment → paid`), trigger `generate_ticket_pdf` + `send_ticket_email`
- [ ] T011 [US1] Make `test_session.py` and `test_webhook.py` green

**Checkpoint**: Payment round-trip works end-to-end with the Fake gateway; US1 independently testable.

---

## Phase 2: User Story 2 — Exactly-once webhook idempotency (Priority: P1)

**Goal**: Duplicate webhook deliveries produce exactly one `paid` booking and exactly one `tickets` row.

**Independent Test**: Call `handle_payment_webhook` twice with identical payload and valid signature; assert one `tickets` row and one `payments` row with `idempotency_key` set.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US2] Write `tests/test_payment/test_idempotency.py` FIRST — first delivery → booking `paid` + one `tickets` row; second delivery with same payload → no error, still one `tickets` row, `idempotency_key` unchanged; parametrised with three identical calls — must fail

### Implementation for User Story 2

- [ ] T013 [US2] `src/booking_agent/payments/idempotency.py` — `check_and_mark_idempotency(idempotency_key: str, payments_row_id: int, session: Session) -> bool`: within a single transaction, read `payments.idempotency_key`; if already set and matches, return `True` (already processed); otherwise write the key and return `False`; on SQLite uses transaction serialisation; on Postgres issues `SELECT ... FOR UPDATE` on the `payments` row
- [ ] T014 [US2] Wire `check_and_mark_idempotency` into `handle_payment_webhook` (T010) — call before any DB mutation; if returns `True`, return immediately
- [ ] T015 [US2] Make `test_idempotency.py` green

**Checkpoint**: Idempotency proven by test; US2 independently testable using `FakeGateway.simulate_webhook`.

---

## Phase 3: User Story 3 — HMAC-signed QR fraud prevention (Priority: P1)

**Goal**: `sign_qr_token` produces a verifiable token; `verify_qr_token` rejects all tampered or forged inputs.

**Independent Test**: Generate valid token → verify passes; tamper booking id → `InvalidQRTokenError`; tamper seat list → `InvalidQRTokenError`; wrong HMAC → `InvalidQRTokenError`; raw booking id string → `InvalidQRTokenError`.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US3] Write `tests/test_fulfilment/test_qr.py` FIRST — parametrised: valid token passes; tampered `booking_id` raises `InvalidQRTokenError`; tampered `seat_ids` raises `InvalidQRTokenError`; wrong HMAC byte raises `InvalidQRTokenError`; raw booking id string raises `InvalidQRTokenError`; nonce difference raises `InvalidQRTokenError` — must fail

### Implementation for User Story 3

- [ ] T017 [US3] `src/booking_agent/fulfilment/qr.py` — `sign_qr_token(booking_id: int, seat_ids: list[str], nonce: str) -> str`: serialise payload as JSON, compute HMAC-SHA256 over JSON bytes using `QR_HMAC_KEY`, encode as URL-safe base64(`json + "." + hmac_hex`); `verify_qr_token(token: str) -> QRPayload`: base64-decode, split at last `.`, recompute HMAC, compare with `hmac.compare_digest`, raise `InvalidQRTokenError` if mismatch or malformed; `QRPayload` Pydantic model: `booking_id`, `seat_ids`, `nonce`
- [ ] T018 [US3] Make `test_qr.py` green

**Checkpoint**: QR signing and verification fully tested in isolation; no payment flow needed.

---

## Phase 4: User Story 4 — PDF ticket generation, email delivery, booking status (Priority: P2)

**Goal**: `generate_ticket_pdf` produces a bilingual PDF with embedded QR; `send_ticket_email` delivers it; `get_booking_status` returns structured ticket-card data.

**Independent Test**: Create `paid_booking` fixture, call `generate_ticket_pdf`, assert non-empty bytes + `tickets` row with non-null `qr_token` that passes `verify_qr_token`; call `send_ticket_email` in sandbox mode, assert `emailed_at` is set; call `get_booking_status`, assert `status="paid"` and `pdf_path` non-null.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T019 [P] [US4] Write `tests/test_fulfilment/test_ticket_pdf.py` FIRST — `paid_booking` fixture → `generate_ticket_pdf` returns non-empty bytes, `tickets` row exists with non-null `pdf_path` and `qr_token`, `verify_qr_token(qr_token)` does not raise; calling on non-`paid` booking raises `BookingStateError` — must fail
- [ ] T020 [P] [US4] Write `tests/test_fulfilment/test_email.py` FIRST — sandbox adapter: `send_ticket_email` on `paid_booking` with `tickets.pdf_path` set → `emailed_at` is set; calling when `pdf_path` is null raises `TicketNotReadyError` — must fail
- [ ] T021 [P] [US4] Write `tests/test_fulfilment/test_booking_status.py` FIRST — `paid_booking` fixture → `get_booking_status` returns `BookingStatusOut` with `status="paid"`, non-null `pdf_path`, non-null `qr_token`; `expired_booking` fixture → `status="expired"`, null `pdf_path`; `pending_payment_booking` → `status="pending_payment"`, null `pdf_path` — must fail

### Implementation for User Story 4

- [ ] T022 [P] [US4] `src/booking_agent/fulfilment/ticket_pdf.py` — `generate_ticket_pdf(booking_id: int, session: Session) -> bytes`: verify booking is `paid`; join `bookings`, `booking_items`, `events`, `venues`, `seats`; call `sign_qr_token(booking_id, seat_ids, nonce=secrets.token_hex(16))` to produce `qr_token`; render QR image via `qrcode` library; generate bilingual PDF (English header, Arabic event title via bidi/font) using ReportLab or WeasyPrint; write PDF to `TICKET_PDF_DIR/{booking_id}.pdf`; upsert `tickets` row with `pdf_path`, `qr_token`, `issued_at=now`; return PDF bytes
- [ ] T023 [P] [US4] `src/booking_agent/fulfilment/email.py` — `EmailGateway` Protocol (`send(to, subject, body, attachments)`); `SMTPAdapter` (smtplib, configured for Mailtrap/Ethereal sandbox); `SendGridAdapter`; `ResendAdapter`; `send_ticket_email(booking_id: int, session: Session)`: verify `tickets.pdf_path` is set (raise `TicketNotReadyError` if not); build email with PDF attachment; call active adapter; set `tickets.emailed_at = now`
- [ ] T024 [US4] `src/booking_agent/tools/booking_status.py` — `get_booking_status(booking_id: int, session: Session) -> BookingStatusOut`: join `bookings + events + venues + tickets`; return `BookingStatusOut` Pydantic model; `BookingStatusOut` includes `booking_id`, `status`, `event_title`, `venue`, `event_datetime`, `seat_ids`, `total_sar` (Decimal from halalas), `pdf_path`, `qr_token`, `emailed_at`
- [ ] T025 [US4] Make `test_ticket_pdf.py`, `test_email.py`, and `test_booking_status.py` green

**Checkpoint**: Full ticket delivery path works from `paid_booking` fixture; US4 independently testable.

---

## Phase 5: User Story 5 — Hold expiry releases seats and transitions booking to expired (Priority: P2)

**Goal**: A `pending_payment` booking whose hold TTL has elapsed is moved to `expired` and its seats returned to `available`.

**Independent Test**: Create `pending_payment_booking` with `holds.expires_at` in the past (freezegun); call `release_expired_holds()`; assert booking `expired`, seats `available`, `audit_log` row written.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T026 [P] [US5] Write `tests/test_payment/test_expiry.py` FIRST — `pending_payment_booking` fixture with `holds.expires_at` overridden to past (freezegun): `release_expired_holds()` → booking status `expired`, all seats `available`, `audit_log` row has `pending_payment → expired`; `get_booking_status` returns `status="expired"` and null `pdf_path` — must fail

### Implementation for User Story 5

- [ ] T027 [US5] Extend `src/booking_agent/tools/holds.py` (F001) — ensure `release_expired_holds()` transitions `pending_payment` bookings (not just `held`) to `expired` when their holds have elapsed, and writes the `audit_log` row for `pending_payment → expired`
- [ ] T028 [US5] Make `test_expiry.py` green

**Checkpoint**: Hold-expiry lifecycle fully covered across both `held` (F001) and `pending_payment` (F003) states.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Extend `src/booking_agent/cli.py` with `pay-session <booking_id>` (calls `create_payment_session`, prints URL) and `fake-webhook <booking_id>` (calls `FakeGateway.simulate_webhook` + `handle_payment_webhook`, confirms payment, generates ticket, prints status) for headless smoke-demo
- [ ] T030 [P] Extend `scripts/smoke_demo.py` to include payment → webhook → ticket → status steps (all via Fake gateway, no network required)
- [ ] T031 Run full suite + coverage ≥ 85% on `src/booking_agent/payments/` and `src/booking_agent/fulfilment/`; ruff clean
- [ ] T032 [P] Update `.env.example` with `PAYMENT_GATEWAY`, `MOYASAR_SECRET_KEY`, `MOYASAR_PUBLISHABLE_KEY`, `MOYASAR_WEBHOOK_SECRET`, `MOYASAR_CALLBACK_URL`, `QR_HMAC_KEY`, `EMAIL_ADAPTER`, `TICKET_PDF_DIR` (all as placeholder strings, never real values)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 0)**: No dependencies — can start immediately after F001 is merged.
- **Foundational tests and error types (T003, T005, T006, T007)**: Must complete before implementation tasks that depend on them.
- **US1 (Phase 1)**: Depends on Phase 0 completion. `session.py` (T009) depends on `gateway.py` (T008). `webhook.py` (T010) depends on `session.py` (T009) and `idempotency.py` (T013 from Phase 2, but the idempotency call can be stubbed in T010 and wired in T014).
- **US2 (Phase 2)**: Depends on Phase 1 (`handle_payment_webhook` stub must exist).
- **US3 (Phase 3)**: Depends only on Phase 0 (errors); fully independent of US1/US2 — can run in parallel with Phase 1.
- **US4 (Phase 4)**: `generate_ticket_pdf` depends on `sign_qr_token` (US3 T017). `send_ticket_email` depends on `generate_ticket_pdf` (T022). `get_booking_status` is independent.
- **US5 (Phase 5)**: Depends on Phase 0 fixtures; extends F001's `holds.py` — minimal dependency on US1.
- **Polish (Phase 6)**: After all user stories complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 0. Core dependency for US2.
- **US2 (P1)**: Depends on US1 `handle_payment_webhook` existing (can stub); `idempotency.py` is wired in T014.
- **US3 (P1)**: Fully independent; can start after Phase 0 (only needs `QR_HMAC_KEY` in config and `InvalidQRTokenError` in errors).
- **US4 (P2)**: `ticket_pdf.py` depends on US3 `sign_qr_token` (T017). `email.py` and `booking_status.py` are independent of each other.
- **US5 (P2)**: Depends on Phase 0 fixtures; independent of US3/US4.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution VI).
- Gateway/protocol before session before webhook.
- `sign_qr_token` before `generate_ticket_pdf`.
- `generate_ticket_pdf` before `send_ticket_email` (email needs a PDF path).
- `idempotency.py` wired after `webhook.py` stub exists.

### Parallel Opportunities

- Phase 0 tasks T001–T005 can all run in parallel.
- US3 (T016–T018) can run entirely in parallel with US1 (T006–T011) and US2 (T012–T015).
- Within US4: T019, T020, T021 (test writing) can run in parallel; T022 and T023 can run in parallel (different files).
- US5 (T026–T028) can run in parallel with US4.
- Phase 6 polish tasks T029, T030, T032 can run in parallel; T031 runs last.

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 0: Setup.
2. Complete Phase 1: US1 (payment session + webhook round-trip with Fake gateway).
3. Complete Phase 2: US2 (idempotency — exactly one ticket per payment event).
4. Complete Phase 3: US3 (QR signing + fraud prevention).
5. **STOP and VALIDATE**: smoke_demo.py runs `hold → session → fake-webhook → ticket-status` without errors. US1/US2/US3 independently testable.

### Incremental Delivery

1. Setup → US1 → US2 → US3 → core MVP payment + fraud prevention.
2. Add US4 → PDF + email delivery fully working.
3. Add US5 → hold-expiry lifecycle complete end-to-end.
4. Polish → CLI helpers + smoke demo + coverage gate.

### Parallel Team Strategy

With multiple developers, once Phase 0 is complete:
- Developer A: US1 + US2 (payment round-trip + idempotency).
- Developer B: US3 (QR signing — fully independent, fast path).
- Developer C: US4 PDF + email (can start after US3's `sign_qr_token` is merged).
- Any developer: US5 (small extension to F001 holds).

---

## Notes

- [ ] marks tasks as unchecked (not yet started); do not check off until the task is verified working.
- Constitution VI: tests for `handle_payment_webhook`, `sign_qr_token`/`verify_qr_token`, `generate_ticket_pdf`, and `check_and_mark_idempotency` MUST be written and failing before implementation begins.
- `FakeGateway` is the default for all tests; `MoyasarGateway` is exercised in a manual sandbox smoke test, not in the automated suite.
- Secrets (`MOYASAR_WEBHOOK_SECRET`, `QR_HMAC_KEY`) must never appear in test files; use `TEST_WEBHOOK_SECRET` and `TEST_QR_HMAC_KEY` env vars set in `conftest.py` fixtures.
- The HTTP route `POST /payments/webhook` that calls `handle_payment_webhook` is wired in F004 (API Layer), not here.
- F002 (Agent & Confirmation Gate) is the feature that calls `create_payment_session`; this feature implements the tool but does not wire it to the agent loop.
- Money in the gateway call is read from `bookings.total` (integer halalas); never accept a caller-supplied amount (Constitution IV).
