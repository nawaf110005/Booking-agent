---
description: "Task list for Personalisation & Sentiment — preference memory and per-turn sentiment-aware adaptation"
---

# Tasks: Personalisation & Sentiment

**Input**: Design documents from `/specs/006-personalisation-sentiment/`

**Prerequisites**: plan.md (required), spec.md (required for user stories); F001 foundation complete (ORM models + `user_preferences` + `interaction_log` tables exist; `tools/errors.py` and `tools/schemas.py` present)

**Tests**: Included — Constitution VI makes tests mandatory for `update_user_preferences` and `log_sentiment_turn` (DB-writing tools). Classifier tests use a mocked LLM provider.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (preference-weighted recommendations), US2 (frustration detection + strategy), US3 (auto-update preferences), US4 (per-turn sentiment logging)

---

## Phase 0: Setup (Shared Infrastructure)

**Purpose**: Create the two new sub-packages and extend shared DTOs before any story implementation.

- [ ] T001 Create `src/booking_agent/personalisation/__init__.py` (empty, exports public API when filled)
- [ ] T002 [P] Create `src/booking_agent/sentiment/__init__.py` (empty, exports public API when filled)
- [ ] T003 [P] Extend `src/booking_agent/tools/schemas.py` — add `UserPreferencesOut` (all `user_preferences` columns + `is_cold_start: bool`), `AdaptiveStrategyOut` (`sentiment`, `widen_category`, `suppress_last_category`, `clarifying_question_template`, `surface_promotion`, `handoff_recommended`), and `SentimentLabel = Literal["engaged","neutral","frustrated"]`
- [ ] T004 [P] Create `tests/test_personalisation/__init__.py` and `tests/test_sentiment/__init__.py`

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Shared scoring helper used by US1 and US2; must exist before recommender or strategy can be implemented.

**No new migration is required** — `user_preferences` and `interaction_log` are defined in F001 (`migrations/versions/0001_initial.py`).

- [ ] T005 Implement `_score_event(event: EventOut, prefs: UserPreferencesOut) -> int` as a private pure function in `src/booking_agent/personalisation/recommender.py` — `+2` per matching preferred category, `+1` per matching preferred venue or city, `-999` for rejected categories; ties broken by `events.datetime` ascending

**Checkpoint**: Scoring helper ready; US1 (recommender) and US2 (strategy) can now begin in parallel.

---

## Phase 2: User Story 1 — Preference-weighted recommendations (Priority: P1)

**Goal**: `get_user_preferences` returns the profile or a cold-start sentinel; `recommend_events` ranks the catalog by preference score.

**Independent test**: Seed `user_preferences` for one email; call `recommend_events`; assert sports/music events rank above theatre. Call for unknown email; assert non-empty default catalog returned.

### Tests for User Story 1 (written FIRST — must fail before implementation)

- [ ] T006 [P] [US1] Write `tests/test_personalisation/test_preferences.py` FIRST: cold-start sentinel returns `is_cold_start=True` and all-empty lists; known email returns stored values; unknown email does not raise — must fail
- [ ] T007 [P] [US1] Write `tests/test_personalisation/test_recommender.py` FIRST: preferred categories rank first; rejected categories suppressed; cold-start returns default catalog order; filtered-to-empty returns full catalog with flag — must fail

### Implementation for User Story 1

- [ ] T008 [US1] `src/booking_agent/personalisation/preferences.py` — implement `get_user_preferences(email: str, session) -> UserPreferencesOut`: query `user_preferences` by email; return sentinel `UserPreferencesOut(is_cold_start=True, ...)` for unknown email; never raise `NotFoundError`
- [ ] T009 [US1] `src/booking_agent/personalisation/recommender.py` — implement `recommend_events(email: str, context: str, session) -> list[EventOut]`: call `get_user_preferences`, call `search_events` (F001) for the full active catalog, apply `_score_event` to each event, sort descending by score then ascending by datetime, suppress rejected categories, return full catalog on empty-after-filter with `PreferencesNotAppliedWarning` logged
- [ ] T010 [US1] Export `get_user_preferences` and `recommend_events` from `src/booking_agent/personalisation/__init__.py`
- [ ] T011 [US1] Make `test_preferences.py` and `test_recommender.py` green

**Checkpoint**: User Story 1 fully functional and independently testable. A returning user gets preference-ranked suggestions; a cold-start user gets default catalog.

---

## Phase 3: User Story 2 — Frustration detection and adaptive strategy (Priority: P1)

**Goal**: `classify_sentiment` returns `engaged`/`neutral`/`frustrated`; `get_adaptive_strategy` returns a directive that changes category and question when frustrated.

**Independent test**: Call `classify_sentiment("none of these", history=[...])` with LLM mocked to be unavailable; heuristic returns `"frustrated"`. Call `get_adaptive_strategy("frustrated", "sports")`; assert `suppress_last_category=True` and `widen_category=True`.

### Tests for User Story 2 (written FIRST — must fail before implementation)

- [ ] T012 [P] [US2] Write `tests/test_sentiment/test_classifier.py` FIRST: LLM path (mocked provider returns label), heuristic fallback (LLM unavailable → keyword match), English frustration keywords, Arabic frustration keywords ("مو زين", "ما عجبني"), neutral short reply ("ok"), engaged opener, invalid LLM label falls back to `"neutral"` — must fail
- [ ] T013 [P] [US2] Write `tests/test_sentiment/test_strategy.py` FIRST: `frustrated` + last_category → `suppress_last_category=True`, `widen_category=True`, non-empty `clarifying_question_template`; `engaged` → all False; `neutral` → `widen_category=False`; `handoff_recommended` always False in MVP — must fail

### Implementation for User Story 2

- [ ] T014 [US2] `src/booking_agent/sentiment/classifier.py` — implement `classify_sentiment(message: str, history: list[dict]) -> SentimentLabel`: build prompt with last-3-turn history + bilingual message; call LLM provider via `config.LLMClient`; parse label; on exception or invalid label run `_heuristic_classify(message)` and return result; heuristic keyword lists: English (`["none of these","not what i","nope","boring","lame","not interested","meh","ugh","i don't like"]`) and Arabic (`["مو زين","ما عجبني","لا ما يناسب","مو مناسب","ما حبيت"]`)
- [ ] T015 [US2] `src/booking_agent/sentiment/strategy.py` — implement `get_adaptive_strategy(sentiment: SentimentLabel, last_category: str) -> AdaptiveStrategyOut`: `frustrated` → `widen_category=True`, `suppress_last_category=True`, `surface_promotion=True`, `clarifying_question_template` set to an open-ended bilingual template, `handoff_recommended=False`; `neutral` → `widen_category=False`, others False; `engaged` → all False
- [ ] T016 [US2] Export `classify_sentiment` and `get_adaptive_strategy` from `src/booking_agent/sentiment/__init__.py`
- [ ] T017 [US2] Make `test_classifier.py` and `test_strategy.py` green

**Checkpoint**: User Story 2 fully functional. Frustration is detected and strategy directive is ready for F002 consumption.

---

## Phase 4: User Story 3 — Auto-update preferences after booking or rejection (Priority: P2)

**Goal**: `update_user_preferences` upserts the `user_preferences` row; idempotent on duplicate `booking_id`; deduplicates list entries; enforces 20-item cap.

**Independent test**: Start with empty row; call `update_user_preferences(email, booked_category="sports", booking_id="b1")`; assert row created with `preferred_categories=["sports"]`. Call again with same `booking_id`; assert no duplicate. Call with `rejected_category="comedy"`; assert `rejected_categories=["comedy"]`.

### Tests for User Story 3 (written FIRST — must fail before implementation)

- [ ] T018 [P] [US3] Write `tests/test_personalisation/test_update.py` FIRST: upsert creates new row; second call same booking_id is idempotent; rejected category added and deduped; 21st preferred_category evicts oldest; price_band_low/high updated; language field updated; partial call (only one kwarg) leaves other fields unchanged — must fail

### Implementation for User Story 3

- [ ] T019 [US3] `src/booking_agent/personalisation/preferences.py` — implement `update_user_preferences(email: str, session, *, booked_category: str | None = None, booked_venue_id: int | None = None, booked_city: str | None = None, price_paid: int | None = None, rejected_category: str | None = None, language: str | None = None, booking_id: str | None = None) -> None`: load or create row in one transaction; check `booking_id` against processed-ids JSON set for idempotency; append to `preferred_categories` / `rejected_categories`; evict oldest when list exceeds 20; update `price_band_low`/`price_band_high` running min/max; set `last_updated = utcnow()`
- [ ] T020 [US3] Make `test_update.py` green

**Checkpoint**: User Story 3 fully functional. Preferences auto-learn from bookings and rejections without manual intervention.

---

## Phase 5: User Story 4 — Per-turn sentiment logging for evaluation (Priority: P2)

**Goal**: `log_sentiment_turn` appends one `interaction_log` row per call; rows are in turn-number order; DB error raises `ToolError`.

**Independent test**: Call `log_sentiment_turn("s1", 3, "none of these", "frustrated")`; query `interaction_log`; assert row exists with correct `sentiment`. Call 10 times for same session; assert 10 rows in ascending `turn_no` order.

### Tests for User Story 4 (written FIRST — must fail before implementation)

- [ ] T021 [P] [US4] Write `tests/test_sentiment/test_log.py` FIRST: row created with correct fields; 10-turn session has 10 rows ordered by `turn_no`; missing optional fields (`agent_msg`, `tools_called`) stored as NULL without error; DB locked raises `ToolError` not silent pass — must fail

### Implementation for User Story 4

- [ ] T022 [US4] `src/booking_agent/sentiment/strategy.py` — implement `log_sentiment_turn(session_id: str, turn_no: int, user_msg: str, sentiment: SentimentLabel, session, *, agent_msg: str | None = None, tools_called: list[str] | None = None) -> None`: create `InteractionLog` ORM row; commit in its own transaction separate from booking writes; on `OperationalError` raise `ToolError("interaction_log write failed")`
- [ ] T023 [US4] Make `test_log.py` green

**Checkpoint**: User Story 4 fully functional. Every turn's sentiment is persisted for grader evaluation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Coverage gate, linting, hand-labelled evaluation set, smoke integration.

- [ ] T024 [P] Add hand-labelled evaluation CSV `tests/test_sentiment/labelled_turns.csv` (30 rows: 10 engaged, 10 neutral, 10 frustrated; bilingual; columns: `message`, `history_summary`, `ground_truth`) for SC-002 and SC-003 measurement
- [ ] T025 [P] Write `tests/test_sentiment/test_accuracy.py`: load `labelled_turns.csv`, call `classify_sentiment` with LLM mocked to return the label it would produce (parametrised on heuristic-only mode for SC-003), assert accuracy >= 85% LLM / 70% heuristic
- [ ] T026 [P] Export all six public functions from `src/booking_agent/personalisation/__init__.py` and `src/booking_agent/sentiment/__init__.py`; update `src/booking_agent/__init__.py` re-exports if present
- [ ] T027 Run `pytest tests/test_personalisation/ tests/test_sentiment/ --cov=src/booking_agent/personalisation --cov=src/booking_agent/sentiment --cov-fail-under=85`; fix any gaps
- [ ] T028 [P] Run `ruff check src/booking_agent/personalisation/ src/booking_agent/sentiment/` and resolve any lint errors
- [ ] T029 Add `scripts/smoke_personalisation.py` — headless script: seed one user's preferences, call `recommend_events`, print ranked list; call `classify_sentiment` with a frustrated sample, print label and strategy directive; no API key required (heuristic mode)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 0)**: No dependencies — start immediately. T001–T004 can all run in parallel.
- **Foundational (Phase 1)**: Depends on T003 (`schemas.py` DTOs) and T004 (test packages). Blocks US1 (recommender) and US2 (strategy).
- **US1 (Phase 2)**: Depends on Phase 1 (T005 scorer). Can start once T005 is complete.
- **US2 (Phase 3)**: Depends on Phase 0 (T003 DTOs). Can start in parallel with US1 after Phase 0.
- **US3 (Phase 4)**: Depends on Phase 0 (T003 DTOs) and Phase 2 T008 (`preferences.py` file exists to add `update_user_preferences` into).
- **US4 (Phase 5)**: Depends on Phase 0 (T003 DTOs) and Phase 3 T015 (`strategy.py` file exists to add `log_sentiment_turn` into).
- **Polish (Phase 6)**: Depends on all four user stories being complete (T011, T017, T020, T023).

### User Story Dependencies

- **US1 (P1)**: Starts after T005 (scorer) — no dependency on US2, US3, US4.
- **US2 (P1)**: Starts after T003 (DTOs) — no dependency on US1, US3, US4. Can run in parallel with US1.
- **US3 (P2)**: Starts after T008 (`preferences.py` created by US1) — depends on US1 file, but not US1 tests.
- **US4 (P2)**: Starts after T015 (`strategy.py` created by US2) — depends on US2 file, but not US2 tests.

### Within Each User Story

- Test files MUST be written and FAIL before implementation files are created (Constitution VI).
- Schemas before service implementation.
- Implementation before making tests green.

### Parallel Opportunities

- T001, T002, T003, T004 (Phase 0) — all independent, run together.
- T006, T007 (US1 tests) — independent, run together.
- T012, T013 (US2 tests) — independent, run together.
- T006/T007 (US1 tests) and T012/T013 (US2 tests) — can be written in parallel across stories.
- T024, T025, T026, T027, T028 (Polish) — T024/T025/T026/T028 are independent of each other; T027 (coverage) runs last.

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 0: Setup (T001–T004).
2. Complete Phase 1: Foundational scorer (T005).
3. Complete Phase 2: US1 preference-weighted recommendations (T006–T011).
4. Complete Phase 3: US2 frustration detection + strategy (T012–T017).
5. **STOP and VALIDATE**: Demo preference ranking and frustration recovery independently.
6. Wire US1 + US2 into F002 agent loop.

### Incremental Delivery

1. Setup + Foundational → scorer ready.
2. Add US1 → test independently → demonstrate preference ranking (P1 MVP).
3. Add US2 → test independently → demonstrate frustration detection (P1 MVP).
4. Add US3 → test independently → preferences auto-learn from bookings (P2).
5. Add US4 → test independently → per-turn sentiment logged for graders (P2).
6. Polish → coverage gate, accuracy CSV, smoke script.

### Parallel Team Strategy

With two developers available after Phase 1:
- Developer A: US1 (preferences + recommender).
- Developer B: US2 (classifier + strategy).
- Both integrate into F002 after individual stories are tested.

---

## Notes

- [P] tasks = different files, no shared state dependencies — safe to run in parallel.
- [Story] label maps each task to its user story for grading traceability.
- Verify tests FAIL before writing implementation (Constitution VI — test-first for DB-writing tools).
- `update_user_preferences` and `log_sentiment_turn` are the only DB-writing tools in this feature; both require tests before wiring.
- `classify_sentiment` calls the LLM provider; all tests mock the provider so the test suite runs without an API key.
- The `booking_id` idempotency guard in `update_user_preferences` is critical to prevent double-counting from webhook retries (Constitution V analogue for this feature).
- `handoff_recommended` in `AdaptiveStrategyOut` is always `False` in the MVP; the field is reserved for the stretch human-support handoff goal (Requirements.md §13).
- Commit after each checkpoint to enable graders to inspect incremental progress.
