# Feature Specification: Streamlit Chat UI

**Feature Branch**: `005-streamlit-ui`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "A chat-first Streamlit surface that renders the booking conversation with inline rich elements: event cards (poster image + title + date + venue + Select action), a quote card (itemised base / member discount / VAT 15% / total), the seat-map PNG shown inline (available green / sold grey / held yellow), a confirmation card (full booking summary with Confirm and Cancel buttons — the Confirm button is the Constitution-I HITL gate in the UI), the Moyasar payment link, and a ticket card (event + seats + QR thumbnail + Download PDF). A mode banner shows AI mode vs heuristic-fallback vs error (from /healthz). Talks to the F004 FastAPI backend and can call the agent directly for an offline demo. Transcript persists within the session and a live 10-minute hold countdown is shown while seats are held."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Complete a booking visually in chat, including the HITL Confirm gate (Priority: P1)

As a buyer using the Streamlit UI, I can type a booking request in the chat input, receive inline event cards, pick a category, view the seat-map image, select seats, see the quote card, and then click the **Confirm** button on the confirmation card — which acts as the Constitution-I HITL gate before any payment URL is ever shown.

**Why this priority.** This is the full booking funnel in one user story. It directly satisfies the evaluation criterion "one conversation, under 2 minutes to ticket" and is the primary demonstration of the HITL Confirm gate (a non-negotiable Constitution-I requirement). Without this story, the feature has no value.

**Independent test.** Launch the Streamlit app against a running F004 backend (or the offline-demo mode). Type a booking request, walk through the cards step by step, click Confirm on the confirmation card, and verify a payment URL appears. The test passes when the payment link is never visible before the Confirm click.

**Acceptance scenarios.**

1. **Given** the Streamlit app is running and the F004 backend is healthy, **When** the user types "I want a Coldplay ticket, Gold, nawaf@example.com, 4 seats", **Then** the agent response renders event cards inline (poster image, title, date, venue, Select button), the user can click Select, and subsequent responses render the quote card and seat-map PNG in the same chat thread.
2. **Given** the confirmation card is displayed (event, seats, base price, discount, VAT 15%, total, hold expiry), **When** the user clicks **Confirm**, **Then** the Moyasar payment URL is posted into the chat and no payment URL was visible before that click.
3. **Given** the confirmation card is displayed, **When** the user clicks **Cancel**, **Then** the hold is released (via the API), a cancellation message is appended to the transcript, and the payment URL is never shown.

---

### User Story 2 — View the seat-map inline and interact to select seats (Priority: P1)

As a buyer, after choosing a category I can see the Pillow-rendered seat-map PNG rendered directly inside the chat, with available seats in green, sold seats in grey, and currently held seats in yellow — and I can type my chosen seat IDs in the chat input to proceed.

**Why this priority.** Inline seat-map rendering is an explicit evaluation criterion ("inline event cards, seat map, and ticket card render in chat") and a key differentiator over web forms. Without it the UI is incomplete.

**Independent test.** Drive the UI to the seat-selection step (or mock the API response to return a `seat_map` PNG payload). Assert the PNG is rendered with `st.image` inside the chat message area, not as a side panel.

**Acceptance scenarios.**

1. **Given** the user has selected a category and the API returns a seat-map PNG, **When** the seat-map response is appended to the transcript, **Then** the PNG is displayed inline in the chat bubble using `st.image`, with a caption identifying the section.
2. **Given** the seat-map is shown, **When** the user types "G12, G13, G14, G15" and submits, **Then** `state.py` records the selected seat IDs and the UI posts the seat-selection message to the backend, which responds with the quote card.
3. **Given** the user selects seats that are no longer available (race condition), **When** the API returns a `SeatUnavailableError`, **Then** the chat renders an error message and re-displays the seat map so the user can choose different seats.

---

### User Story 3 — Live 10-minute hold countdown visible while seats are held (Priority: P2)

As a buyer with seats on hold, I can see a countdown timer ticking down from 10:00 in the Streamlit sidebar (or as a pinned banner above the chat input), so I know exactly how much time I have before the hold expires and seats are released.

**Why this priority.** A visible expiry timer is an explicit evaluation criterion ("visible 10-minute timer") and a trust-building element — it removes uncertainty and drives urgency to complete the payment. Lower priority than the full booking flow but required for MVP.

**Independent test.** Place a hold via the API. Observe the Streamlit session for 60 seconds with `st.rerun()` driving updates. Assert the displayed time decrements correctly and the timer widget disappears (or shows "Hold expired") once `expires_at` is passed.

**Acceptance scenarios.**

1. **Given** a hold is active with `expires_at` in session state, **When** the chat is displayed, **Then** a countdown MM:SS is shown in the sidebar (or sticky banner), updating every second via `st.rerun()`.
2. **Given** the countdown reaches 00:00, **When** the timer expires, **Then** the UI appends a hold-expiry message to the transcript ("Your hold has expired — seats were released. Would you like to start again?") and the countdown widget is removed.
3. **Given** no hold is active, **When** the chat is displayed, **Then** no countdown widget is rendered.

---

### User Story 4 — Download the ticket PDF and see the QR thumbnail after payment (Priority: P2)

As a buyer who has completed payment, I can see a ticket card rendered inline in the chat — showing event title, date, venue, seat IDs, a QR thumbnail image, and a **Download PDF** button — and I can click the button to download the signed ticket PDF to my device.

**Why this priority.** Post-payment ticket delivery in-chat completes the evaluation criterion ("inline … ticket card render in chat") and closes the booking loop. Depends on payment being processed, so it is lower priority than the booking funnel itself.

**Independent test.** Mock the `GET /v1/bookings/{id}/ticket` API response to return ticket metadata (event, seats, QR PNG bytes, pdf_url). Assert the ticket card is rendered inside the chat bubble and the Download PDF button triggers `st.download_button` with the correct PDF bytes.

**Acceptance scenarios.**

1. **Given** the payment webhook has been processed and the booking status is `paid`, **When** the UI polls `GET /v1/bookings/{id}/status` and receives `paid`, **Then** a ticket card is appended to the transcript showing event title, date, venue, seat list, and a QR thumbnail via `st.image`.
2. **Given** the ticket card is shown, **When** the user clicks **Download PDF**, **Then** `st.download_button` streams the PDF bytes and the file downloads with the filename `ticket_{booking_id}.pdf`.
3. **Given** the ticket email was sent, **When** the ticket card is displayed, **Then** a line "Also sent to {email}" appears beneath the card.

---

### Edge Cases

- **Hold expires mid-flow** (between confirmation card display and Confirm click): when the user clicks Confirm after `expires_at` has passed, the API returns a `HoldExpiredError`; the UI appends a friendly expiry message and clears the confirmation card without ever showing a payment URL.
- **LLM down / no API key** (F004 returns `ai_mode: false` from `/healthz`): the mode banner renders in amber with "Heuristic fallback mode — AI reasoning unavailable"; all UI interactions continue using the heuristic path.
- **F004 backend unreachable** (`/healthz` fails entirely): the mode banner renders in red with "Backend error — please reload"; the chat input is disabled and a retry button is shown.
- **Duplicate Confirm clicks** (network lag): after the first Confirm click, the Confirm button is disabled and a spinner is shown until the API responds, preventing double-submission.
- **Bilingual input** (Arabic/English code-switching): the chat input accepts any Unicode; all card labels are rendered from API response strings that may be in Arabic or English; the UI does not force a language.
- **Very long transcript**: the chat container scrolls to the latest message after each `st.rerun()` via `st.markdown` with an anchor hack; older messages remain accessible by scrolling up.
- **Large seat-map PNG** (> 1 MB): displayed via `st.image` with `use_column_width=True`; no resizing or compression in the UI layer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST render a multi-turn chat transcript using `st.chat_message` (or equivalent), with user messages on the right and agent responses on the left, persisting all messages within the Streamlit session via `st.session_state`.
- **FR-002**: The UI MUST render event cards inline inside agent chat bubbles — each card showing a poster image (`st.image`), event title, date, venue name, and a **Select** button that posts the selection to the backend.
- **FR-003**: The UI MUST render a quote card inline showing itemised: base price (SAR), member discount amount and percentage, VAT at 15% (SAR), and grand total (SAR).
- **FR-004**: The UI MUST render the seat-map PNG inline (via `st.image`) inside the agent chat bubble, with no additional navigation required.
- **FR-005**: The UI MUST render a confirmation card with: event, date, venue, selected seats, itemised pricing (base / discount / VAT / total), hold expiry time, a **Confirm** button, and a **Cancel** button. The **Confirm** button is the sole HITL gate and MUST NOT be rendered until the backend has returned a hold token.
- **FR-006**: The UI MUST NOT display a payment URL until the user clicks **Confirm** on the confirmation card; after Confirm, the payment URL is appended to the transcript as a clickable link.
- **FR-007**: The UI MUST show a live countdown (MM:SS, updating every second) while a seat hold is active, derived from `hold.expires_at` stored in session state. The countdown MUST disappear when the hold expires or is cancelled.
- **FR-008**: The UI MUST render a ticket card inline after payment is confirmed, showing event title, date, venue, seat list, QR thumbnail (`st.image`), and a **Download PDF** button (`st.download_button`).
- **FR-009**: The UI MUST display a mode banner at the top of the page indicating AI mode (green), heuristic-fallback mode (amber), or backend error (red), based on the `/healthz` response polled at session start and on reconnect.
- **FR-010**: The UI MUST communicate with the F004 FastAPI backend via `api_client.py` (typed HTTP calls to `/v1/*`); it MUST also support an offline-demo mode that calls the agent Python object directly (no HTTP), controlled by an environment variable `DEMO_OFFLINE=true`.
- **FR-011**: The UI MUST disable the chat input and show a spinner while an API call is in-flight, preventing concurrent submissions.
- **FR-012**: After the hold expires (timer reaches zero), the UI MUST append a hold-expiry message to the transcript and clear all hold-related state (confirmation card, countdown) before allowing the user to start a new flow.

### Key Entities *(include if feature involves data)*

- **SessionState.** Streamlit session-state bag managed by `state.py`: `messages` (transcript list), `hold` (hold token + `expires_at`), `booking_id`, `pending_confirm` (bool), `ai_mode` (str: `"ai"` / `"heuristic"` / `"error"`), `email`, `selected_event_id`, `selected_seats`.
- **ChatMessage.** A typed dict in the transcript list: `role` (`"user"` / `"assistant"`), `content` (plain text or a typed card payload).
- **CardPayload.** Union type discriminated by `card_type`: `"event_card"`, `"quote_card"`, `"seat_map"`, `"confirmation_card"`, `"payment_link"`, `"ticket_card"`, `"error"`.
- **HoldCountdown.** Derived from `state.hold.expires_at`; rendered in the sidebar; drives `st.rerun()` at 1-second intervals while active.
- **ApiClient.** Wraps `httpx` calls to `POST /v1/chat`, `GET /v1/bookings/{id}/status`, `GET /v1/bookings/{id}/ticket`, `DELETE /v1/holds/{hold_id}`, `GET /healthz`. Returns typed Pydantic response models.

## Success Criteria *(mandatory)*

- **SC-001**: A tester can start the Streamlit app with `streamlit run src/booking_agent/ui/app.py` and complete a full booking flow (event selection → seat map → seat selection → quote → confirmation → payment link) in under 2 minutes from a standing start, with no page reloads.
- **SC-002**: Inline rendering: event card (image + title + date + venue + Select), seat-map PNG, quote card (all four pricing lines), confirmation card (Confirm + Cancel buttons), and ticket card (QR thumbnail + Download PDF) all appear inside `st.chat_message` bubbles — not in sidebars or separate pages.
- **SC-003**: The **Confirm** button is the only mechanism that produces a payment URL; clicking Cancel or letting the hold expire produces no payment URL.
- **SC-004**: The live hold countdown is visible and counts down in real time (second-by-second) for the full 10-minute TTL; it clears automatically on expiry.
- **SC-005**: The mode banner correctly reflects the `/healthz` response: green in normal AI mode, amber when `ai_mode` is false, red when the backend is unreachable.
- **SC-006**: The app runs in offline-demo mode (`DEMO_OFFLINE=true`) without a running F004 backend, calling the agent Python object directly, with all card types still rendering correctly.
- **SC-007**: The chat input is disabled and a spinner is shown during any in-flight API call; no duplicate submissions are possible.

## Assumptions

- The F004 FastAPI backend (feature branch `004-fastapi-backend`) is the primary API target; the `/v1/chat` endpoint accepts a `{message, session_id}` payload and returns a structured response containing one or more `CardPayload` objects.
- The backend's `/healthz` endpoint returns `{"status": "ok", "ai_mode": true|false}` and is reachable at the URL set in the `API_BASE_URL` environment variable (default `http://localhost:8000`).
- Seat-map images are returned as base64-encoded PNG strings in the API response; `api_client.py` decodes them to bytes before passing to `components.py`.
- Ticket PDF bytes are fetched via `GET /v1/bookings/{id}/ticket/pdf`; the response is `application/pdf`.
- VAT is 15%; all monetary amounts in API responses are in SAR as strings formatted to 2 decimal places.
- Hold TTL is 10 minutes; `expires_at` is an ISO-8601 UTC timestamp returned by the API.
- The UI does not compute pricing or perform seat validation — it delegates entirely to the backend.
- Streamlit 1.35+ is assumed; `st.chat_message`, `st.chat_input`, and `st.download_button` are available.
- Bilingual rendering (Arabic / English) is handled by rendering text strings returned by the API verbatim; no translation is done in the UI layer.
- Backend logic (agent, tools, database) is out of scope for this feature; the UI only calls F004/F002 endpoints.
