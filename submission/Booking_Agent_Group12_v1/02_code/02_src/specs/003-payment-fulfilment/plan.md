# Implementation Plan: Payment & Ticket Fulfilment

**Branch**: `003-payment-fulfilment` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-payment-fulfilment/spec.md`

## Summary

Wire the payment round-trip and ticket delivery layer on top of the F001 schema.
Two new module families: `src/booking_agent/payments/` (gateway abstraction,
session creation, webhook handling, idempotency) and `src/booking_agent/fulfilment/`
(PDF generation, HMAC QR signing/verification, email dispatch, booking status).
The Moyasar sandbox adapter sits behind a `PaymentGateway` Protocol so the Fake
gateway keeps the full test suite offline-capable. Every booking state transition
is audit-logged; webhook handling is signature-verified and idempotency-keyed so
duplicate deliveries produce exactly one paid booking and exactly one ticket.
No payment session is ever created without the F002 confirmation gate having
first advanced the booking to `held` status (Constitution I).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings, httpx (Moyasar REST calls), reportlab or weasyprint (PDF), qrcode, Pillow (QR image), smtplib / sendgrid / resend (email sandbox)

**Storage**: SQLite (dev/test/demo) via `DATABASE_URL`; PostgreSQL-compatible; existing `payments` and `tickets` tables from F001 migration

**Testing**: pytest, pytest-cov, freezegun (hold-expiry tests), pytest-asyncio if async needed for email sandbox

**Target Platform**: Local backend (Windows/macOS/Linux); offline-capable via `FakeGateway`

**Project Type**: Single Python project (`src/booking_agent/`) — extends F001 layout; no new top-level project

**Performance Goals**: `create_payment_session` < 500 ms (Moyasar sandbox RTT); `generate_ticket_pdf` < 2 s; webhook handler < 100 ms (pure DB + crypto, no network)

**Constraints**: Webhook handler MUST verify signature before any DB mutation; idempotency check MUST be a single atomic read-and-lock; no float money anywhere; secrets in `.env` only

**Scale/Scope**: Same demo scale as F001 (single-writer SQLite, a few bookings per demo run); Postgres row-lock path documented

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | `create_payment_session` verifies the booking is in `held` status, which is only reachable after F002's HITL confirmation gate has run. No payment URL is ever generated without that gate. ✅ |
| II. Atomic, Time-Bounded Holds | This feature reuses the F001 hold mechanics. Hold expiry during payment (`pending_payment → expired`) is explicitly handled: `release_expired_holds` releases seats and the booking transitions to `expired` with an audit log entry. ✅ |
| III. Tools Are Python Functions | `create_payment_session`, `handle_payment_webhook`, `generate_ticket_pdf`, `verify_qr_token`, `send_ticket_email`, `get_booking_status` are all in-repo typed Python functions. The Moyasar gateway is isolated behind a `PaymentGateway` Protocol; all other tools remain offline-capable via `FakeGateway`. ✅ |
| IV. Exact, Auditable Money | Payment amount is taken directly from `bookings.total` (integer halalas set by F001's `compute_quote`). The gateway adapter does not accept a caller-supplied amount. No float conversion anywhere in the payment or ticket path. ✅ |
| V. Tamper-Evident Tickets & Exactly-Once Fulfilment | QR tokens are HMAC-SHA256 signed (booking id + seat ids + nonce); `verify_qr_token` uses `hmac.compare_digest`. Webhook idempotency key prevents duplicate ticket creation. This is the **primary delivery surface** for Principle V. ✅ |
| VI. Test-First for Data & Money Operations | `handle_payment_webhook` (DB-writing), `sign_qr_token`/`verify_qr_token` (security-critical), and `generate_ticket_pdf` (creates `tickets` row) all have unit tests written and failing before implementation begins. ✅ |
| VII. Observable Reasoning | Every booking state transition (`held → pending_payment`, `pending_payment → paid`, `pending_payment → expired`) is written to `audit_log` with timestamp, tool name, booking id, and session/idempotency id. PII (buyer email) is redacted at INFO log level. ✅ |
| VIII. MVP First, Multi-Agent Later | This feature extends the single-agent MVP tool surface. No LangGraph or multi-agent structure is introduced. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-payment-fulfilment/
├── plan.md              # This file
├── spec.md              # Feature spec
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── config.py                       # Extended: PAYMENT_GATEWAY, MOYASAR_SECRET_KEY,
│                                   #   MOYASAR_PUBLISHABLE_KEY, MOYASAR_WEBHOOK_SECRET,
│                                   #   MOYASAR_CALLBACK_URL, QR_HMAC_KEY, EMAIL_ADAPTER
├── payments/
│   ├── __init__.py
│   ├── gateway.py                  # PaymentGateway Protocol + MoyasarGateway + FakeGateway
│   ├── session.py                  # create_payment_session(booking_id) → PaymentSession
│   ├── webhook.py                  # handle_payment_webhook(payload, signature)
│   └── idempotency.py              # idempotency key check + lock (read-before-write)
├── fulfilment/
│   ├── __init__.py
│   ├── ticket_pdf.py               # generate_ticket_pdf(booking_id) → bytes / path
│   ├── qr.py                       # sign_qr_token, verify_qr_token, InvalidQRTokenError
│   └── email.py                    # send_ticket_email(booking_id); SMTPAdapter / SendGridAdapter
├── tools/
│   └── booking_status.py           # get_booking_status(booking_id) → BookingStatusOut
│                                   #   (new tool; joins bookings + tickets + events)

migrations/
└── versions/
    └── 0002_payments_tickets_fulfilment.py   # No new tables needed (F001 created them);
                                              # migration adds payments.raw_webhook_payload col
                                              # if not already present

tests/
├── conftest.py                     # Extended: paid_booking fixture, fake_gateway fixture
└── test_payment/
    ├── test_session.py             # create_payment_session: held → pending_payment, bad states
    ├── test_webhook.py             # handle_payment_webhook: valid sig, bad sig, idempotency
    ├── test_idempotency.py         # concurrent duplicate delivery → exactly one ticket
    └── test_expiry.py              # pending_payment + expired hold → expired booking (freezegun)
└── test_fulfilment/
    ├── test_qr.py                  # sign_qr_token + verify: valid, tampered id, tampered seats,
    │                               #   wrong hmac, raw id
    ├── test_ticket_pdf.py          # generate_ticket_pdf: paid fixture → bytes + tickets row
    ├── test_email.py               # send_ticket_email: sandbox adapter sets emailed_at
    └── test_booking_status.py      # get_booking_status: paid / expired / pending states
```

**Structure Decision**: Single-project `src/booking_agent/` layout continued from
F001. Two new sibling packages (`payments/`, `fulfilment/`) keep payment and
delivery concerns separate from the foundation tools (`tools/`) and the forthcoming
agent (`agent/`) and API (`api/`) layers. `get_booking_status` lives in `tools/`
rather than `payments/` or `fulfilment/` because it is a read-only query tool the
agent calls directly and should be co-located with the other agent-facing tools.

## Phase 0 — Research / Decisions

- **Moyasar webhook signature**: Moyasar signs webhook bodies with HMAC-SHA256 using
  the webhook secret; the signature is delivered in the `X-Moyasar-Signature` header
  as a hex digest. The handler recomputes `hmac.new(secret, raw_body, sha256).hexdigest()`
  and compares with `hmac.compare_digest` to prevent timing attacks.
- **Idempotency key**: derived from the Moyasar event id field in the webhook JSON body
  (`event.id`). Stored in `payments.idempotency_key`. On receipt, the handler reads the
  `payments` row for the matching session id inside a transaction; if `idempotency_key`
  is already set and matches, the handler returns immediately (no further writes). SQLite
  serialises this naturally; Postgres path uses `SELECT ... FOR UPDATE` on the `payments` row.
- **QR token encoding**: `json.dumps({"b": booking_id, "s": seat_ids, "n": nonce}) + "." + hmac_hex`.
  URL-safe base64 wraps the whole string. `verify_qr_token` base64-decodes, splits at the
  last `.`, recomputes HMAC over the JSON part, and uses `hmac.compare_digest`.
- **PDF library**: team chooses ReportLab (lower system deps) or WeasyPrint (HTML template).
  `generate_ticket_pdf` returns bytes; caller writes to `TICKET_PDF_DIR` (config).
  Bilingual layout: English header + Arabic event title (RTL via bidi library if WeasyPrint,
  or a pre-rendered Arabic font glyph path with ReportLab).
- **Email adapter**: `SMTPAdapter` uses `smtplib` + Mailtrap/Ethereal sandbox for tests.
  `SendGridAdapter` and `ResendAdapter` are thin wrappers selected by `EMAIL_ADAPTER` config.
  All adapters implement an `EmailGateway` Protocol (`send(to, subject, body, attachments)`).
- **FakeGateway.simulate_webhook**: generates a JSON payload mirroring Moyasar's structure,
  computes the correct HMAC signature with the test secret (`TEST_WEBHOOK_SECRET`), and
  returns `(payload_bytes, signature_hex)` for use in unit tests.
- **Money in gateway call**: `MoyasarGateway.create_session` reads `bookings.total` (halalas)
  directly from the DB row passed to it; no amount parameter is accepted from the caller.

## Phase 1 — Design Artifacts

- `PaymentGateway` Protocol: `create_session(booking_id, amount_halalas, currency, callback_url) -> PaymentSession`; selected via `config.PAYMENT_GATEWAY`.
- `PaymentSession` Pydantic model: `session_id (str)`, `checkout_url (str)`, `gateway (str)`, `expires_at (datetime)`.
- `BookingStatusOut` Pydantic model: `booking_id (int)`, `status (BookingStatus)`, `event_title (str)`, `venue (str)`, `event_datetime (datetime)`, `seat_ids (list[str])`, `total_sar (Decimal)`, `pdf_path (str | None)`, `qr_token (str | None)`, `emailed_at (datetime | None)`.
- `QRPayload` Pydantic model: `booking_id (int)`, `seat_ids (list[str])`, `nonce (str)`.
- Error hierarchy extension in `tools/errors.py`: `WebhookSignatureError`, `WebhookBookingNotFoundError`, `BookingStateError`, `TicketNotReadyError`, `InvalidQRTokenError`, `ConfigurationError`.
- Alembic migration `0002` adds `payments.raw_webhook_payload (LargeBinary, nullable)` if not present from F001.

## Complexity Tracking

No constitution violations — table intentionally empty.
