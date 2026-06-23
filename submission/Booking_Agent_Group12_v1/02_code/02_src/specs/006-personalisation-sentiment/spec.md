# Feature Specification: Personalisation & Sentiment

**Feature Branch**: `006-personalisation-sentiment`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "Per-user preference memory and per-turn sentiment-aware adaptation. Covers get_user_preferences(email) and update_user_preferences(email, …) over the user_preferences table (preferred categories, preferred venues/cities, typical price band, rejected categories, preferred language); recommend_events(email, context) returns preference-WEIGHTED suggestions instead of a flat catalog, and the profile auto-updates after a booking or an explicit rejection; classify_sentiment(message, history) → engaged / neutral / frustrated (LLM-based with a heuristic keyword fallback), logged per turn into interaction_log. Adaptive strategy: on detected frustration the agent stops pushing the same category, asks a more open clarifying question, offers a different event type, or surfaces a member-discount/promo to recover the conversation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Returning user sees preference-weighted suggestions (Priority: P1)

A returning user whose `user_preferences` record shows past bookings across football and rock concerts asks "What's on this weekend?" and receives a ranked list that surfaces sports and music events first — not the generic flat catalog returned to first-time users.

**Why this priority.** This is the primary WeBook-gap differentiator identified in `docs/proposal.md` §2.4 (the personalisation gap). Preference-weighted suggestions are also an explicit graded evaluation criterion in `Requirements.md` §11 ("Returning users see preference-weighted suggestions, not a flat catalog"). Without this story the feature delivers no observable user value.

**Independent test.** Seed `user_preferences` for `nawaf@example.com` with `preferred_categories=["sports","music"]`. Call `recommend_events("nawaf@example.com", context="What's on this weekend?")` against a catalog containing sports, music, and theatre events. Assert that all sports and music events appear before any theatre events in the returned list; assert the raw catalog order differs from the weighted order.

**Acceptance scenarios.**

1. **Given** `user_preferences` for `nawaf@example.com` has `preferred_categories=["sports","music"]` and `rejected_categories=["comedy"]`, **When** `recommend_events("nawaf@example.com", context="What's on this weekend?")` is called, **Then** the result ranks sports and music events above all others, and comedy events are suppressed or ranked last.
2. **Given** a user with no `user_preferences` row (cold start), **When** `recommend_events("newuser@example.com", context="anything on?")` is called, **Then** the function returns the catalog in default recency/popularity order without raising an error.
3. **Given** a user with `preferred_city="Riyadh"`, **When** `recommend_events` is called with no explicit city in context, **Then** Riyadh events are ranked above events in other cities.

---

### User Story 2 — Agent detects frustration and visibly changes strategy (Priority: P1)

A user who has rejected two consecutive suggestion sets with terse phrases ("none of these", "not interested") is classified as `frustrated` by `classify_sentiment`, and the agent loop (F002) responds by widening the event category, asking a more open clarifying question, and optionally surfacing a member promotion — instead of re-serving the same category.

**Why this priority.** Frustration detection and strategy adaptation are the second WeBook-gap differentiator (`docs/proposal.md` §2.4 "the behaviour-awareness gap") and a named graded criterion: "On detected frustration, the agent visibly changes strategy." This story produces directly observable behaviour in the demo.

**Independent test.** Call `classify_sentiment("none of these", history=[...two prior rejections...])` and assert it returns `"frustrated"`. Then call `get_adaptive_strategy("frustrated", last_category="sports")` and assert the response includes a directive to widen the category and formulate an open clarifying question, not to repeat `"sports"`.

**Acceptance scenarios.**

1. **Given** a message `"meh, none of these"` and a history of two prior rejections, **When** `classify_sentiment(message, history)` is called, **Then** it returns `"frustrated"`.
2. **Given** `classify_sentiment` returns `"frustrated"` and the last pushed category was `"sports"`, **When** `get_adaptive_strategy(sentiment="frustrated", last_category="sports")` is called, **Then** the strategy output instructs the caller NOT to re-push sports, to ask a broader open question, and to offer an alternative category.
3. **Given** an engaged opener such as `"I'd love to see something this Friday!"` with no prior rejections, **When** `classify_sentiment` is called, **Then** it returns `"engaged"` or `"neutral"` — not `"frustrated"`.
4. **Given** the LLM API is unavailable, **When** `classify_sentiment` is called, **Then** the heuristic keyword fallback runs (keywords: "none of these", "not what i", "nope", "boring", "lame", terse single-word replies) and returns a sentiment label without raising an exception.

---

### User Story 3 — Preference profile auto-updates after booking or rejection (Priority: P2)

After a booking is confirmed or after a user explicitly rejects a category mid-conversation, `update_user_preferences` is called (by the F002 agent loop) and the `user_preferences` record is updated — so future calls to `recommend_events` immediately reflect the new signal.

**Why this priority.** Without auto-update the preference profile stagnates after the first session. Automatic learning is the mechanism that makes the personalisation loop valuable over time. It is P2 because the preference-weighted recommendation (US1) can be demonstrated with a manually seeded profile during the demo.

**Independent test.** Start with an empty `user_preferences` row. Call `update_user_preferences("nawaf@example.com", booked_category="sports", booked_venue_id=1, booked_city="Riyadh", price_paid=800)`. Then call `get_user_preferences("nawaf@example.com")` and assert `preferred_categories` now includes `"sports"`, `preferred_city` is `"Riyadh"`, and `price_band` reflects the price paid.

**Acceptance scenarios.**

1. **Given** no prior `user_preferences` row, **When** `update_user_preferences(email, booked_category="sports", ...)` is called, **Then** a new row is created with `preferred_categories=["sports"]`.
2. **Given** an existing row with `preferred_categories=["music"]`, **When** `update_user_preferences(email, booked_category="sports")` is called again, **Then** `preferred_categories` becomes `["music","sports"]` (deduped, order-preserved by recency).
3. **Given** a user rejects the category `"comedy"` explicitly, **When** `update_user_preferences(email, rejected_category="comedy")` is called, **Then** `rejected_categories` includes `"comedy"` and future `recommend_events` calls suppress that category.
4. **Given** the same `rejected_category` is passed twice, **When** `update_user_preferences` is called, **Then** the category appears exactly once in `rejected_categories` (idempotent).

---

### User Story 4 — Every turn's sentiment label is logged for evaluation (Priority: P2)

Every call to `classify_sentiment` results in a row being written to `interaction_log` with the turn's `session_id`, `turn_no`, the raw `user_msg`, the classified `sentiment` label (`engaged`/`neutral`/`frustrated`), and a timestamp — enabling the bootcamp graders to audit the classifier's decisions on a held-out labelled set.

**Why this priority.** Constitution VII ("every per-turn sentiment label MUST be persisted to an append-only audit/interaction log") makes this mandatory for observability. `Requirements.md` §11 grades sentiment accuracy against a labelled set; that set must be recoverable from the log. It is P2 because it is scaffolded by the `interaction_log` table already defined in F001, and it does not block the live demo.

**Independent test.** Call `log_sentiment_turn(session_id="s1", turn_no=3, user_msg="none of these", sentiment="frustrated")`. Query `interaction_log` and assert a row exists with matching fields and `sentiment="frustrated"`.

**Acceptance scenarios.**

1. **Given** a completed `classify_sentiment` call returns `"frustrated"`, **When** the caller invokes `log_sentiment_turn(...)`, **Then** `interaction_log` contains one new row for that turn with `sentiment="frustrated"`.
2. **Given** ten turns in one session, **When** the log is queried by `session_id`, **Then** exactly ten rows are returned in ascending `turn_no` order.
3. **Given** a logging failure (e.g. DB locked), **When** `log_sentiment_turn` is called, **Then** it raises a `ToolError` subclass rather than swallowing the exception silently — so the agent loop can decide whether to retry.

---

### Edge Cases

- **Cold start (no history).** `get_user_preferences` for an unknown email returns a default `UserPreferences` sentinel (all lists empty, `price_band=None`, `language="mixed"`) — not `None` and not an exception. `recommend_events` handles this gracefully by returning the default catalog order.
- **Mixed Arabic/English sentiment signals.** Heuristic keyword lists include Arabic rejection phrases (e.g. "مو زين", "ما عجبني", "لا ما يناسب") alongside English. LLM prompt explicitly instructs bilingual classification.
- **All events in rejected categories.** `recommend_events` returns whatever remains after filtering; if the filtered list is empty it returns the full catalog with a flag indicating preferences could not be applied, rather than an empty list that breaks the agent.
- **Preference list size.** `preferred_categories` and `rejected_categories` are capped at 20 entries each; oldest entries are evicted when the cap is exceeded.
- **Idempotent update after duplicate webhook.** If `update_user_preferences` is called twice for the same `booking_id` (webhook retry), the profile must not double-count the category.
- **Neutral message misclassified as frustrated.** A very short message such as "ok" or "fine" should be `neutral`, not `frustrated`. Heuristic fallback must not over-trigger on brevity alone.
- **LLM returns an unexpected label.** If the LLM output is not one of `engaged`, `neutral`, `frustrated`, the parser falls back to `neutral` and logs a warning.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose `get_user_preferences(email: str) -> UserPreferencesOut` that reads from the `user_preferences` table and returns a sentinel for unknown emails rather than raising an error.
- **FR-002**: System MUST expose `update_user_preferences(email, booked_category?, booked_venue_id?, booked_city?, price_paid?, rejected_category?, language?)` that upserts the `user_preferences` row in a single DB transaction, deduplicates list entries, and enforces the 20-item cap.
- **FR-003**: System MUST expose `recommend_events(email: str, context: str) -> list[EventOut]` that reads preferences via `get_user_preferences`, scores each event in the catalog by preference signal, and returns a ranked list with preferred categories first and rejected categories suppressed.
- **FR-004**: System MUST expose `classify_sentiment(message: str, history: list[dict]) -> Literal["engaged","neutral","frustrated"]` using an LLM call (same provider as the agent) with a heuristic keyword fallback when the LLM is unavailable or returns an invalid label.
- **FR-005**: System MUST expose `get_adaptive_strategy(sentiment: str, last_category: str) -> AdaptiveStrategyOut` that returns a structured directive for the agent loop: whether to widen the category, suggested clarifying question template, whether to surface a promotion, and whether to suppress the last category.
- **FR-006**: System MUST expose `log_sentiment_turn(session_id, turn_no, user_msg, agent_msg?, sentiment, tools_called?)` that appends one row to `interaction_log` in a separate transaction from the booking write path.
- **FR-007**: `classify_sentiment` MUST include Arabic rejection keywords in its heuristic fallback and MUST pass the full bilingual message to the LLM without translation.
- **FR-008**: `update_user_preferences` MUST be idempotent when called with the same `booking_id` (deduplication guard on the booking-update path to survive webhook retries).
- **FR-009**: All tools in this feature MUST raise typed errors (`NotFoundError`, `ValidationToolError`) consistent with the error hierarchy in `tools/errors.py` (F001).
- **FR-010**: Every tool in this feature that writes to the DB MUST have unit tests (happy path + at least one error path) passing against an in-memory SQLite fixture before the feature is wired into the F002 agent loop.

### Key Entities

- **UserPreferences.** email (lookup key), preferred_categories (JSON list, cap 20), preferred_venues (JSON list of venue_id, cap 20), preferred_cities (JSON list, cap 20), price_band_low (minor units), price_band_high (minor units), rejected_categories (JSON list, cap 20), language (`"arabic"` / `"english"` / `"mixed"`), last_updated (UTC timestamp). Already defined in F001 schema; this feature provides the behaviour layer.
- **InteractionLog.** session_id, turn_no, user_msg (PII-redactable), agent_msg (nullable), intent (nullable), sentiment (`"engaged"` / `"neutral"` / `"frustrated"`), tools_called (JSON list), timestamp (UTC). Already defined in F001 schema; this feature writes to it.
- **AdaptiveStrategyOut** (Pydantic DTO, not a DB table). sentiment, widen_category (bool), suppress_last_category (bool), clarifying_question_template (str), surface_promotion (bool), handoff_recommended (bool, always False in MVP).
- **UserPreferencesOut** (Pydantic DTO). All fields of `UserPreferences` plus an `is_cold_start` flag indicating the sentinel was returned.
- **SentimentLabel.** An enum / `Literal` of `"engaged"` / `"neutral"` / `"frustrated"`.

## Success Criteria *(mandatory)*

- **SC-001**: `recommend_events` returns a list where all events matching `preferred_categories` rank strictly above all events not matching them, verified on a seeded catalog of at least 10 events across 4 categories.
- **SC-002**: `classify_sentiment` achieves at least **85% accuracy** on a hand-labelled evaluation set of 30 turns (10 engaged, 10 neutral, 10 frustrated, bilingual), measured by comparing model output against the ground-truth labels.
- **SC-003**: The heuristic keyword fallback alone achieves at least **70% accuracy** on the same 30-turn labelled set when the LLM is stubbed to be unavailable.
- **SC-004**: On a scripted "frustration-recovery" scenario (user rejects two suggestion sets with terse replies), the agent loop (F002, which consumes `get_adaptive_strategy`) demonstrably produces a different category and a broader clarifying question in the third turn — verifiable by inspection of the turn log.
- **SC-005**: `update_user_preferences` called twice with the same `booking_id` produces exactly one entry for the booked category (idempotency), verified by a unit test.
- **SC-006**: `log_sentiment_turn` produces one `interaction_log` row per call; after 10 turns the log contains exactly 10 rows for that session, verified by a unit test.
- **SC-007**: Cold-start path (`get_user_preferences` for unknown email) returns a sentinel without an exception, and `recommend_events` on that sentinel returns a non-empty list equal to the default catalog order.
- **SC-008**: `pytest` on `tests/test_personalisation/` and `tests/test_sentiment/` runs green in under 30 seconds on a clean clone.

## Assumptions

- The `user_preferences` and `interaction_log` tables are already created by the F001 Alembic migration; this feature adds no new migrations, only the behaviour layer on top.
- The LLM provider configured in `config.py` (OpenAI / Anthropic / Gemini) supports single-turn classification calls; the system degrades to the heuristic fallback when no API key is set (Constitution VIII — MVP must run offline for demo purposes).
- SAR is the only currency; `price_band` values are stored as integer minor units (halalas) consistent with F001 money conventions.
- The F002 agent loop is responsible for calling `classify_sentiment` and `get_adaptive_strategy` on every turn, and for calling `update_user_preferences` after a booking confirmation or explicit rejection; this feature does not self-invoke those calls.
- Arabic text arrives in Unicode (UTF-8); no transliteration is required before matching heuristic keywords.
- Human-support handoff (`handoff_recommended=True`) is a stretch goal; `AdaptiveStrategyOut.handoff_recommended` is always `False` in the MVP and the field is present only to reserve the interface for the stretch implementation.
- VAT (15%) and member discounts are not computed inside this feature; they are read from the existing `members` table by F001 tools and are referenced here only when `price_paid` is recorded for price-band calibration.
