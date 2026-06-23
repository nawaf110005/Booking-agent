# Feature Specification: Payment & Ticket Fulfilment

**Feature Branch**: `003-payment-fulfilment`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "Turn an approved, held booking into a paid booking and a delivered, tamper-evident ticket. Covers a Moyasar SANDBOX adapter behind one interface plus a Fake gateway for offline tests — create_payment_session returns a hosted-checkout URL + session id. Booking lifecycle held → pending_payment → paid / expired / cancelled. Webhook handling verifies Moyasar signature (HMAC over raw body), enforces an idempotency key (duplicate deliveries → exactly one paid booking + one ticket), converts the hold to a confirmed booking, and writes audit_log. Ticket generation: generate_ticket_pdf (ReportLab/WeasyPrint, bilingual) embedding an HMAC-signed QR token; verify_qr_token for door scan; send_ticket_email via SMTP/SendGrid/Resend sandbox; get_booking_status."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sandbox payment completes and booking is marked paid via a signature-verified webhook (Priority: P1)

As the booking agent, after a user has explicitly confirmed their booking summary (per F002's HITL gate), I call `create_payment_session(booking_id)` to obtain a Moyasar hosted-checkout URL and session id, which I surface to the user. When the user pays, Moyasar fires a webhook to the handler; the handler verifies the HMAC signature over the raw body, advances the booking from `held` → `pending_payment` (session created) → `paid` (webhook received), and writes an audit log entry for every state transition.

**Why this priority.** The payment round-trip is the product's core financial outcome. Without a working, signature-verified webhook the booking can never be confirmed, making every downstream step (ticket generation, email delivery) unreachable.

**Independent test.** Using the Fake gateway: call `create_payment_session` on a `held` booking, assert the booking moves to `pending_payment` and a session id is stored. Then call `handle_payment_webhook` with a correctly-signed fake payload, assert the booking moves to `paid`, a `payments` row is written with `signature_verified=True`, and an `audit_log` row records the `pending_payment → paid` transition.

**Acceptance scenarios.**

1. **Given** a booking in `held` status with valid seats, **When** `create_payment_session(booking_id)` is called, **Then** the booking status becomes `pending_payment`, a `payments` row is inserted with the session id, and a hosted-checkout URL string is returned.
2. **Given** a booking in `pending_payment` status and a correctly-signed Moyasar webhook payload, **When** `handle_payment_webhook(payload, signature)` is called, **Then** the booking status becomes `paid`, `payments.signature_verified` is `True`, and an `audit_log` row records the transition with timestamp.
3. **Given** a webhook payload with an invalid or missing signature, **When** `handle_payment_webhook(payload, bad_signature)` is called, **Then** a `WebhookSignatureError` is raised, the booking status is unchanged, and no `audit_log` row is written.

---

### User Story 2 — Duplicate webhook delivery produces exactly one paid booking and exactly one ticket (Priority: P1)

As the backend, when Moyasar retries a webhook it has already delivered, the second (and any subsequent) delivery is recognised by the idempotency key, immediately returns HTTP 200 without re-processing, and leaves the database in exactly the same state as after the first delivery — one `paid` booking and one ticket row.

**Why this priority.** Payment gateways retry webhooks; processing a webhook twice could create duplicate tickets or double-confirm a booking. Idempotency is an explicit evaluation criterion ("duplicate deliveries result in exactly one ticket").

**Independent test.** Call `handle_payment_webhook` twice with identical payload and valid signature. Assert the booking is `paid`, there is exactly one row in `tickets`, and the second call returns without raising an error (idempotent success path).

**Acceptance scenarios.**

1. **Given** a webhook has already been processed for `booking_id` (booking is `paid`, ticket exists), **When** `handle_payment_webhook` is called again with the same payload and signature, **Then** the function returns without error, `tickets` still contains exactly one row for the booking, and no duplicate `audit_log` entry is written.
2. **Given** two concurrent deliveries of the same webhook, **When** both calls reach `handle_payment_webhook` simultaneously, **Then** exactly one wins the idempotency lock, the other returns the cached success, and the booking has exactly one ticket row after both calls complete.

---

### User Story 3 — A screenshotted or forged QR is rejected because the HMAC token does not verify (Priority: P1)

As the door-scan system, when a QR code is presented that encodes a raw booking id, an expired token, or a token whose HMAC signature does not match the server key, `verify_qr_token(token)` raises `InvalidQRTokenError` and denies entry — even if the booking id itself exists in the database.

**Why this priority.** Ticket fraud prevention (screenshotted QR must not grant entry) is an explicit evaluation criterion. This story is independently testable without any payment flow: generate a valid token with `sign_qr_token`, tamper with one field, call `verify_qr_token`, and assert the error.

**Independent test.** Call `sign_qr_token(booking_id, seat_ids, nonce)` to produce a valid token. Then verify the valid token succeeds. Then produce three invalid tokens — one with a tampered booking id, one with a tampered seat list, one with a wrong HMAC — and assert all three raise `InvalidQRTokenError`.

**Acceptance scenarios.**

1. **Given** a valid HMAC-signed QR token for booking B with seats [G12, G13], **When** `verify_qr_token(token)` is called, **Then** the result contains booking id and seat ids and no error is raised.
2. **Given** a token where the booking id has been replaced with a different id, **When** `verify_qr_token(tampered_token)` is called, **Then** `InvalidQRTokenError` is raised.
3. **Given** a token where the HMAC has been changed or truncated, **When** `verify_qr_token(bad_hmac_token)` is called, **Then** `InvalidQRTokenError` is raised.
4. **Given** a bare booking id string (not a signed token), **When** `verify_qr_token(raw_id)` is called, **Then** `InvalidQRTokenError` is raised.

---

### User Story 4 — PDF ticket is generated and emailed; agent receives in-chat ticket card data (Priority: P2)

As the booking agent, after a booking is marked `paid`, I call `generate_ticket_pdf(booking_id)` to produce a bilingual (Arabic/English) PDF ticket with an embedded HMAC-signed QR code, and then `send_ticket_email(booking_id)` to deliver it to the buyer's email address. I also call `get_booking_status(booking_id)` to retrieve the structured ticket-card data (event, seats, PDF path, QR thumbnail) for rendering in-chat.

**Why this priority.** Ticket delivery is the final fulfilment step and a graded deliverable, but it can function independently of the idempotency logic tested in US2, using a `paid` fixture booking directly.

**Independent test.** Create a `paid` booking fixture. Call `generate_ticket_pdf(booking_id)` and assert a non-empty bytes/file result is returned and a `tickets` row is created with `pdf_path` set and `qr_token` non-empty. Call `send_ticket_email(booking_id)` in sandbox mode and assert `tickets.emailed_at` is set. Call `get_booking_status(booking_id)` and assert the returned status object contains `status="paid"`, `pdf_path`, and `qr_token`.

**Acceptance scenarios.**

1. **Given** a booking in `paid` status, **When** `generate_ticket_pdf(booking_id)` is called, **Then** a `tickets` row is created with a non-null `pdf_path` (or bytes), a non-null HMAC `qr_token`, and an `issued_at` timestamp.
2. **Given** a `tickets` row with a `pdf_path`, **When** `send_ticket_email(booking_id)` is called in sandbox mode, **Then** `tickets.emailed_at` is set to now and no error is raised.
3. **Given** a `paid` booking, **When** `get_booking_status(booking_id)` is called, **Then** the returned object includes `status="paid"`, `event_title`, `seat_ids`, `pdf_path`, and `qr_token`.

---

### User Story 5 — A hold that expires before payment releases its seats and the agent can tell the user (Priority: P2)

As the booking agent, when a payment session is created but the user does not pay before the 10-minute hold TTL expires, the hold-sweeper (from F001) marks the booking `expired`, releases the seats back to `available`, and `get_booking_status` returns `status="expired"` so the agent can inform the user and offer to restart.

**Why this priority.** Hold expiry is already partly covered in F001 (seat release mechanics); this story proves the booking lifecycle transition (`pending_payment → expired`) and the agent-facing status tool work correctly together. It is independently testable with a fake clock.

**Independent test.** Create a booking in `pending_payment` with `holds.expires_at` set to 1 second in the past (via freezegun). Run `release_expired_holds()`. Assert the booking status becomes `expired`, each seat returns to `available`, and `get_booking_status(booking_id)` returns `status="expired"`.

**Acceptance scenarios.**

1. **Given** a booking in `pending_payment` with an expired hold (TTL elapsed), **When** `release_expired_holds()` is called, **Then** the booking status is `expired`, the seats return to `available`, and an `audit_log` row records `pending_payment → expired`.
2. **Given** a booking in `expired` status, **When** `get_booking_status(booking_id)` is called, **Then** the returned object contains `status="expired"` and no `pdf_path` or `qr_token`.

---

### Edge Cases

- `create_payment_session` called on a booking NOT in `held` status (e.g., already `paid`, `cancelled`, or `expired`): raises `BookingStateError`; no payment session is created.
- `create_payment_session` called without a prior confirmed hold (F002's HITL gate not passed): the booking record will not exist in `held` status, so the `BookingStateError` above covers this case — no payment URL is ever issued without the confirmation gate.
- Webhook arrives for an unknown `session_id` or unknown `booking_id`: raises `WebhookBookingNotFoundError`; returns HTTP 404 to the gateway so it retries.
- Webhook arrives after the booking has already expired: rejected with `BookingStateError`; the gateway receives HTTP 409 and does not retry.
- `generate_ticket_pdf` called on a booking not in `paid` status: raises `BookingStateError`.
- `send_ticket_email` called when `tickets.pdf_path` is null (PDF not yet generated): raises `TicketNotReadyError`.
- Email delivery fails (sandbox error): exception propagates; `emailed_at` is NOT set; the caller may retry.
- QR token nonce collision (extremely unlikely): the nonce is a `secrets.token_hex(16)`; no special handling needed, probability negligible.
- Missing `MOYASAR_WEBHOOK_SECRET` or `QR_HMAC_KEY` env vars: startup raises `ConfigurationError` before any request is served.
- Fake gateway used in production (env `PAYMENT_GATEWAY=fake` with `ENV=production`): raises `ConfigurationError` at startup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a `PaymentGateway` Protocol with `create_session(booking_id, amount_halalas, currency, callback_url) -> PaymentSession` and a `MoyasarGateway` (sandbox) and `FakeGateway` (offline tests) implementing it; the active implementation MUST be selected by a config flag (`PAYMENT_GATEWAY`).
- **FR-002**: `create_payment_session(booking_id)` MUST verify the booking is in `held` status, call the active `PaymentGateway`, write a `payments` row with `session_id`, advance the booking to `pending_payment`, write an `audit_log` row, and return the hosted-checkout URL and session id.
- **FR-003**: `handle_payment_webhook(payload: bytes, signature: str)` MUST verify the Moyasar HMAC signature over the raw `payload` bytes using `MOYASAR_WEBHOOK_SECRET` before any DB mutation; a signature mismatch MUST raise `WebhookSignatureError` and leave the booking unchanged.
- **FR-004**: `handle_payment_webhook` MUST be idempotent: before processing, it MUST check whether the `payments.idempotency_key` (derived from the webhook payload's unique event id) has already been seen; if so, it MUST return immediately without any further DB writes.
- **FR-005**: On a successful, first-time webhook delivery, `handle_payment_webhook` MUST advance the booking to `paid`, set `payments.signature_verified = True`, write an `audit_log` row for the `pending_payment → paid` transition, and trigger `generate_ticket_pdf` + `send_ticket_email` in the same logical flow.
- **FR-006**: `sign_qr_token(booking_id, seat_ids, nonce) -> str` MUST produce a URL-safe base64 token encoding booking id, seat ids, nonce, and an HMAC-SHA256 digest over those fields using `QR_HMAC_KEY`; `verify_qr_token(token) -> QRPayload` MUST verify the digest using `hmac.compare_digest` and raise `InvalidQRTokenError` if invalid or malformed.
- **FR-007**: `generate_ticket_pdf(booking_id)` MUST verify the booking is `paid`, generate a PDF ticket (ReportLab or WeasyPrint) with a bilingual (Arabic/English) layout, embed a QR code image produced from a fresh `sign_qr_token` call, write the PDF to a file or store as bytes, and create (or update) the `tickets` row with `pdf_path`, `qr_token`, and `issued_at`.
- **FR-008**: `send_ticket_email(booking_id)` MUST verify `tickets.pdf_path` is set, send the PDF as an email attachment to `bookings.buyer_email` via the configured SMTP/SendGrid/Resend sandbox adapter, and set `tickets.emailed_at` on success.
- **FR-009**: `get_booking_status(booking_id)` MUST return a `BookingStatusOut` Pydantic object containing `booking_id`, `status`, `event_title`, `seat_ids`, `total_sar`, `pdf_path` (null if not yet generated), `qr_token` (null if not yet generated), and `emailed_at` (null if not yet sent).
- **FR-010**: Every booking status transition (`held → pending_payment`, `pending_payment → paid`, `pending_payment → expired`, `paid → cancelled`) MUST be recorded in `audit_log` with timestamp, tool name, and the triggering entity (booking id, session id, or webhook idempotency key) — PII (buyer email) MUST be redactable at INFO log level.
- **FR-011**: Money values passed to the payment gateway MUST be taken from `bookings.total` (stored as integer halalas from F001's `compute_quote`); the gateway adapter MUST NOT accept a caller-supplied amount.
- **FR-012**: The `FakeGateway` MUST be usable without any network call; it MUST support a `simulate_webhook(booking_id)` helper that generates a correctly-signed fake webhook payload for use in unit tests.

### Key Entities

- **Payment**: booking_id (FK), gateway (`moyasar`/`fake`), session_id, status (`pending`/`paid`/`failed`/`refunded`), idempotency_key, signature_verified (bool), raw_webhook_payload (bytes, stored for audit), created_at, updated_at.
- **Ticket**: booking_id (FK, unique), pdf_path (str or null), qr_token (str — the HMAC-signed token), issued_at (datetime or null), emailed_at (datetime or null).
- **QRPayload**: booking_id, seat_ids (list[str]), nonce (str), hmac_digest (str) — this is the decoded, verified structure returned by `verify_qr_token`.
- **PaymentSession**: session_id (str), checkout_url (str), gateway (str), expires_at (datetime) — the return type of `create_payment_session`.
- **BookingStatusOut**: booking_id, status, event_title, venue, event_datetime, seat_ids, total_sar (Decimal), pdf_path, qr_token, emailed_at.

## Success Criteria *(mandatory)*

- **SC-001**: `handle_payment_webhook` with a valid signature and first-time idempotency key advances the booking to `paid` and creates exactly one `tickets` row — verified by unit test.
- **SC-002**: Calling `handle_payment_webhook` twice with the same payload and valid signature leaves exactly one `tickets` row and one `payments` row — verified by idempotency unit test.
- **SC-003**: `verify_qr_token` rejects a token with a tampered booking id, a tampered seat list, and a wrong HMAC — all three cases pass in a single parametrised pytest.
- **SC-004**: A booking whose hold expires before payment is processed reaches `expired` status and its seats return to `available` — verified by freezegun test.
- **SC-005**: `generate_ticket_pdf` on a `paid` fixture booking returns non-empty bytes, creates a `tickets` row with non-null `qr_token`, and the QR token passes `verify_qr_token`.
- **SC-006**: `send_ticket_email` in sandbox mode sets `tickets.emailed_at` without raising an error.
- **SC-007**: A webhook with a missing or invalid signature raises `WebhookSignatureError` and leaves the booking in its prior state — verified by unit test.
- **SC-008**: All payment/fulfilment tools pass `pytest` in under 30 seconds on a fresh clone; coverage on `src/booking_agent/payments/` and `src/booking_agent/fulfilment/` ≥ 85%.

## Assumptions

- F001 (Foundation) is complete: `bookings`, `payments`, `tickets`, `audit_log`, `holds`, and `seats` tables exist; `compute_quote`, `place_seat_hold`, and `release_expired_holds` are available.
- F002 (Agent & Confirmation Gate) has run the HITL confirmation step before F003 is invoked — `create_payment_session` cannot be called on a booking that has not reached `held` status, which is only possible after F002 has called `create_booking` post-confirmation.
- F004 (API Layer) will wire `POST /payments/webhook` to `handle_payment_webhook`; this feature implements the handler only, not the HTTP route.
- The Moyasar sandbox is used; no real money is charged. Credentials live in `.env` (`MOYASAR_SECRET_KEY`, `MOYASAR_PUBLISHABLE_KEY`, `MOYASAR_WEBHOOK_SECRET`, `MOYASAR_CALLBACK_URL`).
- `QR_HMAC_KEY` is a random 32-byte hex string in `.env`; it is never committed to the repository.
- PDF generation uses ReportLab or WeasyPrint (team choice at implementation time); the spec is agnostic between the two.
- Email delivery uses an SMTP/SendGrid/Resend sandbox adapter selected by config (`EMAIL_ADAPTER`); no real emails are sent during tests.
- The `FakeGateway` is the default when `PAYMENT_GATEWAY=fake`; the `MoyasarGateway` is active when `PAYMENT_GATEWAY=moyasar`.
- SAR is the only currency; all amounts stored as integer halalas; the gateway receives halalas.
- Hold TTL remains 10 minutes (as established in F001); payment sessions created after TTL expiry are rejected by the `BookingStateError` guard.
