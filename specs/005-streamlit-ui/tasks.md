---
description: "Task list for Streamlit Chat UI"
---

# Tasks: Streamlit Chat UI

**Input**: Design documents from `/specs/005-streamlit-ui/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Included — component and API-client tests are part of this slice.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [US?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (full booking flow + HITL gate), US2 (seat-map inline), US3 (hold countdown), US4 (ticket card + PDF download)

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Add `streamlit`, `httpx`, `python-dotenv` to `pyproject.toml` optional extras group `ui`; verify `pip install -e ".[ui]"` installs cleanly
- [ ] T002 [P] Extend `src/booking_agent/config.py` with `API_BASE_URL` (default `http://localhost:8000`) and `DEMO_OFFLINE` (bool, default False) settings
- [ ] T003 [P] Create `src/booking_agent/ui/__init__.py` (empty package marker)
- [ ] T004 [P] Create `tests/test_ui/__init__.py` (empty package marker)

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until state and API client exist.

- [ ] T005 `src/booking_agent/ui/state.py` — `SessionState` typed dict; helpers: `init_state(session_state)`, `append_message(session_state, role, content)`, `set_hold(session_state, hold_token, expires_at)`, `clear_hold(session_state)`, `set_booking(session_state, booking_id)`, `get_hold_remaining_seconds(session_state) -> float`
- [ ] T006 [P] `src/booking_agent/ui/api_client.py` — Pydantic response models for `/v1/chat` (ChatResponse with `messages: List[CardPayload]`), `/v1/bookings/{id}/status` (BookingStatus), `/v1/bookings/{id}/ticket` (TicketCard), `/v1/bookings/{id}/ticket/pdf` (bytes), `DELETE /v1/holds/{hold_id}` (HoldReleaseResponse), `GET /healthz` (HealthResponse); typed `ApiClient` class using `httpx`; `ApiError` hierarchy (`BackendUnreachableError`, `HoldExpiredError`, `SeatUnavailableError`); offline-demo shim toggled by `DEMO_OFFLINE` config
- [ ] T007 [P] `src/booking_agent/ui/components.py` — stub one function per card type returning immediately (to be filled in per user story): `event_card`, `quote_card`, `seat_map`, `confirmation_card`, `payment_link_card`, `ticket_card`, `mode_banner`, `error_card`, `text_message`; plus `render_message(msg, state)` dispatcher
- [ ] T008 [P] `tests/test_ui/test_state.py` — unit tests: `init_state` populates required keys; `append_message` grows `messages`; `set_hold` / `clear_hold` round-trip; `get_hold_remaining_seconds` returns correct value for a future and past `expires_at`
- [ ] T009 [P] `tests/test_ui/test_api_client.py` — httpx-mock tests: `POST /v1/chat` happy path returns `ChatResponse`; `GET /healthz` returns `HealthResponse`; `BackendUnreachableError` raised on connection error; `HoldExpiredError` raised on 409; offline-demo shim returns fixture `ChatResponse` without HTTP

**Checkpoint**: State management and typed API client exist and are tested — user story work can begin in parallel.

## Phase 3: User Story 1 — Complete booking flow with HITL Confirm gate (Priority: P1) 🎯 MVP

**Goal**: Full chat loop from user message to payment URL, with Confirm button as the sole HITL gate.

- [ ] T010 [P] [US1] Write `tests/test_ui/test_components.py` stubs for US1 cards: `event_card` renders poster + title + date + venue + Select button; `quote_card` renders all four price lines; `confirmation_card` renders Confirm + Cancel buttons; `payment_link_card` renders clickable URL — all tested with fixture payloads using `streamlit.testing.v1.AppTest` or mock assertions
- [ ] T011 [US1] `components.event_card(payload, state)` — renders `st.image(poster_url)`, `st.markdown(title/date/venue)`, `st.button("Select", key=…)` that sets `state["selected_event_id"]` and calls `st.rerun()`; defined in `src/booking_agent/ui/components.py`
- [ ] T012 [US1] `components.quote_card(payload, state)` — renders four-line itemised table (base SAR, discount SAR/%, VAT 15% SAR, total SAR) using `st.table` or `st.markdown`; defined in `src/booking_agent/ui/components.py`
- [ ] T013 [US1] `components.confirmation_card(payload, state)` — renders event/date/venue/seats summary, itemised pricing, hold expiry time, `st.button("Confirm")` that sets `state["pending_confirm"] = True` and `st.rerun()`, `st.button("Cancel")` that calls `api_client.release_hold(hold_id)` + appends cancellation message + `clear_hold(state)` + `st.rerun()`; **Confirm button is disabled if `not state["hold"]`**; defined in `src/booking_agent/ui/components.py`
- [ ] T014 [US1] `components.payment_link_card(payload, state)` — renders Moyasar URL as `st.link_button("Pay now", url)` and a plain `st.markdown` fallback; payment URL MUST NOT appear in the transcript until this function is called (enforced by dispatcher); defined in `src/booking_agent/ui/components.py`
- [ ] T015 [US1] `src/booking_agent/ui/app.py` — Streamlit page entry point: `st.set_page_config(layout="wide")`; call `init_state(st.session_state)` on first run; poll `/healthz` and render `mode_banner`; render transcript via `render_message` loop; `st.chat_input("Type your message…")` captured and posted to `api_client.chat(message, session_id)`; response messages appended to transcript; `pending_confirm` flag handled — fires `api_client.confirm_booking(booking_id)` and appends payment link card
- [ ] T016 [US1] Make all US1 component tests green

**Checkpoint**: Full booking funnel (event → quote → seat map → confirmation → payment URL) renders in chat; HITL gate enforced.

## Phase 4: User Story 2 — Seat-map inline rendering (Priority: P1)

**Goal**: Seat-map PNG displayed inline inside the chat bubble; seat selection captured and sent.

- [ ] T017 [P] [US2] Add `seat_map` test to `tests/test_ui/test_components.py`: fixture base64 PNG string → `seat_map` renderer decodes to bytes → `st.image` called with bytes; assert no file I/O
- [ ] T018 [US2] `components.seat_map(payload, state)` — decodes `payload.png_b64` from base64 to `bytes`; calls `st.image(bytes, caption=payload.section_label, use_column_width=True)`; renders helper text "Type your seat IDs (e.g. G12, G13)"; defined in `src/booking_agent/ui/components.py`
- [ ] T019 [US2] Extend `app.py` chat input handler: when current state step is `seat_selection`, parse comma-separated seat IDs from user input → store in `state["selected_seats"]` → post to `/v1/chat`; on `SeatUnavailableError` from API, append error card + re-fetch and re-display seat map
- [ ] T020 [US2] Make US2 seat-map tests green

**Checkpoint**: Seat-map PNG renders inline; seat IDs captured from chat input; unavailable-seat error re-displays map.

## Phase 5: User Story 3 — Live hold countdown (Priority: P2)

**Goal**: MM:SS countdown in sidebar updates every second while hold is active; clears on expiry.

- [ ] T021 [P] [US3] Add state tests for countdown: `get_hold_remaining_seconds` returns positive float when `expires_at` is 5 minutes in future; returns 0 when past; `clear_hold` sets `state["hold"]` to None
- [ ] T022 [US3] `app.py` countdown logic: after rendering the transcript, if `state["hold"]` is set, call `get_hold_remaining_seconds`; if > 0, use `@st.fragment` (or `st.sidebar`) to render `st.metric("Hold expires in", f"{mm:02d}:{ss:02d}")` + `time.sleep(1)` + `st.rerun()`; if ≤ 0, call `clear_hold(state)` + append hold-expiry `text_message` + `st.rerun()` (no HTTP call — backend sweeper handles the actual release)
- [ ] T023 [US3] `components.mode_banner(ai_mode)` — `"ai"` → green `st.success`; `"heuristic"` → amber `st.warning`; `"error"` → red `st.error` with disabled chat input flag set in state; defined in `src/booking_agent/ui/components.py`

**Checkpoint**: Live countdown ticks down and auto-clears; mode banner reflects backend health.

## Phase 6: User Story 4 — Ticket card and PDF download (Priority: P2)

**Goal**: Post-payment ticket card with QR thumbnail and Download PDF button renders inline.

- [ ] T024 [P] [US4] Add ticket-card test to `tests/test_ui/test_components.py`: fixture `TicketCard` payload → `ticket_card` renders event/date/venue/seats text + `st.image` for QR bytes + `st.download_button` with PDF bytes
- [ ] T025 [US4] `components.ticket_card(payload, state)` — renders `st.markdown` block with event title, date, venue, seat list; decodes `payload.qr_png_b64` → `st.image(bytes, caption="Scan at the gate", width=180)`; calls `st.download_button("Download PDF", data=payload.pdf_bytes, file_name=f"ticket_{payload.booking_id}.pdf", mime="application/pdf")`; renders `st.caption(f"Also sent to {payload.email}")`; defined in `src/booking_agent/ui/components.py`
- [ ] T026 [US4] Extend `app.py` post-payment polling: after payment URL is shown, `app.py` calls `api_client.get_booking_status(booking_id)` on each rerun until status is `paid` (max 30 attempts at 2-second intervals); on `paid`, calls `api_client.get_ticket(booking_id)` and appends ticket card to transcript
- [ ] T027 [US4] `api_client.get_ticket(booking_id)` fetches `GET /v1/bookings/{id}/ticket` (metadata + QR PNG base64) and `GET /v1/bookings/{id}/ticket/pdf` (bytes); assembles and returns a `TicketCard` Pydantic model; defined in `src/booking_agent/ui/api_client.py`
- [ ] T028 [US4] Make US4 ticket-card tests green

**Checkpoint**: Ticket card renders inline after payment; PDF download works; QR thumbnail visible.

## Phase 7: Polish & Cross-Cutting

- [ ] T029 [P] `components.error_card(payload, state)` — renders `st.error(payload.message)` with optional `st.button("Try again")` that clears the error from state and reruns; defined in `src/booking_agent/ui/components.py`
- [ ] T030 [P] Chat-input disable during in-flight calls: `app.py` sets `state["loading"] = True` before each API call and `False` after; `st.chat_input` is rendered with `disabled=state["loading"]`; a `st.spinner("Thinking…")` is shown during load
- [ ] T031 [P] Duplicate-Confirm guard: after Confirm button click, the button is immediately replaced with `st.spinner("Confirming…")` by setting `state["pending_confirm"] = True` before rerun; the dispatcher skips re-rendering the Confirm button while `pending_confirm` is True
- [ ] T032 [P] Offline-demo smoke test: `scripts/smoke_ui_demo.py` launches Streamlit in headless mode (via `AppTest`) and drives the full US1 flow without a backend; asserts payment URL appears after Confirm and not before
- [ ] T033 Run full test suite (`pytest tests/test_ui/`); fix any failures; ensure ruff passes on `src/booking_agent/ui/`

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all user stories.
- After Phase 2: **US1** (Phase 3) and **US2** (Phase 4) can proceed in parallel (different component functions, different test files).
- **US3** (Phase 5) and **US4** (Phase 6) can begin after Phase 2 is complete and proceed in parallel with US1/US2.
- **Polish (Phase 7)** after all user stories.

## Implementation Strategy

MVP-first: complete Phase 1 + Phase 2 (state and API client), then Phase 3 (US1 — full booking flow with HITL Confirm gate). This alone satisfies the primary evaluation criterion. US2 (seat-map inline) is also P1 and can be developed in parallel once Phase 2 is done. US3 and US4 complete the experience. Polish phase hardens edge cases and adds the offline-demo smoke test.

## Notes

- All checkboxes are UNCHECKED — no tasks are pre-completed in this slice.
- The Confirm button is the ONLY mechanism that triggers the payment URL; any deviation is a Constitution-I violation.
- `components.py` renderers are pure functions that call Streamlit primitives only; no HTTP, no DB, no tool calls.
- The offline-demo shim in `api_client.py` MUST return identically structured `CardPayload` objects as the real HTTP path; `components.py` must be unmodified between modes.
- VAT is always 15%; all pricing displayed is sourced from the API response, never computed in the UI layer.
- Hold TTL is 10 minutes; `expires_at` drives the countdown, not a local timer started at hold creation time.
- Seat-map PNG and QR thumbnail are delivered as base64 strings in JSON responses; no binary multipart in the MVP.
