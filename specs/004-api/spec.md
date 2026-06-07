# Feature Specification: FastAPI Backend — HTTP Surface & Session Management

**Feature Branch**: `004-api`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "The HTTP surface that binds the chat UI and the payment gateway to the agent and tools. Endpoints under /v1: GET /healthz, POST /sessions, POST /sessions/{id}/messages (agent drive), GET /sessions/{id}/messages (transcript restore), POST /sessions/{id}/approve and /reject (HITL helpers), GET /events and GET /events/{id}, GET /events/{id}/seatmap.png, POST /quote, GET /bookings/{id}, POST /payments/webhook (signature-verified, idempotent, calls F003), POST /admin/init-db, /admin/seed, /admin/sweep (X-Admin-Token gated). CORS allowlist for Streamlit. In-memory SessionStore. FastAPI lifespan. Modules: src/booking_agent/api/ (app.py, deps.py, schemas.py, store.py, routers/)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Drive the agent via chat and restore the transcript (Priority: P1)

As a Streamlit frontend (or any HTTP client), I can POST a message to a session and receive a structured agent response; I can also GET the full transcript to restore an ongoing conversation after a page refresh.

**Why this priority.** The chat message endpoint is the primary integration point for the entire product. Without it, the agent is unreachable from any UI. Transcript restore is coupled here because the GET endpoint shares the same session store and is essential for session continuity — a graded requirement for memory quality.

**Independent test.** Start the API server with a mock agent stub; POST `/v1/sessions` to create a session; POST `/v1/sessions/{id}/messages` with `{"role":"user","content":"Coldplay Riyadh"}` and assert a 200 response whose body matches the `AgentResponse` schema (has `role`, `content`, `response_type`). Then GET `/v1/sessions/{id}/messages` and assert the full turn list is returned.

**Acceptance Scenarios**:

1. **Given** no session exists, **When** POST `/v1/sessions` is called, **Then** a 201 response returns a new `session_id` UUID and an empty transcript.
2. **Given** a valid `session_id`, **When** POST `/v1/sessions/{id}/messages` is called with a user message, **Then** the agent processes it and the response body contains `role`, `content`, and a non-null `response_type` (`clarification` | `event_cards` | `quote` | `seat_map` | `confirmation` | `payment_link` | `ticket`).
3. **Given** a session with two completed turns, **When** GET `/v1/sessions/{id}/messages` is called, **Then** both user and agent messages are returned in order with timestamps.
4. **Given** an unknown `session_id`, **When** GET `/v1/sessions/{id}/messages` is called, **Then** a 404 response is returned.

---

### User Story 2 — Webhook verifies signature and is idempotent (Priority: P1)

As the Moyasar payment gateway, I can POST a signed payment webhook to `/v1/payments/webhook`; the server verifies the signature, processes the payment exactly once even if the webhook fires multiple times, and returns 200 on all deliveries.

**Why this priority.** Signature verification and idempotency are non-negotiable graded criteria ("webhook robustness: duplicate deliveries result in exactly one ticket"). A missing or broken webhook handler means the system never completes a booking after payment.

**Independent test.** Call the endpoint with a valid HMAC-signed body matching a seeded booking; assert 200 and that the booking moves to `paid`. Call the identical payload a second time; assert 200 again and that the booking is still `paid` (no duplicate processing). Call with a tampered signature; assert 400.

**Acceptance Scenarios**:

1. **Given** a valid Moyasar webhook payload with correct `X-Moyasar-Signature` header, **When** POST `/v1/payments/webhook` is called, **Then** the booking is marked paid (delegated to F003 `handle_payment_webhook`) and 200 is returned.
2. **Given** the identical webhook payload is re-delivered, **When** POST `/v1/payments/webhook` is called again, **Then** the handler is idempotent: 200 is returned and exactly one paid booking and one ticket exist.
3. **Given** a webhook body with an invalid or missing signature, **When** POST `/v1/payments/webhook` is called, **Then** 400 is returned and no booking is mutated.

---

### User Story 3 — HITL approve/reject endpoints gate payment (Priority: P1)

As the Streamlit UI, I can POST to `/v1/sessions/{id}/approve` or `/v1/sessions/{id}/reject` to resolve the pending human-in-the-loop confirmation step, and the agent continues or cancels the booking accordingly.

**Why this priority.** Constitution Principle I makes "confirmation before payment" non-negotiable. The approve/reject endpoints are the HTTP gate that enforces this — without them, the UI cannot signal user consent and the agent has no server-side hook to proceed to payment.

**Independent test.** Drive a session to the `pending_approval` state via a stubbed agent; POST `/v1/sessions/{id}/approve`; assert 200 and that the session state transitions toward `payment_link`. POST `/v1/sessions/{id}/reject`; assert 200 and that the hold is released and state returns to `idle`.

**Acceptance Scenarios**:

1. **Given** a session in `pending_approval` state, **When** POST `/v1/sessions/{id}/approve` is called, **Then** 200 is returned and the agent proceeds to create the payment session.
2. **Given** a session in `pending_approval` state, **When** POST `/v1/sessions/{id}/reject` is called, **Then** 200 is returned, the seat hold is released, and the conversation is reset to an idle state.
3. **Given** a session NOT in `pending_approval` state, **When** POST `/v1/sessions/{id}/approve` is called, **Then** 409 is returned with an explanatory error message.

---

### User Story 4 — Seat-map PNG endpoint returns a live image (Priority: P2)

As the Streamlit frontend, I can GET `/v1/events/{id}/seatmap.png?category=Gold` and receive a `image/png` response that reflects the current availability of seats in that category.

**Why this priority.** Inline seat-map rendering in chat is a graded deliverable ("visual seat selection — agent renders a generated seat-map image"). This endpoint makes the existing `render_seat_map` tool reachable over HTTP without coupling the tool to the API layer.

**Independent test.** Seed an event with mixed available/held/sold seats; GET the endpoint for the Gold category; assert `Content-Type: image/png`, `Content-Length > 0`, and a 200 status. Repeat with an unknown `event_id` and assert 404. Repeat with an unknown `category` and assert 422.

**Acceptance Scenarios**:

1. **Given** a valid `event_id` and `category` query parameter, **When** GET `/v1/events/{id}/seatmap.png?category=Gold` is called, **Then** a `image/png` response is returned with status 200 and non-zero body.
2. **Given** an unknown `event_id`, **When** GET `/v1/events/{id}/seatmap.png` is called, **Then** 404 is returned.
3. **Given** a missing `category` query parameter, **When** GET `/v1/events/{id}/seatmap.png` is called, **Then** 422 is returned.

---

### User Story 5 — Admin endpoints are token-gated (Priority: P2)

As an operator, I can POST to `/v1/admin/init-db`, `/v1/admin/seed`, and `/v1/admin/sweep` with a valid `X-Admin-Token` header to initialise, seed, or sweep expired holds; these operations are rejected without the correct token.

**Why this priority.** Constitution Security section requires "admin-only operations gated behind an admin token and themselves logged." The admin surface is required for the demo bootstrap and hold-expiry maintenance, but must not be reachable anonymously.

**Independent test.** POST `/v1/admin/seed` without a token; assert 403. POST with the correct `X-Admin-Token`; assert 200 and that seed data is present. POST again (idempotent); assert 200.

**Acceptance Scenarios**:

1. **Given** a request with no `X-Admin-Token` header, **When** POST `/v1/admin/seed` is called, **Then** 403 is returned and no mutation occurs.
2. **Given** a request with an incorrect `X-Admin-Token`, **When** POST `/v1/admin/seed` is called, **Then** 403 is returned.
3. **Given** a request with the correct `X-Admin-Token`, **When** POST `/v1/admin/seed` is called, **Then** 200 is returned and the catalog is seeded (idempotent on re-run).
4. **Given** a request with the correct token, **When** POST `/v1/admin/sweep` is called, **Then** 200 is returned and expired holds are released.

---

### Edge Cases

- What happens when the agent raises an exception mid-turn? The router catches it, logs it, and returns a structured `500` with a safe error message (no stack trace to client).
- How does the system handle a session that has expired or been garbage-collected from the in-memory store? Returns 404; the client must create a new session.
- What happens when `POST /v1/sessions/{id}/messages` is called while a previous agent invocation for the same session is still running? Returns 409 to prevent concurrent agent invocations on the same session.
- What if the webhook arrives before the booking record exists (race with `create_booking`)? The handler returns 202 and the event is queued for retry, or 400 if the payload is malformed.
- What happens when CORS preflight is sent from a non-allowlisted origin? FastAPI CORS middleware returns 403; the Streamlit origin is in the allowlist via `CORS_ORIGINS` setting.
- What if the `seatmap.png` render raises `NotFoundError` (no seats for that category)? The router translates the tool error to 404.
- What if the `X-Admin-Token` is configured as an empty string in `.env`? The server MUST refuse to start (Settings validator raises `ValueError`) — never allow an empty token to bypass the gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a FastAPI application created by a factory function `create_app()` in `src/booking_agent/api/app.py`, configured via Pydantic Settings, with a lifespan that initialises the `SessionStore` and disposes resources on shutdown.
- **FR-002**: System MUST apply CORS middleware allowing only the origins listed in `CORS_ORIGINS` (at minimum the Streamlit dev origin), supporting the `Authorization` and `Content-Type` headers.
- **FR-003**: System MUST expose GET `/v1/healthz` returning `{"status":"ok","extractor_mode":"<value>","llm_provider":"<value>","llm_model":"<value>","last_error":"<value>|null"}` without authentication.
- **FR-004**: System MUST expose POST `/v1/sessions` (create session, returns `session_id`) and GET/POST `/v1/sessions/{session_id}/messages` (transcript and agent drive).
- **FR-005**: POST `/v1/sessions/{session_id}/messages` MUST call the LangChain agent (obtained from the `SessionStore`) with the user message and return the structured `AgentResponse`; it MUST be idempotent with respect to the message ID if one is supplied.
- **FR-006**: System MUST expose POST `/v1/sessions/{session_id}/approve` and POST `/v1/sessions/{session_id}/reject` as the HITL gate (Constitution I); both endpoints MUST resolve or cancel the pending approval future held in session state and return 409 when no approval is pending.
- **FR-007**: System MUST expose GET `/v1/events` (list with optional `q`, `city`, `date` filters), GET `/v1/events/{event_id}` (detail), and GET `/v1/events/{event_id}/seatmap.png?category=<str>` (returns `StreamingResponse` with `media_type="image/png"` from `render_seat_map`).
- **FR-008**: System MUST expose POST `/v1/quote` accepting `QuoteRequest` and returning the itemised `Quote` DTO from `compute_quote` (base, discount, VAT 15%, total).
- **FR-009**: System MUST expose GET `/v1/bookings/{booking_id}` returning current booking status.
- **FR-010**: System MUST expose POST `/v1/payments/webhook` that reads the raw request body and the `X-Moyasar-Signature` header, then delegates to F003 `handle_payment_webhook(payload, signature)`; the endpoint MUST be idempotent and MUST reject requests with invalid/missing signatures with HTTP 400 (Constitution V).
- **FR-011**: System MUST expose POST `/v1/admin/init-db`, POST `/v1/admin/seed`, and POST `/v1/admin/sweep`, all gated by `X-Admin-Token` header validated against the `ADMIN_TOKEN` setting; requests without a valid token MUST return 403 and produce no mutation (Constitution Security).
- **FR-012**: The `SessionStore` (in `src/booking_agent/api/store.py`) MUST build the agent + LLM primitives once per session and cache them in memory; it MUST be thread-safe for concurrent sessions.
- **FR-013**: Every incoming request and every tool call triggered by the API MUST be logged with timestamp, method, path, session ID (if applicable), and response status code (Constitution VII).
- **FR-014**: All request/response bodies exchanged by the API MUST be defined as Pydantic schemas in `src/booking_agent/api/schemas.py`; no raw dicts on router boundaries.
- **FR-015**: Dependency injection helpers in `src/booking_agent/api/deps.py` MUST provide `get_session_store`, `get_db`, and `require_admin_token` for use with FastAPI `Depends`.
- **FR-016**: The server MUST refuse to start if `ADMIN_TOKEN` is empty or `SECRET_KEY` is unset (Settings validator).

### Key Entities

- **ChatSession**: logical conversation unit; holds `session_id` (UUID), `agent` instance, `memory`, `pending_approval` state flag, and message transcript list.
- **SessionStore**: in-memory registry mapping `session_id` to `ChatSession`; built once at lifespan start; thread-safe.
- **AgentRequest**: `{"role":"user","content":"<str>","message_id":"<uuid>|null"}` — inbound message to the agent router.
- **AgentResponse**: `{"role":"assistant","content":"<str>","response_type":"clarification|event_cards|quote|seat_map|confirmation|payment_link|ticket","payload":<object>|null,"timestamp":"<iso8601>"}` — structured agent output.
- **QuoteRequest**: `{"event_id":"<uuid>","category":"<str>","quantity":<int>,"member_email":"<str>|null"}`.
- **WebhookPayload**: raw bytes + `X-Moyasar-Signature` header string; passed opaque to F003 handler.
- **AdminTokenDep**: FastAPI dependency that extracts `X-Admin-Token` header and compares to `settings.ADMIN_TOKEN`; raises HTTP 403 on mismatch.

## Success Criteria *(mandatory)*

- **SC-001**: `uvicorn booking_agent.api.app:app` starts without errors given a valid `.env`; GET `/v1/healthz` returns 200 within 500ms.
- **SC-002**: The full agent round-trip (POST session → POST message → GET transcript) completes end-to-end with the real LangChain agent and returns a correctly typed `AgentResponse`.
- **SC-003**: POST `/v1/payments/webhook` with a duplicate payload returns 200 and produces exactly one `paid` booking and one ticket (idempotency proven by test).
- **SC-004**: POST `/v1/payments/webhook` with a tampered signature returns 400 and leaves all booking records unchanged.
- **SC-005**: GET `/v1/events/{id}/seatmap.png?category=Gold` returns `Content-Type: image/png` and a non-zero body for a seeded event.
- **SC-006**: POST `/v1/admin/seed` without `X-Admin-Token` returns 403; with the correct token returns 200; calling it a second time is idempotent (200, no duplicate data).
- **SC-007**: POST `/v1/sessions/{id}/approve` when no approval is pending returns 409.
- **SC-008**: All router modules pass `ruff` linting; `pytest tests/test_api/` runs green with coverage ≥ 80% on the `src/booking_agent/api/` package.
- **SC-009**: The server refuses to start (raises `ValidationError` on settings load) when `ADMIN_TOKEN` is empty.

## Assumptions

- F001 (Foundation — DB & Tools) is merged and available; this feature imports from `booking_agent.tools.*` and `booking_agent.db.*`.
- F002 (Agent Orchestrator) is merged and exposes a callable `BookingAgent` that accepts a session and a user message string; if F002 is not yet merged, the router accepts a stubbed agent conforming to the same interface.
- F003 (Payment & Fulfilment) is merged and exposes `handle_payment_webhook(payload: bytes, signature: str)`.
- The Streamlit frontend communicates with this API over HTTP on localhost; the CORS allowlist includes `http://localhost:8501`.
- Sessions are in-memory only for the MVP; restarting the server clears all sessions (acceptable for demo scope).
- The server runs as a single process (single-writer SQLite assumption from F001 is preserved).
- `ADMIN_TOKEN`, `SECRET_KEY`, `MOYASAR_WEBHOOK_SECRET`, and `CORS_ORIGINS` are supplied via `.env` (gitignored).
- VAT rate is 15% and SAR is the only currency (inherited from F001).
- Hold TTL is 10 minutes (inherited from F001 `HOLD_TTL_MINUTES` setting).
- Authentication for end-users (JWT, OAuth) is out of MVP scope; sessions are identified by `session_id` UUID only.
