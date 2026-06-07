---
description: "Task list for Agent Core — Conversational Booking Loop"
---

# Tasks: Agent Core — Conversational Booking Loop

**Input**: Design documents from `/specs/002-agent-core/`

**Prerequisites**: plan.md (required), spec.md (required for user stories); F001 (`001-foundation-db-tools`) fully complete and all tools importable.

**Tests**: Included — Constitution VI (test-first for money/seat tools) applies to the policy and confirmation layers; state-machine and HITL tests are written before implementation in each phase.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (end-to-end booking + HITL), US2 (missing-field clarification), US3 (cap enforcement), US4 (heuristic fallback)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `agent/` package skeleton and extend config for LLM keys.

- [ ] T001 Create `src/booking_agent/agent/` package with `__init__.py` re-exporting `BookingAgent` and `AgentResponse`
- [ ] T002 [P] Extend `src/booking_agent/config.py` — add `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `LLM_MODEL`, `FALLBACK_MODE` settings (all optional)
- [ ] T003 [P] Add LangChain dependencies to `pyproject.toml` — `langchain-core`, `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langgraph` (optional extras); `pytest-mock`, `freezegun` to dev deps

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types (enums, Pydantic models, response union) that every other module depends on. No business logic yet.

**CRITICAL**: No agent logic or tool-wiring can begin until this phase is complete.

- [ ] T004 `src/booking_agent/agent/intent.py` — define `Intent` enum (`book_ticket`, `ask_policy`, `discover`, `approve`, `reject`, `smalltalk`) and stub `classify_intent(message, history) -> Intent`
- [ ] T005 [P] `src/booking_agent/agent/state.py` — define `ConversationState` enum (all 11 states) and `SessionMemory` dataclass (current_event, cart, active_hold, pending_approval, payment_session_id, last_error, sentiment_history); `load_session` / `save_session` stubs
- [ ] T006 [P] `src/booking_agent/agent/extract.py` — define `BookingParams` Pydantic model with all seven fields (`event_query`, `city`, `date`, `quantity`, `category`, `seat_ids`, `email`) and `@computed_field missing_fields: list[str]`; stub `extract_params(message, history) -> BookingParams`
- [ ] T007 [P] `src/booking_agent/agent/responses.py` — define all eight response dataclasses (`ClarificationResponse`, `EventCardsResponse`, `QuoteCardResponse`, `SeatMapResponse`, `ConfirmationCardResponse`, `PaymentLinkResponse`, `TicketCardResponse`, `SmalltalkResponse`) with `response_type: Literal[...]` discriminator; define `AgentResponse` union type
- [ ] T008 [P] `tests/test_agent/test_extract.py` — write tests FIRST for `BookingParams` field parsing and `missing_fields` computation (canonical full-message test, each-field-absent tests, zero-quantity validation); tests must FAIL before T015
- [ ] T009 [P] `tests/test_agent/test_state.py` — write tests FIRST for `SessionMemory` construction and field defaults; tests must FAIL before T016

**Checkpoint**: All enums, Pydantic models, and response types are importable — agent logic phases can now begin in parallel.

---

## Phase 3: User Story 1 — End-to-End Booking with HITL Confirmation Gate (Priority: P1)

**Goal**: The agent orchestrates all F001 tools through the full booking state machine, presents a confirmation card, and issues a payment link only after explicit approval.

**Independent Test**: Run `tests/test_agent/test_e2e_booking.py` with all F001 tool calls mocked; assert state advances correctly through all 9 states and `create_payment_session` is called exactly once, only after the `approve` turn.

### Tests for User Story 1 (write FIRST — must FAIL before implementation)

- [ ] T010 [P] [US1] `tests/test_agent/test_policy.py` — HITL gate tests: (a) `approve` in `AWAITING_CONFIRMATION` → `PAYMENT_PENDING`; (b) any non-`approve` intent in `AWAITING_CONFIRMATION` → stays in `AWAITING_CONFIRMATION`, `create_payment_session` not called; (c) 20 invalid-transition pairs each return `(current_state, "clarify")` — must FAIL before T018
- [ ] T011 [P] [US1] `tests/test_agent/test_confirmation.py` — `ConfirmationCard` builder tests: given a `Quote` DTO (Gold, 4 tickets, Platinum member) and a `HoldResult`, assert card fields: base=2720 SAR, discount=480 SAR, vat=408 SAR, total=3128 SAR, expires_at correct — must FAIL before T019
- [ ] T012 [P] [US1] `tests/test_agent/test_e2e_booking.py` — scripted end-to-end dialogue test (all F001 tools mocked via `pytest-mock`): assert full state sequence and `create_payment_session` call count — must FAIL before T023

### Implementation for User Story 1

- [ ] T013 [P] [US1] `src/booking_agent/agent/tools_langchain.py` — `@tool` wrappers for all F001 tools: `search_events`, `get_event_details`, `render_event_card`, `lookup_member_by_email`, `get_ticket_cap`, `get_categories_with_pricing`, `compute_quote`, `render_seat_map`, `check_seat_availability`, `place_seat_hold`, `release_seat_hold`, `get_booking_status`; stubs for F003 tools: `create_payment_session`, `generate_ticket_pdf`, `send_ticket_email`; stub for F006 tools: `classify_sentiment`, `recommend_events`
- [ ] T014 [US1] `src/booking_agent/agent/llm.py` — LLM hook: detect API key at import time; if present, build LangChain `ChatModel` with `with_structured_output(BookingParams)` for extraction and standard chat for response generation; if absent, set `FALLBACK_MODE=True` and log WARNING (heuristic activated in US4)
- [ ] T015 [US1] `src/booking_agent/agent/extract.py` — implement `extract_params` (LLM path): call LLM structured-output endpoint → `BookingParams`; handle `ValidationError` (fall back to heuristic for the failing turn, log WARNING) (depends on T006, T014)
- [ ] T016 [US1] `src/booking_agent/agent/state.py` — implement `load_session` / `save_session` (in-process dict); implement `SessionMemory` update helpers (`set_event`, `set_cart`, `set_hold`, `set_pending_approval`, `push_sentiment`) (depends on T005)
- [ ] T017 [US1] `src/booking_agent/agent/intent.py` — implement `classify_intent` (LLM path): single-prompt classification returning `Intent` enum value; bilingual approval synonym list used as a pre-check before calling LLM (depends on T004, T014)
- [ ] T018 [US1] `src/booking_agent/agent/policy.py` — implement full state-machine transition table: `(ConversationState, Intent) → (next_state, [tool_names])`; implement `HITL guard`: raises `HITLViolationError` if `create_payment_session` is requested outside the approved path (depends on T004, T005, T007)
- [ ] T019 [US1] `src/booking_agent/agent/confirmation.py` — implement `build_confirmation_card(quote: Quote, event: EventOut, seat_ids: list[str], hold_result: HoldResult) -> ConfirmationCardResponse`; asserts all money fields are non-zero SAR values and `expires_at` is in the future (depends on T007)
- [ ] T020 [US1] `src/booking_agent/agent/__init__.py` — implement `BookingAgent.run_turn(session_id, message) -> AgentResponse`: load session → classify intent → extract params → advance state via policy → call tools → build response → log to `interaction_log` → save session (depends on T013–T019)
- [ ] T021 [US1] Add LangChain logging callback in `llm.py`: on every tool call emit a structured log entry (timestamp, tool name, redacted args, output summary, user-message ID) to both Python logger and `audit_log` table (depends on T014, T020)
- [ ] T022 [US1] Make `test_policy.py` green (T010 passes)
- [ ] T023 [US1] Make `test_confirmation.py` green (T011 passes)
- [ ] T024 [US1] Make `test_e2e_booking.py` green (T012 passes)

**Checkpoint**: Full end-to-end booking flow works in tests; HITL gate proven; state machine fully functional.

---

## Phase 4: User Story 2 — Clarify Missing Fields (Priority: P1)

**Goal**: The agent asks for the first absent required field in the user's detected language and does not advance state until all required fields are present.

**Independent Test**: Run `tests/test_agent/test_extract.py` (T008) — all missing-field scenarios green; run a targeted clarification dialogue test asserting `ClarificationResponse` is returned for each absent field.

### Tests for User Story 2 (write FIRST — must FAIL before implementation)

- [ ] T025 [P] [US2] `tests/test_agent/test_intent.py` — write bilingual intent classification tests: 10 Arabic messages (including "نعم", "تمام", "أريد تذكرة", "لا", "إلغاء") and 10 English messages map to correct `Intent`; heuristic approval synonym list tested directly — must FAIL before T028

### Implementation for User Story 2

- [ ] T026 [US2] Implement `extract_params` heuristic path in `src/booking_agent/agent/extract.py`: compiled regex patterns for email, Arabic/Latin city names from a city lookup list, ISO date strings and relative dates ("tomorrow", "Friday"), integer quantities, category keywords (VIP/Gold/Silver/Standing + Arabic equivalents), seat-ID patterns (letter + digits), email (depends on T006, T015)
- [ ] T027 [P] [US2] Language detection helper in `src/booking_agent/agent/extract.py`: `detect_language(message) -> Literal["ar","en"]` using `unicodedata` Arabic block membership ratio; bilingual clarification template dict keyed by field name and language
- [ ] T028 [US2] `src/booking_agent/agent/policy.py` — add `build_clarification_response(missing_fields, language) -> ClarificationResponse`: selects first missing field, looks up bilingual template, returns `ClarificationResponse`; called by `BookingAgent.run_turn` whenever `missing_fields` is non-empty before any state-advancing tool call (depends on T018, T027)
- [ ] T029 [US2] Make `test_extract.py` green (T008 passes)
- [ ] T030 [US2] Make `test_intent.py` green (T025 passes); verify heuristic approval synonym detection works for all listed Arabic/English tokens

**Checkpoint**: All missing-field scenarios handled; bilingual clarification functional; `test_extract.py` and `test_intent.py` green.

---

## Phase 5: User Story 3 — Ticket-Cap Enforcement (Priority: P2)

**Goal**: Agent calls `get_ticket_cap` after membership lookup and refuses politely when quantity exceeds cap, naming the tier and cap in the response.

**Independent Test**: Mock `lookup_member_by_email` returning Bronze tier (cap 4) and mock `get_ticket_cap` returning 4; send "6 tickets"; assert `compute_quote` is not called and response is `ClarificationResponse` naming cap=4 and tier=Bronze.

### Tests for User Story 3 (write FIRST — must FAIL before implementation)

- [ ] T031 [P] [US3] `tests/test_agent/test_policy.py` — add cap-enforcement tests: Platinum member (cap 8) requests 9 → `ClarificationResponse` with cap=8, `compute_quote` not called; non-member (cap 4) requests 5 → same pattern; user accepts offer (replies "book 4") → state advances to `QUOTED` — must FAIL before T033

### Implementation for User Story 3

- [ ] T032 [US3] `src/booking_agent/agent/policy.py` — add cap-enforcement check in the `MEMBER_IDENTIFIED → QUOTED` transition: after `lookup_member_by_email` resolves, call `get_ticket_cap(tier)`; if `requested_qty > cap`, build `ClarificationResponse` with bilingual cap-exceeded message (mentioning tier name and cap value) and offer to proceed at cap; do not advance state or call `compute_quote` (depends on T018, T028)
- [ ] T033 [US3] Make cap-enforcement tests in `test_policy.py` (T031) green

**Checkpoint**: Cap enforcement tested and working; `compute_quote` never called when quantity exceeds cap.

---

## Phase 6: User Story 4 — Heuristic Fallback (Priority: P2)

**Goal**: With no LLM API key, the agent stays fully functional using regex extraction and deterministic response templates; a WARNING is logged.

**Independent Test**: Unset all API key env vars in the test environment; instantiate `BookingAgent`; drive a fully-specified booking message through to `HELD` state using mocked F001 tools; assert no HTTP calls are made and no exception is raised.

### Tests for User Story 4 (write FIRST — must FAIL before implementation)

- [ ] T034 [P] [US4] `tests/test_agent/test_e2e_booking.py` — add `test_fallback_e2e`: monkeypatch all LLM key env vars to `None`; run fully-specified message; assert `FALLBACK_MODE` is active, `BookingParams` populated correctly, `HoldResult` returned by mocked `place_seat_hold`, response is `QuoteCardResponse` — must FAIL before T036

### Implementation for User Story 4

- [ ] T035 [US4] `src/booking_agent/agent/llm.py` — complete fallback mode: when `FALLBACK_MODE=True`, `classify_intent` uses the approval-synonym list + keyword table for all intents; `extract_params` calls the heuristic path in `extract.py`; all response generation uses deterministic bilingual templates from `responses.py`; log `WARNING: LLM unavailable — running in heuristic fallback mode` on first call (depends on T014, T026, T027)
- [ ] T036 [US4] Make `test_fallback_e2e` (T034) green

**Checkpoint**: Fallback mode fully functional; demo runs offline without any API key.

---

## Phase 7: LangGraph Stub

**Purpose**: Add the single-node LangGraph adapter so the multi-agent stretch can be grafted in without touching any MVP code.

- [ ] T037 [P] `src/booking_agent/agent/graph.py` — implement single-node `StateGraph`: one node wrapping `BookingAgent.run_turn`; compile the graph; expose `graph.invoke({"session_id": ..., "message": ...}) -> AgentResponse`; add import guard so the module is importable even if `langgraph` is not installed (depends on T020)
- [ ] T038 [P] `tests/test_agent/test_e2e_booking.py` — add `test_graph_stub`: call `graph.invoke` with the same scripted dialogue; assert output matches direct `BookingAgent.run_turn` output (depends on T024, T037)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Logging completeness, coverage gate, smoke demo, and documentation.

- [ ] T039 [P] `src/booking_agent/agent/state.py` — implement per-turn `interaction_log` write: after each `run_turn` call, persist session_id, turn number, user message (PII-redacted if email detected), intent label, sentiment label, list of tools called, and response type to `interaction_log` table via F001 DB session (depends on T020)
- [ ] T040 [P] `scripts/smoke_demo_agent.py` — headless scripted booking session driven via `BookingAgent.run_turn` (all F001 tools live, no mocks); prints each state transition and final confirmation card; confirms no payment URL is emitted until an explicit "yes" turn (depends on T024)
- [ ] T041 [P] Extend `cli.py` — add `agent-chat` subcommand: interactive REPL that calls `BookingAgent.run_turn` per line and pretty-prints the `AgentResponse` type and key fields (depends on T020)
- [ ] T042 Run full test suite (`pytest --cov=src/booking_agent/agent tests/test_agent/`); assert coverage ≥ 80% on `agent/`; ruff clean on all new files (depends on T024, T030, T033, T036, T038)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all user-story phases.
- **US1 (Phase 3)**: Depends on Foundational (Phase 2) — the primary P1 story.
- **US2 (Phase 4)**: Depends on Foundational (Phase 2) and T015 (extract_params LLM path from US1, which provides the structure US2's heuristic path fills).
- **US3 (Phase 5)**: Depends on US1 (Phase 3) policy.py foundation (T018).
- **US4 (Phase 6)**: Depends on US2 (Phase 4) heuristic extractor (T026, T027) and US1 `llm.py` (T014).
- **LangGraph Stub (Phase 7)**: Depends on US1 `BookingAgent.run_turn` (T020).
- **Polish (Phase 8)**: Depends on all user-story phases complete.

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Foundational — no dependency on other user stories.
- **US2 (P1)**: Requires US1's `extract_params` LLM path (T015) to exist as the primary path before the heuristic fallback is layered on top; can otherwise proceed in parallel on different files (T026, T027).
- **US3 (P2)**: Requires `policy.py` from US1 (T018) — adds a new transition guard.
- **US4 (P2)**: Requires US2's heuristic extractor (T026, T027) and US1's `llm.py` (T014).

### Within Each User Story

- Test tasks (T010–T012, T025, T031, T034) MUST be written and FAIL before implementation tasks begin (Constitution VI).
- Enums and Pydantic models before services.
- Tool wrappers (`tools_langchain.py`) before agent orchestration (`__init__.py`).
- State machine (`policy.py`) before confirmation card (`confirmation.py`).
- Core agent loop (`__init__.py`, T020) before logging callback (T021).

### Parallel Opportunities

- T001, T002, T003 (Phase 1 Setup) can all run in parallel.
- T004, T005, T006, T007, T008, T009 (Phase 2 Foundational) can run in parallel after Phase 1.
- Once Foundational is done: T010–T012 (US1 tests), T013 (tool wrappers) can run in parallel before US1 implementation tasks.
- T013, T014 (tools, LLM hook) can run in parallel within US1.
- T026, T027 (heuristic extractor, language detection) can run in parallel within US2.
- T037 (graph stub) and T039 (interaction_log write) can run in parallel within Phase 7/8.

---

## Implementation Strategy

### MVP First (User Stories 1 and 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (end-to-end booking + HITL)
4. **STOP and VALIDATE**: Run `test_e2e_booking.py` and `test_policy.py`; demo `smoke_demo_agent.py`
5. Complete Phase 4: User Story 2 (missing-field clarification)
6. **STOP and VALIDATE**: Run full `tests/test_agent/` suite

### Incremental Delivery

1. Setup + Foundational → types and enums importable
2. User Story 1 → full booking loop working end-to-end (MVP!)
3. User Story 2 → clarification questions robust
4. User Story 3 → cap enforcement solid
5. User Story 4 → offline/demo mode working
6. LangGraph Stub → stretch-goal adapter ready
7. Polish → coverage gate + smoke demo + CLI

### Parallel Team Strategy

With multiple developers (after Foundational is complete):

- Developer A: User Story 1 (policy + confirmation + agent loop)
- Developer B: User Story 2 (heuristic extractor + language detection)
- Developer C: User Story 3 (cap enforcement guard) and User Story 4 (fallback mode)

---

## Notes

- All task checkboxes are UNCHECKED `[ ]` — this feature is planned, not yet built. F001 task checkboxes ([X]) served as the model for what done looks like.
- [P] tasks are on different files with no shared state — safe to parallelize.
- [Story] labels map each task to a user story for traceability and independent demo.
- Test tasks must FAIL before implementation begins (Constitution Principle VI).
- Money in confirmation cards always comes from `compute_quote` (F001 `Quote` DTO) — never recomputed in this layer.
- All money is in SAR, VAT is 15%, hold TTL is 10 minutes; these constants come from `config.py` (F001).
- PII redaction in logging: replace email addresses with `***@***.***` before writing to `interaction_log` or any Python logger at INFO or above.
- The package import path throughout is `booking_agent` (e.g., `from booking_agent.agent import BookingAgent`).
