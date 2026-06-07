# Feature Specification: Agent Core — Conversational Booking Loop

**Feature Branch**: `002-agent-core`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "The single LangChain-based booking agent that orchestrates F001 tools end to end. Covers intent classification (book_ticket / ask_policy / discover / approve / reject / smalltalk); bilingual Arabic+English NLU; structured extraction of booking parameters into a typed Pydantic object with explicit missing_fields; a deterministic conversation state machine GREETING → EVENT_SELECTION → MEMBER_IDENTIFIED → QUOTED → SEAT_SELECTION → HELD → AWAITING_CONFIRMATION → PAYMENT_PENDING → CONFIRMED; HITL confirmation gate that shows a full booking summary before issuing any payment URL; heuristic regex fallback when no LLM API key is configured."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Book a ticket end-to-end via chat with the HITL confirmation gate (Priority: P1)

As a buyer, I can describe an event in natural language (in Arabic, English, or mixed), provide my email, select a category and seats, receive a full itemised summary, give explicit approval, and be handed a payment URL — all within a single chat conversation — without the agent ever generating a payment link before I say yes.

**Why this priority.** This is the primary end-to-end booking flow and the core value proposition of the entire product. It exercises every state in the conversation machine, all F001 tools in sequence, and the mandatory HITL gate (Constitution Principle I, graded evaluation criterion: "NEVER issues a payment URL without explicit confirmation"). Nothing else in the feature delivers value without this story.

**Independent test.** Drive the agent through a scripted dialogue (simulate tool responses via mocks): greet → search → pick event → provide email → pick category → provide seat IDs → receive quote card → approve → receive payment link. Assert (a) the state machine advances through each step in order, (b) no payment URL appears until the approve turn, and (c) the confirmation card itemises event, date, venue, seats, base price, member discount, VAT at 15%, total, and hold expiry.

**Acceptance Scenarios:**

1. **Given** a fresh session and the user says "I want 4 Gold tickets to the Coldplay show in Riyadh, nawaf@example.com", **When** the agent processes the message, **Then** it classifies intent as `book_ticket`, transitions to `EVENT_SELECTION`, calls `search_events("Coldplay", city="Riyadh")`, and returns an event-cards response (not a payment link).
2. **Given** state is `QUOTED` and the agent has just shown the confirmation card with base=2720 SAR, VAT=408 SAR, total=3128 SAR, and hold expiry, **When** the user sends "yes" (or "نعم"), **Then** the agent transitions to `PAYMENT_PENDING`, calls `create_payment_session`, and returns a payment-link response — and the `pending_approval` flag is cleared.
3. **Given** state is `AWAITING_CONFIRMATION` and the user sends any message other than an explicit approval, **When** the agent processes it, **Then** it remains in `AWAITING_CONFIRMATION`, re-shows the confirmation card, and does NOT call `create_payment_session`.
4. **Given** state is `HELD` and the hold TTL has expired before the user approves, **When** the agent receives any user message, **Then** it transitions to an `EXPIRED` branch, informs the user the hold has expired, and offers to restart seat selection.

---

### User Story 2 — Clarify missing fields instead of guessing (Priority: P1)

As a buyer who sends an incomplete request (e.g., no email, no quantity, no category, or no seat IDs), I receive a targeted clarification question for each missing field rather than the agent making an assumption or failing silently.

**Why this priority.** The bootcamp evaluation explicitly grades "asks for missing info (email, quantity, category, seats) instead of guessing." Incomplete inputs are the norm in real conversational commerce, and a silent guess would corrupt the booking or apply the wrong discount. This story must be solid before any downstream feature builds on intent extraction.

**Independent test.** Send the message "I want a ticket to the Coldplay show." (no email, no quantity, no category, no seats). Assert the extracted `BookingParams` object has `missing_fields = ["email", "quantity", "category"]`; assert the agent response type is `clarification`; assert the response text asks for the first missing field in the user's detected language. Repeat for each individually missing field in isolation.

**Acceptance Scenarios:**

1. **Given** a user message contains an event query but no email, **When** the extractor runs, **Then** `BookingParams.missing_fields` includes `"email"` and the agent returns a `clarification` response asking for the buyer's email — it does not call `lookup_member_by_email`.
2. **Given** a user message provides email and event but no quantity, **When** the extractor runs, **Then** `missing_fields` includes `"quantity"` and the agent asks "How many tickets?" before calling `compute_quote`.
3. **Given** state is `SEAT_SELECTION` and the user supplies fewer seat IDs than the requested quantity, **When** the agent processes the message, **Then** it asks the user to provide the remaining seat IDs and does not call `place_seat_hold`.
4. **Given** all required fields are present in a single message, **When** the extractor runs, **Then** `missing_fields` is empty and the agent proceeds directly to the next state without asking any clarifying question.

---

### User Story 3 — Refuse politely when quantity exceeds the tier cap (Priority: P2)

As a buyer whose requested quantity exceeds their membership tier's ticket cap, I receive a polite, clear refusal that states my cap, my tier, and the maximum I can book in a single transaction — and the agent offers to proceed with the maximum allowed quantity.

**Why this priority.** Cap enforcement is an explicit evaluation criterion ("refuses politely when quantity exceeds the tier cap") and a Constitution Principle IV requirement (discount/cap derived from the `members` table, never assumed). Enforcement at the agent layer prevents a `CapExceededError` from propagating unhandled to the user.

**Independent test.** Set member tier to Bronze (cap 4); send "I want 6 tickets to the Al-Hilal match". Assert: `compute_quote` is not called; agent response type is `clarification`; response text mentions the Bronze tier cap of 4; agent offers to book 4 instead.

**Acceptance Scenarios:**

1. **Given** a Platinum member (cap 8) requests 9 tickets, **When** the agent resolves the cap via `get_ticket_cap`, **Then** it returns a `clarification` response naming the cap (8) and offering to book 8 instead — no quote is generated.
2. **Given** a non-member (cap 4) requests 5 tickets, **When** the agent resolves the cap, **Then** the response explains cap enforcement and offers to book 4 — and the state does NOT advance past `MEMBER_IDENTIFIED`.
3. **Given** the user accepts the agent's offer to proceed at the cap, **When** the user replies "yes, book 4", **Then** the agent updates quantity to 4, transitions to `QUOTED`, and calls `compute_quote` with qty=4.

---

### User Story 4 — Graceful heuristic fallback when the LLM is unavailable (Priority: P2)

As a developer or demo operator running the system without an LLM API key, the agent still handles the core booking flow using a regex-based heuristic extractor and deterministic response templates, and it clearly signals to the user that it is operating in fallback mode.

**Why this priority.** The Constitution (Technology Constraints) mandates the system "MUST degrade gracefully (heuristic fallback) when no key is configured." A demo that crashes without a key is unusable for offline evaluation. This story ensures the entire booking loop remains functional — with reduced NLU quality — in an offline or key-less environment.

**Independent test.** Unset all LLM API key env vars; instantiate the agent; send "Book Coldplay Riyadh 4 Gold nawaf@example.com". Assert: (a) `llm.py` falls back to the heuristic extractor (no HTTP calls); (b) `BookingParams` is populated from regex patterns; (c) the agent advances through the state machine; (d) a `clarification` or `event-cards` response is returned without raising an exception.

**Acceptance Scenarios:**

1. **Given** no LLM API key is set, **When** the agent module is imported and the agent is instantiated, **Then** `llm.py` logs a warning and activates the heuristic extractor — no exception is raised.
2. **Given** fallback mode is active and the user sends "Book Coldplay Riyadh 4 Gold nawaf@example.com", **When** the heuristic extractor runs, **Then** it correctly parses event_query="Coldplay", city="Riyadh", quantity=4, category="Gold", email="nawaf@example.com" from the message.
3. **Given** fallback mode is active and the user sends a message the heuristic cannot parse, **When** the extractor runs, **Then** it returns a `BookingParams` with all fields set to `None` and `missing_fields` populated, and the agent issues a `clarification` response requesting each field — it does not crash.

---

### Edge Cases

- State machine receives an intent that is invalid for the current state (e.g., `approve` when state is `GREETING`): agent logs the event, returns a `clarification` response, and does not transition.
- User sends the Arabic approval word "نعم" or "تمام": intent classifier maps these to the `approve` intent identically to "yes" or "confirm".
- User sends a `reject` intent at `AWAITING_CONFIRMATION`: agent cancels the hold via `release_seat_hold`, transitions back to `EVENT_SELECTION`, and offers to start over.
- Hold expires mid-conversation (between `HELD` and `AWAITING_CONFIRMATION`): on next user turn the agent detects `expires_at < now`, transitions to `EXPIRED`, and prompts the user to re-select seats.
- Multiple events match the user's query: agent transitions to `EVENT_SELECTION` and returns an `event-cards` response with up to 5 results; does not auto-select.
- User requests zero or negative quantity: `BookingParams` validator raises a `ValidationError`; agent returns a `clarification` response asking for a valid quantity.
- Session already has an active hold when the user starts a new booking request: agent warns the user that an existing hold will be released before proceeding.
- Arabic-only message with no Latin characters: language detector flags `ar`; all agent responses are returned in Arabic.
- LLM returns malformed JSON (structured extraction): `extract.py` falls back to the heuristic extractor for that turn and logs a warning; the conversation continues.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent MUST implement a deterministic conversation state machine with states: `GREETING`, `EVENT_SELECTION`, `MEMBER_IDENTIFIED`, `QUOTED`, `SEAT_SELECTION`, `HELD`, `AWAITING_CONFIRMATION`, `PAYMENT_PENDING`, `CONFIRMED`, `EXPIRED`, `ERROR`; invalid transitions MUST be rejected and logged.
- **FR-002**: The agent MUST classify user intent into one of: `book_ticket`, `ask_policy`, `discover`, `approve`, `reject`, `smalltalk`; classification MUST be attempted via the LLM extractor first and fall back to heuristic regex when no LLM API key is configured.
- **FR-003**: The agent MUST extract booking parameters into a typed `BookingParams` Pydantic object with fields: `event_query`, `city`, `date`, `quantity`, `category`, `seat_ids`, `email`; and an explicit `missing_fields: list[str]` computed field enumerating which required fields are absent.
- **FR-004**: The agent MUST return a `clarification` response for each missing required field, asking for the first absent field in the user's detected language (Arabic or English), and MUST NOT advance the state machine until all required fields for the current transition are present.
- **FR-005**: The agent MUST enforce the membership tier ticket cap by calling `get_ticket_cap` after `lookup_member_by_email`; if the requested quantity exceeds the cap, it MUST return a polite `clarification` response naming the cap and the tier — `compute_quote` MUST NOT be called.
- **FR-006**: The agent MUST present a full booking summary (event title, date, venue, seat IDs, base price per seat, member discount amount, VAT at 15%, total in SAR, hold expiry timestamp) before any payment URL is issued; the summary MUST be shown as a `quote-card` response and the state MUST transition to `AWAITING_CONFIRMATION`.
- **FR-007**: The agent MUST NOT call `create_payment_session` unless the state is `AWAITING_CONFIRMATION` AND the current user intent is `approve`; any other path to payment is a hard violation of Constitution Principle I.
- **FR-008**: Session memory MUST hold: current event (`EventOut`), cart (category, quantity, selected seat IDs), active hold (hold token, seat IDs, `expires_at`), `pending_approval` flag, payment session ID, last tool error, and rolling sentiment labels for the last N turns.
- **FR-009**: The agent MUST support bilingual Arabic/English input and output; it MUST detect the user's language on each turn (from script and vocabulary) and respond in that language; it MUST correctly parse Arabic intent signals (e.g., "نعم", "تمام", "أريد تذكرة").
- **FR-010**: Every `AgentResponse` MUST be a typed union of: `ClarificationResponse`, `EventCardsResponse`, `QuoteCardResponse`, `SeatMapResponse`, `ConfirmationCardResponse`, `PaymentLinkResponse`, `TicketCardResponse`, `SmalltalkResponse`; the agent MUST never return an untyped string as its sole output.
- **FR-011**: The agent MUST log every tool call with timestamp, tool name, input arguments (PII-redactable), output summary, and the triggering user-message ID (Constitution Principle VII).
- **FR-012**: The agent MUST consume `classify_sentiment` on every turn and store the label in session memory; the sentiment label MUST be persisted to `interaction_log` alongside the turn's intent and tools called.
- **FR-013**: The LLM hook in `llm.py` MUST degrade gracefully to a heuristic regex extractor when no API key is configured (env vars `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` all absent); in fallback mode the agent MUST log a WARNING and continue.
- **FR-014**: `graph.py` MUST provide a LangGraph adapter stub (single-node graph wrapping the existing agent) so the multi-agent stretch goal (Constitution Principle VIII) can be grafted in without breaking the MVP.

### Key Entities

- **BookingParams**: Pydantic model capturing extracted booking parameters: `event_query`, `city`, `date`, `quantity`, `category`, `seat_ids`, `email`; computed field `missing_fields: list[str]`.
- **ConversationState**: Enum with values `GREETING`, `EVENT_SELECTION`, `MEMBER_IDENTIFIED`, `QUOTED`, `SEAT_SELECTION`, `HELD`, `AWAITING_CONFIRMATION`, `PAYMENT_PENDING`, `CONFIRMED`, `EXPIRED`, `ERROR`.
- **Intent**: Enum with values `book_ticket`, `ask_policy`, `discover`, `approve`, `reject`, `smalltalk`.
- **SessionMemory**: In-memory dataclass/Pydantic model holding current event, cart (category, quantity, seat_ids), active hold (token, seat_ids, expires_at), pending_approval flag, payment_session_id, last_error, sentiment_history (list of last-N labels).
- **AgentResponse**: Typed union (discriminated on `response_type`) of `ClarificationResponse`, `EventCardsResponse`, `QuoteCardResponse`, `SeatMapResponse`, `ConfirmationCardResponse`, `PaymentLinkResponse`, `TicketCardResponse`, `SmalltalkResponse`.
- **ConfirmationCard**: Value object assembled by `confirmation.py` containing event title, date, venue, seat_ids, base_subtotal, discount_amount, vat_amount, total, hold_expires_at — all money in SAR.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fully scripted end-to-end booking dialogue (greet → search → select event → provide email → quote → select seats → hold → confirm summary → approve → payment link) completes without error in automated tests, with all state transitions correct and no payment link emitted before the `approve` turn.
- **SC-002**: The HITL gate is never bypassed: in 100 scripted test runs across all state paths, `create_payment_session` is called exactly once per booking and only after an explicit `approve` intent in state `AWAITING_CONFIRMATION`.
- **SC-003**: Intent classification correctly maps at least 10 labelled Arabic messages and 10 English messages (including "نعم", "تمام", "لا", "yes", "confirm", "no", "cancel") to the correct intent label.
- **SC-004**: The `BookingParams` extractor populates all seven fields correctly from the canonical example message "I want 4 Gold tickets to the Coldplay show in Riyadh, nawaf@example.com" and sets `missing_fields = []`.
- **SC-005**: When a Platinum member requests 9 tickets, the agent returns a `clarification` response naming cap=8 and does not call `compute_quote` or `place_seat_hold`.
- **SC-006**: With all LLM API keys unset, the agent processes a fully-specified booking message through the heuristic fallback, reaches the `HELD` state (using mocked F001 tools), and returns a `quote-card` response — no exception is raised.
- **SC-007**: Every turn's tool calls are logged to `interaction_log` within the same request, and the log entry includes: session_id, turn number, user message (PII-redacted if email present), intent, sentiment label, and tool names called.
- **SC-008**: The state machine rejects all invalid transitions (e.g., `GREETING` → `CONFIRMED` directly): 20 invalid-transition test cases all return a `clarification` response without advancing state.

## Assumptions

- F001 (Foundation — Database Schema & Core Booking Tools) is complete and all tool functions in `src/booking_agent/tools/` are importable and tested.
- `create_payment_session`, `get_booking_status`, `generate_ticket_pdf`, `send_ticket_email`, and `handle_payment_webhook` are defined (schema available from F001 DB models) but their internal behaviour is owned by F003 (Payment & Fulfilment); the agent core calls them as opaque tool functions.
- `classify_sentiment` and `recommend_events` tool signatures are available (from F006's planned interface) but their internal recommendation/personalisation logic is out of scope for this feature; the agent consumes their outputs.
- LangChain is the agent framework for the MVP; LangGraph is reserved for the multi-agent stretch and only a stub adapter is added here.
- Session memory is in-process (dict / dataclass); Redis-backed session storage is an upgrade deferred to F004 (API Layer).
- The heuristic fallback covers the happy-path booking fields (event query, city, date, quantity, category, seat IDs, email) via regex; nuanced policy questions and smalltalk in fallback mode return a generic "I'm running in offline mode" clarification.
- Money values passed to the confirmation card come from `compute_quote` output (F001); the agent never recomputes money independently.
- The hold TTL is 10 minutes; the agent reads `expires_at` from the `HoldResult` returned by `place_seat_hold` and surfaces it verbatim in the confirmation card.
- VAT is 15% and currency is SAR throughout; the confirmation card always shows both figures explicitly.
