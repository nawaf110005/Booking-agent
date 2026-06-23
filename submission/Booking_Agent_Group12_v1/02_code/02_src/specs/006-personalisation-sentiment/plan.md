# Implementation Plan: Personalisation & Sentiment

**Branch**: `006-personalisation-sentiment` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-personalisation-sentiment/spec.md`

## Summary

Build the preference-memory and sentiment-adaptation layer that differentiates
the Booking-Agent from WeBook's generic catalog. Four typed Python tools are
added — `get_user_preferences`, `update_user_preferences`, `recommend_events`,
and `classify_sentiment` — plus two helper functions: `get_adaptive_strategy`
(strategy directive on frustration) and `log_sentiment_turn` (Constitution VII
observability). All tools are consumed by the F002 agent loop; they have no
agent or LLM calls inside them except `classify_sentiment`, which calls the
configured LLM provider and falls back to a keyword heuristic. Every DB-writing
tool ships with unit tests before F002 wiring (Constitution VI).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLAlchemy 2, Pydantic v2, pydantic-settings, openai / anthropic / google-generativeai (provider-agnostic via config), existing `booking_agent.db` session and models (F001)

**Storage**: SQLite (dev/test/demo); PostgreSQL-compatible. `user_preferences` and `interaction_log` tables created by F001 Alembic migration — no new migrations in this feature.

**Testing**: pytest, pytest-cov, pytest-mock (LLM provider stub), freezegun (timestamp assertions on `last_updated`)

**Target Platform**: Local backend (same process as FastAPI app); offline-capable (heuristic fallback when no LLM key set)

**Project Type**: Single Python project (`src/booking_agent/`); new sub-packages `personalisation/` and `sentiment/` inside it

**Performance Goals**: `get_user_preferences` and `update_user_preferences` < 20ms; `recommend_events` < 100ms on a 50-event catalog; `classify_sentiment` (LLM path) < 2s p95; heuristic fallback < 5ms

**Constraints**: No LLM call inside any DB-writing tool; `classify_sentiment` must degrade gracefully to heuristic; no float money; idempotent `update_user_preferences` on duplicate booking_id

**Scale/Scope**: Demo catalog (~10–20 events); single `user_preferences` row per email; `interaction_log` unbounded but append-only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | This feature contains no payment code; it only provides preference and sentiment tools consumed upstream by the F002 agent loop, which owns the HITL gate. ✅ |
| II. Atomic, Time-Bounded Seat Holds | No hold logic here; seat-hold tools remain in F001. `update_user_preferences` uses a single DB transaction but is not a seat-hold operation. ✅ |
| III. Tools Are Python Functions | All six functions (`get_user_preferences`, `update_user_preferences`, `recommend_events`, `classify_sentiment`, `get_adaptive_strategy`, `log_sentiment_turn`) are in-repo typed Python functions. No external ticketing SaaS. ✅ |
| IV. Exact, Auditable Money | `price_band` values stored as integer minor units (halalas) consistent with F001. No money computation occurs in this feature; discount + VAT remain in F001 `compute_quote`. ✅ |
| V. Tamper-Evident Tickets | No ticket or QR code logic here. ✅ |
| VI. Test-First for Data & Money Operations | `update_user_preferences` and `log_sentiment_turn` write to the DB; both ship with unit tests (happy path + at least one error path) against an in-memory SQLite fixture before F002 wiring. ✅ |
| VII. Observable Reasoning | `log_sentiment_turn` appends every per-turn sentiment label to `interaction_log`. This is the primary Constitution VII hook for this feature. ✅ |
| VIII. MVP First, Multi-Agent Later | All code is in the single-agent surface. `get_adaptive_strategy` returns a structured directive; the LLM-based classifier uses a single provider call — no multi-agent orchestration. Human-support handoff is reserved as a stretch goal behind an always-False flag. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-personalisation-sentiment/
├── plan.md              # This file
├── spec.md              # Feature spec
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
├── personalisation/
│   ├── __init__.py
│   ├── preferences.py        # get_user_preferences, update_user_preferences
│   └── recommender.py        # recommend_events (scoring/ranking logic)
├── sentiment/
│   ├── __init__.py
│   ├── classifier.py         # classify_sentiment (LLM + heuristic fallback)
│   └── strategy.py           # get_adaptive_strategy, log_sentiment_turn
├── tools/
│   ├── schemas.py            # Extended with UserPreferencesOut, AdaptiveStrategyOut (F001 file)
│   └── errors.py             # Re-used unchanged from F001

tests/
├── test_personalisation/
│   ├── __init__.py
│   ├── test_preferences.py   # get_user_preferences (cold-start, sentinel, read-back)
│   ├── test_update.py        # update_user_preferences (upsert, dedup, cap, idempotency)
│   └── test_recommender.py   # recommend_events (ranking order, cold-start, empty-after-filter)
└── test_sentiment/
    ├── __init__.py
    ├── test_classifier.py    # classify_sentiment (LLM path mocked, heuristic fallback, bilingual)
    ├── test_strategy.py      # get_adaptive_strategy (all sentiment × category combos)
    └── test_log.py           # log_sentiment_turn (row created, 10-turn ordering, DB error)
```

**Structure Decision**: Two new sub-packages (`personalisation/` and `sentiment/`) inside `src/booking_agent/`, following the same flat-module convention as F001's `tools/` sub-package. Each sub-package has its own `__init__.py` exporting its public API. Pydantic DTOs (`UserPreferencesOut`, `AdaptiveStrategyOut`) are added to the existing `tools/schemas.py` to keep all agent-facing contracts in one place.

## Phase 0 — Research / Decisions

- **Preference scoring algorithm**: Simple additive score — `+2` per event whose `category` is in `preferred_categories`, `+1` per event whose `venue_id` is in `preferred_venues` or `city` is in `preferred_cities`, `-∞` (exclude) for events in `rejected_categories`. Ties broken by `events.datetime` ascending. Rejected `sortedcontainers` and vector-embedding approaches as over-engineered for a demo catalog of ≤ 50 events.
- **LLM classifier prompt**: One-shot prompt with a three-class label: `engaged` / `neutral` / `frustrated`. The full bilingual `message` + last three turns of `history` are passed as context. Temperature = 0 for determinism. Provider is abstracted behind a `LLMClient` wrapper in `config.py` (already used by F002).
- **Heuristic fallback**: A curated keyword set covering common English and Arabic rejection signals. Keyword match → `frustrated`. Exclamation/positive words → `engaged`. Otherwise → `neutral`. Implemented as a `_heuristic_classify` private function in `classifier.py`.
- **Idempotency on `update_user_preferences`**: The function accepts an optional `booking_id: str` parameter. A JSON set stored alongside `preferred_categories` tracks processed booking IDs; if the ID is already in the set the function returns without mutating the row.
- **`price_band` calibration**: `price_band_low` and `price_band_high` are updated using a running min/max over the last 10 `price_paid` values, stored as a JSON list in the row. Avoids a separate price-history table.
- **No new migration**: `user_preferences` and `interaction_log` are already in `migrations/versions/0001_initial.py` (F001). This feature only adds the behaviour layer.

## Phase 1 — Design Artifacts

- `UserPreferencesOut` Pydantic DTO: mirrors the ORM model plus `is_cold_start: bool`.
- `AdaptiveStrategyOut` Pydantic DTO: `sentiment`, `widen_category`, `suppress_last_category`, `clarifying_question_template`, `surface_promotion`, `handoff_recommended` (always `False` in MVP).
- `SentimentLabel = Literal["engaged", "neutral", "frustrated"]` added to `tools/schemas.py`.
- Scoring function contract: `_score_event(event: EventOut, prefs: UserPreferencesOut) -> int` — pure function, testable without DB.

## Complexity Tracking

No constitution violations — table intentionally empty.
