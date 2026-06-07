# Implementation Plan: Agent Core — Conversational Booking Loop

**Branch**: `002-agent-core` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-agent-core/spec.md`

## Summary

Wire the F001 tools into a single LangChain-based booking agent that carries a
buyer from a natural-language message to a payment-ready state in one
conversation. The agent classifies intent (book_ticket / ask_policy / discover /
approve / reject / smalltalk), extracts a typed `BookingParams` Pydantic object
with an explicit `missing_fields` list, and advances a deterministic state
machine (GREETING → EVENT_SELECTION → MEMBER_IDENTIFIED → QUOTED →
SEAT_SELECTION → HELD → AWAITING_CONFIRMATION → PAYMENT_PENDING → CONFIRMED).
The mandatory HITL gate in `confirmation.py` ensures `create_payment_session` is
never called without an explicit `approve` intent from state
`AWAITING_CONFIRMATION`. An LLM-powered extractor (via `llm.py`) handles
bilingual Arabic/English NLU; a heuristic regex fallback takes over when no API
key is configured. `graph.py` adds a single-node LangGraph stub so the multi-
agent stretch can be grafted in without touching the MVP.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: LangChain (langchain-core, langchain-openai /
langchain-anthropic / langchain-google-genai — any one key activates LLM mode),
Pydantic v2, SQLAlchemy 2 (consumed via F001 tools), pydantic-settings

**Storage**: Session memory is in-process (Python dataclass); long-term
persistence via `interaction_log` / `audit_log` tables (F001 schema, SQLite /
PostgreSQL via `DATABASE_URL`)

**Testing**: pytest, pytest-mock (mock F001 tool calls), freezegun (hold-expiry
simulation)

**Target Platform**: Local backend (Windows / macOS / Linux); offline-capable
(heuristic fallback)

**Project Type**: Single Python project (`src/booking_agent/`), new `agent/`
subpackage alongside existing `db/` and `tools/`

**Performance Goals**: Agent turn-around < 2 s with LLM; < 50 ms in heuristic
fallback mode

**Constraints**: No payment URL without HITL approval; bilingual (Arabic/English)
on every turn; LLM API key is optional; no LangGraph in MVP beyond the stub

**Scale/Scope**: Single concurrent session for the demo; FastAPI session isolation
comes in F004

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment (NON-NEGOTIABLE) | `confirmation.py` assembles the full summary (event, date, venue, seats, base, member discount, VAT 15%, total, hold expiry); `policy.py` enforces the state-machine rule that `create_payment_session` is called ONLY when state == `AWAITING_CONFIRMATION` AND intent == `approve`. Hard-coded guard in `graph.py` entry point — any other path raises an internal error before touching the payment tool. ✅ |
| II. Atomic, Time-Bounded Seat Holds (NON-NEGOTIABLE) | The agent calls `place_seat_hold` (F001, all-or-nothing, 10-min TTL) and stores the returned `expires_at` in `SessionMemory`. On every subsequent turn the agent checks `expires_at < now`; if the hold has expired it transitions to the `EXPIRED` branch and does not re-attempt payment. ✅ |
| III. Tools Are Python Functions | The agent calls only in-repo Python functions from `src/booking_agent/tools/`. `tools_langchain.py` wraps each with a LangChain `@tool` decorator; no external ticketing SaaS is introduced. ✅ |
| IV. Exact, Auditable Money & Discounts | All money in the confirmation card comes from `compute_quote` (F001 — exact minor units, server-side, derived from the `members` table). The agent never recomputes or adjusts money independently; it surfaces the itemised `Quote` DTO verbatim. ✅ |
| V. Tamper-Evident Tickets & Exactly-Once Fulfilment | The agent calls `create_payment_session` (opaque) and `get_booking_status` (polling); HMAC signing, webhook idempotency, and PDF generation are owned by F003. The stub interfaces are called correctly and never bypassed. ✅ |
| VI. Test-First for Data & Money Operations | The agent itself does not write to the DB or compute money — those are F001 tools, already tested. Agent-layer tests use mocked tool calls. State-machine transition tests and HITL-gate tests are written before implementation tasks in each phase. ✅ |
| VII. Observable Reasoning | Every tool call is logged (timestamp, tool name, redacted args, output summary, user-message ID) via a LangChain callback in `llm.py`. Every state transition and per-turn sentiment label is persisted to `interaction_log` by `state.py`. ✅ |
| VIII. MVP First, Multi-Agent Later | The MVP is a single agent in `agent/`. `graph.py` adds a single-node LangGraph stub (import-safe, no new behaviour) so the multi-agent stretch can be wired in later without any MVP changes. No multi-agent logic is introduced here. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-agent-core/
├── spec.md              # Feature spec
├── plan.md              # This file
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── config.py                       # (F001) — HOLD_TTL, VAT_RATE, LLM key settings extended
├── agent/
│   ├── __init__.py                 # Public re-exports: BookingAgent, AgentResponse
│   ├── intent.py                   # Intent enum + intent_label()
│   ├── extract.py                  # BookingParams (Pydantic) + missing_fields logic
│   ├── state.py                    # ConversationState enum + SessionMemory dataclass
│   ├── policy.py                   # State-machine transitions + HITL guard
│   ├── confirmation.py             # ConfirmationCard builder (quote → card)
│   ├── responses.py                # AgentResponse union types (all response dataclasses)
│   ├── llm.py                      # LLM hook (LangChain) + heuristic regex fallback
│   ├── tools_langchain.py          # @tool wrappers around src/booking_agent/tools/*
│   └── graph.py                    # LangGraph single-node stub (stretch adapter)

tests/
├── conftest.py                     # (F001) — extended with agent session fixture
└── test_agent/
    ├── test_intent.py              # Intent classification (LLM mocked + heuristic)
    ├── test_extract.py             # BookingParams extraction + missing_fields
    ├── test_state.py               # State machine transitions, valid + invalid
    ├── test_policy.py              # HITL gate: approve path, non-approve blocked
    ├── test_confirmation.py        # ConfirmationCard values from Quote DTO
    └── test_e2e_booking.py         # End-to-end scripted dialogue (all tools mocked)
```

**Structure Decision**: Single-project `src/booking_agent/` layout; the new
`agent/` subpackage is a sibling to the existing `db/` and `tools/` packages
built in F001. No new top-level directories are introduced.

## Phase 0 — Research / Decisions

- **LangChain tool-calling vs. manual dispatch**: MVP uses LangChain's
  `AgentExecutor` with `@tool`-decorated wrappers in `tools_langchain.py`.
  Structured extraction (`with_structured_output` → `BookingParams`) handles the
  parameter-extraction step separately from tool invocation so `missing_fields`
  is always computed before any tool is called.
- **State machine location**: `policy.py` owns the transition table; `state.py`
  owns the data (SessionMemory). This separates the "what is allowed" question
  from the "what is currently true" question, making the HITL guard testable
  without any LLM involvement.
- **Heuristic fallback design**: `llm.py` checks for API key env vars at import
  time. In fallback mode it routes to `_heuristic_extract(message)` in
  `extract.py` — a set of compiled regex patterns for each `BookingParams` field
  (email, Arabic/English city names, SAR amounts, seat IDs like "G12"). The
  heuristic is intentionally conservative: unmatched fields go to `None`.
- **Bilingual NLU**: LLM mode handles Arabic/English code-switching natively.
  Fallback mode detects Arabic script via `unicodedata` block membership and
  switches response templates accordingly. Approval synonyms list (used by
  `intent.py` in fallback): `["yes","confirm","proceed","ok","sure","نعم","تمام","موافق","اوكي"]`.
- **Session memory scope**: In-process dict keyed by `session_id` for the MVP.
  F004 (API Layer) will migrate this to Redis-backed persistence; `state.py`
  exposes `load_session(session_id)` / `save_session(session_id, memory)` so the
  storage swap is one-file change.
- **LangGraph stub**: `graph.py` defines a `StateGraph` with a single node
  (the booking agent's `run_turn` function) and compiles it. The stub is
  import-safe; calling `graph.invoke` is equivalent to calling `run_turn`
  directly. No new behaviour is introduced.

## Phase 1 — Design Artifacts

- `Intent` enum and `ConversationState` enum finalised in `intent.py` and
  `state.py`; these are the stable contracts `policy.py` and `responses.py`
  depend on.
- `BookingParams` Pydantic model in `extract.py` with all seven fields
  (`event_query`, `city`, `date`, `quantity`, `category`, `seat_ids`, `email`)
  and a `@computed_field` for `missing_fields`.
- `AgentResponse` union in `responses.py`: eight response dataclasses with a
  `response_type: Literal[...]` discriminator field each.
- `SessionMemory` dataclass in `state.py`: holds current event, cart, active
  hold, `pending_approval`, `payment_session_id`, `last_error`,
  `sentiment_history`.
- Transition table in `policy.py`: a dict mapping `(ConversationState, Intent)`
  pairs to `(next_state, tools_to_call)` tuples; invalid pairs map to a
  `(current_state, "clarify")` sentinel.
- `ConfirmationCard` value object in `confirmation.py`: assembled from a `Quote`
  DTO (F001), the current event, seat_ids, and `HoldResult.expires_at`.

## Complexity Tracking

No constitution violations — table intentionally empty.
