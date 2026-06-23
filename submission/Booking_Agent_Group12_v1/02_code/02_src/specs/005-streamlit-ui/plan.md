# Implementation Plan: Streamlit Chat UI

**Branch**: `005-streamlit-ui` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-streamlit-ui/spec.md`

## Summary

Build the chat-first Streamlit front-end for the Booking-Agent. Four new modules
under `src/booking_agent/ui/` cover the page entry point (`app.py`), all inline
card renderers (`components.py`), a typed HTTP client for the F004 API
(`api_client.py`), and session/transcript state management (`state.py`). The UI
renders event cards, the seat-map PNG, quote card, the HITL confirmation card
(Confirm = Constitution-I gate), the Moyasar payment link, and the post-payment
ticket card with QR thumbnail and PDF download — all inside `st.chat_message`
bubbles. A mode banner reflects the `/healthz` status; a live countdown tracks
the 10-minute seat-hold TTL.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Streamlit 1.35+, httpx (async-capable typed client), Pydantic v2, Pillow (for any client-side image prep), python-dotenv

**Storage**: No new DB tables — all state lives in `st.session_state` within the Streamlit session; persisted backend state accessed via F004 API.

**Testing**: pytest + pytest-mock (mock `httpx` calls); Streamlit AppTest for component-level assertions where available.

**Target Platform**: Local dev (Windows/macOS/Linux); launched with `streamlit run src/booking_agent/ui/app.py`; offline-demo mode (`DEMO_OFFLINE=true`) bypasses HTTP.

**Project Type**: Single Python project (`src/booking_agent/`); UI is a sibling sub-package to `agent/`, `tools/`, `api/`.

**Performance Goals**: Initial page load < 2 s; chat round-trip (user message → rendered card) < 3 s on localhost; seat-map PNG display < 500 ms after API response arrives.

**Constraints**: All booking logic stays in the backend (no tool calls or DB access in the UI layer); payment URL never rendered before Confirm click; no React/Next.js; no external CDN assets.

**Scale/Scope**: Single-user demo session; Streamlit single-process model; no multi-user auth.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | The **Confirm** button on the confirmation card is the sole HITL gate in the UI. The payment URL is appended to the transcript only after the user clicks Confirm; the button is disabled at all other times. **Core of this slice.** ✅ |
| II. Atomic, Time-Bounded Holds | The UI displays the 10-minute countdown derived from `hold.expires_at` returned by the backend. On expiry, the UI appends a hold-expiry message and clears hold state; it does not extend or recreate holds — that stays in the backend. ✅ |
| III. Tools Are Python Functions | The UI layer calls no tools directly. All agent/tool logic runs in the F004 backend. In offline-demo mode the agent Python object is imported directly but the tool surface is unchanged. ✅ |
| IV. Exact, Auditable Money | All monetary amounts (base, discount, VAT 15%, total) are displayed as returned by the backend; the UI performs no arithmetic. Quote cards render all four pricing lines. ✅ |
| V. Tamper-Evident Tickets | The UI renders the QR thumbnail and a Download PDF button; it does not generate or sign tokens. QR bytes come from the backend's `GET /v1/bookings/{id}/ticket` endpoint. ✅ |
| VI. Test-First | No money or seat writes happen in the UI; Constitution VI applies to tool-layer tests (covered in F001). UI component tests mock the API client and verify card rendering. ✅ |
| VII. Observable Reasoning | The mode banner surfaces the backend's AI/heuristic/error status to the user. All API calls are logged by the F004 layer (audit_log); the UI itself has no separate audit obligation. ✅ |
| VIII. MVP First | This is the MVP chat surface defined in the constitution's Technology Constraints section ("Streamlit — must render inline images for event cards, seat maps, and ticket cards"). No multi-agent UI scaffolding is introduced. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-streamlit-ui/
├── plan.md              # This file
├── spec.md              # Feature spec
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── config.py                 # (existing) — adds API_BASE_URL, DEMO_OFFLINE settings
├── ui/
│   ├── __init__.py
│   ├── app.py                # Streamlit page: layout, mode banner, chat loop, rerun timer
│   ├── components.py         # Card renderers: event_card, quote_card, seat_map, confirmation_card,
│   │                         #   payment_link, ticket_card, mode_banner, error_card
│   ├── api_client.py         # Typed httpx client for /v1/chat, /v1/bookings/*, /v1/holds/*, /healthz
│   └── state.py              # SessionState dataclass + helpers: init_state, append_message,
│                             #   set_hold, clear_hold, set_booking, get_hold_remaining_seconds

tests/
├── test_ui/
│   ├── test_components.py    # Unit tests: each card renderer called with fixture payload → no error
│   ├── test_api_client.py    # httpx-mock tests: happy path + error paths per endpoint
│   └── test_state.py         # state init, append, hold countdown math, clear_hold
```

**Structure Decision**: Single-project `src/booking_agent/` layout established in F001. The `ui/` sub-package is a new sibling alongside `db/`, `tools/`, `agent/`, and `api/`. Tests live in `tests/test_ui/` mirroring the existing `tests/test_tools/` pattern.

## Phase 0 — Research / Decisions

- **Streamlit chat pattern**: Use `st.chat_message(role)` blocks. Agent messages containing a `CardPayload` are rendered by the matching `components.py` function inside the block. Plain-text messages fall back to `st.markdown`. Transcript stored as `List[ChatMessage]` in `st.session_state["messages"]`.
- **Inline PNG delivery**: The backend returns base64-encoded PNG strings for seat maps and QR thumbnails. `api_client.py` decodes to `bytes`; `components.py` passes bytes directly to `st.image` — no temporary files needed.
- **Countdown rerun**: `st.rerun()` is called every second while a hold is active. A guard in `app.py` skips the rerun when `hold_remaining_seconds <= 0` and instead appends the expiry message. On Streamlit 1.35 + `st.fragment` is available; the timer widget will use a fragment to avoid re-rendering the full transcript on each tick.
- **HITL Confirm gate**: The confirmation card is a Pydantic model returned in the API response. `components.py` renders it with two `st.button` calls ("Confirm" / "Cancel"). Both buttons set flags in `st.session_state` and immediately trigger a `st.rerun()` that the main `app.py` loop catches to fire the appropriate API call.
- **Offline-demo mode**: When `DEMO_OFFLINE=true`, `api_client.py` is replaced at import time by a thin shim that calls `booking_agent.agent.run_turn(message, session_state)` directly. All card payloads must be identical in structure so `components.py` is unaffected.
- **Mode banner**: `/healthz` is called once at session start and stored in `st.session_state["ai_mode"]`. It is re-polled on each page reload. The banner is rendered by `components.mode_banner(ai_mode)` at the top of `app.py`.

## Phase 1 — Design Artifacts

- `state.py` defines the `SessionState` typed dict and helper functions; it is the single source of truth for `messages`, `hold`, `booking_id`, `pending_confirm`, `ai_mode`, `email`, `selected_event_id`, `selected_seats`.
- `api_client.py` defines one Pydantic response model per endpoint; the client raises typed `ApiError` subclasses (`BackendUnreachableError`, `HoldExpiredError`, `SeatUnavailableError`) that `app.py` catches and routes to `components.error_card`.
- `components.py` contains one renderer per `card_type` value; each is a pure function `(payload: CardPayload, state: SessionState) -> None` that calls Streamlit primitives. No business logic in renderers.
- Card type enumeration: `event_card`, `quote_card`, `seat_map`, `confirmation_card`, `payment_link`, `ticket_card`, `error`, `text`.

## Complexity Tracking

No constitution violations — table intentionally empty.
