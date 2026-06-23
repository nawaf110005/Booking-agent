# Implementation Plan: FastAPI Backend — HTTP Surface & Session Management

**Branch**: `004-api` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-api/spec.md`

## Summary

Build the FastAPI application layer that exposes every HTTP endpoint the
Streamlit UI and the Moyasar payment gateway need. The layer routes requests
to the agent (F002), the booking tools (F001), and the payment/fulfilment
handler (F003) — it does not reimplement their logic. Key additions: a
`create_app()` factory with CORS + lifespan, an in-memory `SessionStore` that
builds and caches the LangChain agent once per session, eight router modules
covering chat, events, seat-map, quote, bookings, payments, HITL, and admin,
and a full Pydantic schema layer. Webhook signature verification and
idempotency honour Constitution V; approve/reject endpoints enforce
Constitution I; request and tool logging enforces Constitution VII.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI 0.111+, uvicorn, pydantic v2, pydantic-settings, httpx (test client), pytest-asyncio

**Storage**: SQLite (dev/demo) via `DATABASE_URL` inherited from F001; no new tables introduced by this feature

**Testing**: pytest, pytest-asyncio, httpx `AsyncClient`, respx (mock HTTP for Moyasar if needed)

**Target Platform**: Local backend server (Windows/macOS/Linux); offline-capable except for the LLM provider API call

**Project Type**: Single Python project (`src/booking_agent/`) — `api/` sub-package added alongside existing `db/`, `tools/`, `agent/`

**Performance Goals**: `/v1/healthz` < 50ms; agent message round-trip < 30s (LLM-bound); seat-map PNG < 500ms

**Constraints**: CORS allowlist enforced; admin token non-empty enforced at startup; webhook signature verified before any DB write; no user auth (MVP)

**Scale/Scope**: Single-process, single-writer SQLite demo; a few concurrent Streamlit users at most

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | `/v1/sessions/{id}/approve` and `/v1/sessions/{id}/reject` are the explicit HITL gate; the payment router MUST NOT issue a payment URL without a prior approval signal. ✅ |
| II. Atomic, Time-Bounded Seat Holds | This layer does not implement holds; it delegates to F001 `place_seat_hold` (10-min TTL). `/v1/admin/sweep` calls `release_expired_holds` to maintain TTL discipline. ✅ |
| III. Tools Are Python Functions | The API is a thin HTTP wrapper; all capability lives in `booking_agent.tools.*` and `booking_agent.agent.*`. No new tool logic introduced here. ✅ |
| IV. Exact, Auditable Money | `/v1/quote` delegates entirely to `compute_quote` (F001); no money arithmetic in the API layer. ✅ |
| V. Tamper-Evident Tickets & Exactly-Once Fulfilment | `/v1/payments/webhook` reads raw body + `X-Moyasar-Signature`, rejects invalid signatures with 400, and delegates idempotent processing to F003 `handle_payment_webhook`. ✅ |
| VI. Test-First for Data & Money Operations | The API layer contains no money or DB-write logic of its own; the test-first mandate applies to F001/F003. API tests use `httpx.AsyncClient` against a test app with seeded DB. ✅ |
| VII. Observable Reasoning | A logging middleware records every request (method, path, session_id, status) and the `SessionStore` forwards tool-call events to the audit log via F001. ✅ |
| VIII. MVP First, Multi-Agent Later | Single-agent `BookingAgent` from F002 is wired; no LangGraph or multi-agent plumbing introduced. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/004-api/
├── spec.md              # Feature spec
├── plan.md              # This file
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── config.py                        # Extended: CORS_ORIGINS, ADMIN_TOKEN, SERVER_HOST/PORT
├── api/
│   ├── __init__.py
│   ├── app.py                       # create_app() factory: CORS + logging middleware + lifespan + router includes
│   ├── deps.py                      # Depends helpers: get_session_store, get_db, require_admin_token
│   ├── schemas.py                   # All request/response Pydantic models for the API surface
│   ├── store.py                     # SessionStore (session_id → ChatSession; builds agent once; thread-safe)
│   └── routers/
│       ├── __init__.py
│       ├── health.py                # GET /v1/healthz
│       ├── chat.py                  # POST /v1/sessions; GET + POST /v1/sessions/{id}/messages; POST /v1/sessions/{id}/approve; POST /v1/sessions/{id}/reject
│       ├── events.py                # GET /v1/events; GET /v1/events/{id}
│       ├── seatmap.py               # GET /v1/events/{id}/seatmap.png?category=…
│       ├── quote.py                 # POST /v1/quote
│       ├── bookings.py              # GET /v1/bookings/{id}
│       ├── payments.py              # POST /v1/payments/webhook
│       └── admin.py                 # POST /v1/admin/init-db; /admin/seed; /admin/sweep

tests/
├── conftest.py                      # Extended: async test client fixture, override_get_db
└── test_api/
    ├── __init__.py
    ├── test_health.py               # GET /v1/healthz
    ├── test_chat.py                 # Session create, message round-trip, transcript restore, approve/reject
    ├── test_events.py               # List + detail
    ├── test_seatmap.py              # PNG response, 404 on bad event, 422 on missing category
    ├── test_quote.py                # Delegated to compute_quote; verify schema passthrough
    ├── test_bookings.py             # GET booking status
    ├── test_payments.py             # Webhook: valid sig → 200, duplicate → 200 idempotent, bad sig → 400
    └── test_admin.py                # Token-gated: 403 without token, 200 with token, idempotent seed
```

**Structure Decision**: Single-project `src/booking_agent/` layout, adding `api/` as a sibling of `db/`, `tools/`, `agent/`, and `fulfilment/`. All API-layer tests live in `tests/test_api/` to keep them separate from F001 tool tests. No second project, no frontend directory — the Streamlit UI (F005) is a separate sibling package that calls this API over HTTP.

## Phase 0 — Research / Decisions

- **CORS allowlist**: `CORS_ORIGINS` is a comma-separated env var parsed into a list by Pydantic Settings. Defaults to `["http://localhost:8501"]` for the Streamlit dev origin. Wildcard `*` is explicitly forbidden in settings validation (security).
- **SessionStore concurrency**: Python's GIL plus a `threading.Lock` around the `sessions` dict is sufficient for the single-process MVP. Each `ChatSession` holds one `asyncio.Event` for the HITL approval future; concurrent message calls on the same session are rejected with 409.
- **Webhook raw body**: FastAPI's `Request.body()` is called before Pydantic validation so the raw bytes are available for HMAC verification. The router uses `APIRoute` with `request: Request` as the first parameter to access raw bytes alongside the parsed header.
- **Streaming the seat-map PNG**: `fastapi.responses.StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")` with `Content-Length` header set to avoid chunked encoding surprises in Streamlit.
- **Admin token validation**: Timing-safe comparison (`hmac.compare_digest`) to prevent timing attacks on the token check.
- **Startup validation**: Pydantic `@field_validator` on `Settings.ADMIN_TOKEN` raises `ValueError` on empty string; FastAPI lifespan propagates the error and exits before binding.

## Phase 1 — Design Artifacts

- All request/response schemas are finalised in `schemas.py` before any router is coded. The `AgentResponse.response_type` enum drives the Streamlit UI's rendering logic and must be stable.
- `store.py` `ChatSession` dataclass finalised: `session_id`, `agent` (LangChain `AgentExecutor`), `history` (list of `AgentResponse`), `pending_approval` (`threading.Event | None`), `lock` (`threading.Lock`).
- Dependency graph: `deps.py` provides `get_session_store` (singleton from `app.state`), `get_db` (per-request SQLAlchemy session via generator), and `require_admin_token` (header check with 403 on failure).

## Complexity Tracking

No constitution violations — table intentionally empty.
