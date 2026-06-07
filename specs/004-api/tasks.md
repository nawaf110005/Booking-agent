---
description: "Task list for FastAPI Backend — HTTP Surface & Session Management"
---

# Tasks: FastAPI Backend — HTTP Surface & Session Management

**Input**: Design documents from `/specs/004-api/`

**Prerequisites**: plan.md (required), spec.md (required for user stories); F001 (foundation) merged; F002 (agent) merged or stubbed; F003 (payment/fulfilment) merged or stubbed.

**Tests**: Included — API contract and integration tests using `httpx.AsyncClient`.

**Organization**: Grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (chat/transcript), US2 (webhook), US3 (HITL approve/reject), US4 (seatmap), US5 (admin)

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `src/booking_agent/api/` package tree (`__init__.py`, `app.py`, `deps.py`, `schemas.py`, `store.py`, `routers/__init__.py`) — all files empty stubs at this stage
- [ ] T002 [P] Extend `src/booking_agent/config.py` with new Settings fields: `CORS_ORIGINS` (list[str], default `["http://localhost:8501"]`), `ADMIN_TOKEN` (str, non-empty validator), `SERVER_HOST` (str, default `"0.0.0.0"`), `SERVER_PORT` (int, default `8000`)
- [ ] T003 [P] Add API dependencies to `pyproject.toml`: `fastapi>=0.111`, `uvicorn[standard]`, `httpx`, `pytest-asyncio`; add `[project.optional-dependencies] api` group
- [ ] T004 [P] Create `tests/test_api/__init__.py` and extend `tests/conftest.py` with an `async_client` fixture (httpx `AsyncClient` + `ASGITransport`, override `get_db` with in-memory SQLite)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared infrastructure every router depends on — factory, middleware, lifespan, deps, schemas, and store.

**⚠️ CRITICAL**: No router work can begin until this phase is complete.

- [ ] T005 `src/booking_agent/api/schemas.py` — define ALL Pydantic request/response models: `SessionCreateResponse`, `AgentRequest`, `AgentResponse` (with `ResponseType` enum: `clarification|event_cards|quote|seat_map|confirmation|payment_link|ticket`), `TranscriptResponse`, `QuoteRequest`, `BookingStatusResponse`, `AdminActionResponse`, `HealthResponse`, `ErrorResponse`
- [ ] T006 `src/booking_agent/api/store.py` — `ChatSession` dataclass (`session_id`, `agent`, `history`, `pending_approval`, `lock`) and `SessionStore` class (`create_session`, `get_session`, thread-safe with `threading.Lock`); builds `BookingAgent` from F002 on `create_session`
- [ ] T007 `src/booking_agent/api/deps.py` — `get_session_store` (app-state singleton), `get_db` (per-request SQLAlchemy session generator), `require_admin_token` (extracts `X-Admin-Token`, timing-safe compare against `settings.ADMIN_TOKEN`, raises HTTP 403 on mismatch)
- [ ] T008 `src/booking_agent/api/app.py` — `create_app()` factory: add `CORSMiddleware` (allowlist from `settings.CORS_ORIGINS`), add request-logging middleware, register lifespan (init `SessionStore` on startup, dispose on shutdown), include all routers under `/v1` prefix
- [ ] T009 [P] Create empty router stubs (`health.py`, `chat.py`, `events.py`, `seatmap.py`, `quote.py`, `bookings.py`, `payments.py`, `admin.py`) each returning `{"detail":"not implemented"}` — lets the factory import without error while stories are built

**Checkpoint**: `uvicorn booking_agent.api.app:app --reload` starts; all routes return 501 or stub; `async_client` fixture works in tests.

---

## Phase 3: User Story 1 — Chat message drive & transcript restore (Priority: P1) 🎯 MVP

**Goal**: POST a message and receive a structured agent response; GET the full transcript.

**Independent Test**: `pytest tests/test_api/test_chat.py` — session create, message round-trip (stubbed agent), transcript restore, unknown session 404.

- [ ] T010 [P] [US1] Write `tests/test_api/test_chat.py` FIRST — tests for POST `/v1/sessions` (201 + `session_id`), POST `/v1/sessions/{id}/messages` (200 + `AgentResponse` schema), GET `/v1/sessions/{id}/messages` (transcript list), unknown `session_id` → 404; must FAIL before implementation
- [ ] T011 [US1] `routers/chat.py` — POST `/v1/sessions`: call `store.create_session()`, return `SessionCreateResponse(session_id=..., transcript=[])`
- [ ] T012 [US1] `routers/chat.py` — POST `/v1/sessions/{session_id}/messages`: validate `AgentRequest`, acquire session lock (409 if already running), call `session.agent.invoke(message)`, append to `session.history`, return `AgentResponse`
- [ ] T013 [US1] `routers/chat.py` — GET `/v1/sessions/{session_id}/messages`: return `TranscriptResponse(messages=session.history)`; 404 on unknown session
- [ ] T014 [US1] `routers/health.py` — GET `/v1/healthz`: return `HealthResponse` (status, extractor_mode, llm_provider, llm_model, last_error) from `settings` and `store` state
- [ ] T015 [US1] Add `tests/test_api/test_health.py` — GET `/v1/healthz` returns 200 with correct schema
- [ ] T016 [US1] Make `test_chat.py` and `test_health.py` green

**Checkpoint**: Session create → message → transcript restore independently functional and tested.

---

## Phase 4: User Story 2 — Webhook signature verification & idempotency (Priority: P1)

**Goal**: Signature-verified, idempotent payment webhook; bad signatures rejected with 400.

**Independent Test**: `pytest tests/test_api/test_payments.py` — valid sig → 200 + paid booking, duplicate → 200 idempotent, bad sig → 400, no DB mutation on bad sig.

- [ ] T017 [P] [US2] Write `tests/test_api/test_payments.py` FIRST — three scenarios (valid, duplicate, bad-sig); stub `handle_payment_webhook` in conftest if F003 not merged; must FAIL before implementation
- [ ] T018 [US2] `routers/payments.py` — POST `/v1/payments/webhook`: read raw `Request.body()`, extract `X-Moyasar-Signature` header (400 if missing), call `handle_payment_webhook(payload, signature)` from F003 (import guard if F003 absent), return 200; catch `SignatureError` → 400, catch idempotency short-circuit → 200
- [ ] T019 [US2] Make `test_payments.py` green

**Checkpoint**: Webhook idempotency and signature rejection proven by automated tests (SC-003, SC-004).

---

## Phase 5: User Story 3 — HITL approve/reject endpoints (Priority: P1)

**Goal**: Approve or reject a pending confirmation; 409 when no approval is pending.

**Independent Test**: `pytest tests/test_api/test_chat.py::test_approve_reject` — approve in pending state → 200, reject in pending state → 200 + hold released, approve when not pending → 409.

- [ ] T020 [P] [US3] Write `tests/test_api/test_chat.py` approve/reject tests (extend existing file) FIRST — must FAIL before implementation
- [ ] T021 [US3] `store.py` — add `pending_approval: threading.Event | None` to `ChatSession`; add `set_pending_approval()`, `resolve_approval(approved: bool)` methods; `resolve_approval` when no event pending raises `NoPendingApprovalError`
- [ ] T022 [US3] `routers/chat.py` — POST `/v1/sessions/{session_id}/approve`: call `session.resolve_approval(approved=True)`; 409 on `NoPendingApprovalError`; return 200
- [ ] T023 [US3] `routers/chat.py` — POST `/v1/sessions/{session_id}/reject`: call `session.resolve_approval(approved=False)`; 409 on `NoPendingApprovalError`; return 200
- [ ] T024 [US3] Make approve/reject tests green

**Checkpoint**: HITL gate enforced server-side; session state machine tested independently (SC-007).

---

## Phase 6: User Story 4 — Seat-map PNG endpoint (Priority: P2)

**Goal**: Return live seat-map image from `render_seat_map` as `image/png`.

**Independent Test**: `pytest tests/test_api/test_seatmap.py` — 200 + `image/png`, non-zero body; 404 on bad event; 422 on missing category.

- [ ] T025 [P] [US4] Write `tests/test_api/test_seatmap.py` FIRST — three scenarios above; must FAIL before implementation
- [ ] T026 [P] [US4] `routers/events.py` — GET `/v1/events`: call `search_events` with optional `q`, `city`, `date` query params; return list of `EventOut`; GET `/v1/events/{event_id}`: call `get_event_details`; return `EventOut`; 404 on `NotFoundError`
- [ ] T027 [US4] `routers/seatmap.py` — GET `/v1/events/{event_id}/seatmap.png?category=<str>`: require `category` query param (422 if absent), call `render_seat_map(event_id, category)`, return `StreamingResponse(io.BytesIO(png_bytes), media_type="image/png", headers={"Content-Length": str(len(png_bytes))})`; 404 on `NotFoundError`
- [ ] T028 [P] [US4] `routers/quote.py` — POST `/v1/quote`: validate `QuoteRequest`, call `compute_quote`, return `Quote` DTO; 422 on `CapExceededError`, 404 on `NotFoundError`
- [ ] T029 [P] [US4] `routers/bookings.py` — GET `/v1/bookings/{booking_id}`: call `get_booking_status`, return `BookingStatusResponse`; 404 on unknown booking
- [ ] T030 [P] [US4] Add `tests/test_api/test_events.py`, `tests/test_api/test_quote.py`, `tests/test_api/test_bookings.py`
- [ ] T031 [US4] Make `test_seatmap.py`, `test_events.py`, `test_quote.py`, `test_bookings.py` green

**Checkpoint**: Seat-map endpoint returns PNG; events and quote endpoints functional (SC-005).

---

## Phase 7: User Story 5 — Admin token-gated endpoints (Priority: P2)

**Goal**: init-db, seed, sweep accept the correct `X-Admin-Token` and reject all others with 403.

**Independent Test**: `pytest tests/test_api/test_admin.py` — 403 without token, 403 with wrong token, 200 with correct token, idempotent on re-seed, 200 on sweep.

- [ ] T032 [P] [US5] Write `tests/test_api/test_admin.py` FIRST — five scenarios above; must FAIL before implementation
- [ ] T033 [US5] `routers/admin.py` — POST `/v1/admin/init-db` (Depends `require_admin_token`): call DB init, return `AdminActionResponse`; POST `/v1/admin/seed` (Depends `require_admin_token`): call `seed.run_seed()`, idempotent, return `AdminActionResponse`; POST `/v1/admin/sweep` (Depends `require_admin_token`): call `release_expired_holds()`, return count of released holds in `AdminActionResponse`
- [ ] T034 [US5] Make `test_admin.py` green; verify startup fails with empty `ADMIN_TOKEN` (settings validator test)

**Checkpoint**: Admin surface fully token-gated; seed and sweep proven idempotent (SC-006, SC-009).

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T035 [P] Logging middleware in `app.py` — log every request: `timestamp`, `method`, `path`, `session_id` (from header or path param if present), `status_code`, `duration_ms`; use Python `logging` at INFO level; PII in path params is not logged at DEBUG
- [ ] T036 [P] Global exception handler in `app.py` — catch unhandled exceptions, log full traceback at ERROR level, return `ErrorResponse(detail="internal server error")` with status 500 (no stack trace to client)
- [ ] T037 [P] CORS settings validation test — assert startup raises `ValidationError` when `CORS_ORIGINS` contains `"*"`; assert `ADMIN_TOKEN` empty raises `ValidationError`
- [ ] T038 [P] Add `uvicorn` entry-point script to `pyproject.toml` (`booking-agent-api`) and document `uvicorn booking_agent.api.app:app --host 0.0.0.0 --port 8000` in project README section
- [ ] T039 Run full suite `pytest tests/test_api/` + coverage ≥ 80% on `src/booking_agent/api/`; ruff clean on all new modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all routers.
- **US1 Chat (Phase 3)**: Depends on Foundational; no dependency on other user stories.
- **US2 Webhook (Phase 4)**: Depends on Foundational; no dependency on US1 (different router file).
- **US3 HITL (Phase 5)**: Depends on Foundational and US1 `store.py` session model (T021 extends T006).
- **US4 Seatmap/Events (Phase 6)**: Depends on Foundational; no dependency on US1–US3.
- **US5 Admin (Phase 7)**: Depends on Foundational; no dependency on other user stories.
- **Polish (Phase 8)**: Depends on all user stories being implemented.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on other stories.
- **US2 (P1)**: Can start after Phase 2 — `payments.py` router is an independent file.
- **US3 (P1)**: Depends on Phase 2 + T006 (store.py ChatSession) from US1 setup — starts after T006 is done.
- **US4 (P2)**: Can start after Phase 2 — `seatmap.py`, `events.py`, `quote.py`, `bookings.py` are independent files.
- **US5 (P2)**: Can start after Phase 2 — `admin.py` router is an independent file.

### Within Each User Story

- Tests MUST be written and FAIL before router implementation.
- Schemas (`schemas.py`) before routers.
- `deps.py` before any router that uses `Depends`.
- `store.py` before `chat.py` routers.
- Core router implementation before error-handling edge cases.

### Parallel Opportunities

- T002, T003, T004 (Phase 1) run in parallel.
- T005, T006, T007, T008, T009 (Phase 2) have internal ordering: T005 (schemas) and T007 (deps) can run in parallel; T006 (store) can run in parallel with T005/T007; T008 (app factory) after T006/T007; T009 (stubs) after T008.
- US1 (T010–T016), US2 (T017–T019), and US4 (T025–T031) can run in parallel across team members after Phase 2 completes.
- US5 (T032–T034) is independent and can run in parallel with all other user stories after Phase 2.
- T035, T036, T037, T038 (Phase 8) run in parallel.

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (schemas, store, deps, factory, stubs).
3. Complete Phase 3: US1 (chat + transcript).
4. Complete Phase 4: US2 (webhook).
5. **STOP and VALIDATE**: end-to-end POST session → POST message → receive agent response; POST webhook with valid/duplicate/bad-sig.
6. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → API starts, all routes stub.
2. Add US1 → chat and transcript work → Demo the agent via HTTP.
3. Add US2 → payment webhook closes the booking loop → Demo end-to-end.
4. Add US3 → HITL gate enforced server-side → Constitution I satisfied at HTTP layer.
5. Add US4 → seat-map PNG, events, quote, bookings → Full read surface live.
6. Add US5 → admin surface token-gated → Demo bootstrap and sweep operational.
7. Polish phase → logging, error handling, coverage gate.

### Parallel Team Strategy

With multiple developers (after Phase 2 completes):

- Developer A: US1 (chat, transcript, health) — `routers/chat.py`, `store.py`.
- Developer B: US2 (webhook) + US5 (admin) — `routers/payments.py`, `routers/admin.py`.
- Developer C: US3 (HITL) + US4 (seatmap, events, quote, bookings) — remaining routers.

---

## Notes

- [P] tasks = different files, no dependencies on each other within the same phase.
- [Story] label maps each task to a specific user story for traceability.
- Tests MUST be written and confirmed FAILING before the corresponding router is implemented (mirrors Constitution VI spirit for API layer).
- `handle_payment_webhook` import in `routers/payments.py` MUST be guarded: if F003 is not yet merged, use a stub that raises `NotImplementedError` so the test suite remains runnable.
- `BookingAgent` import in `store.py` MUST be guarded similarly for F002.
- Never log PII (buyer email, name) at INFO level — redact to first 3 chars + `***` if needed in debug logs.
- SAR is the only currency; VAT is 15%; hold TTL is 10 minutes — all inherited from F001 settings, never hardcoded in API layer.
- The `pending_approval` mechanism in `ChatSession` uses a `threading.Event` (not `asyncio.Event`) because the agent may call `resolve_approval` from a synchronous tool callback.
