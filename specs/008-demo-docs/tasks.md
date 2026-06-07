---
description: "Task list for Demo, Docs & Reproducibility"
---

# Tasks: Demo, Docs & Reproducibility

**Input**: Design documents from `/specs/008-demo-docs/`

**Prerequisites**: plan.md (required), spec.md (required for user stories); F001–F007 implementations complete and stable.

**Tests**: smoke_demo.py and eval_harness.py are self-validating scripts that replace unit tests for this slice. Constitution VI test-first gate applies only to money/seat tools; this feature adds none.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (one-command setup/demo), US2 (scripted scenarios), US3 (GUIDE + TECHNICAL docs), US4 (eval harness)

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `docs/` directory at repository root if absent; create `scripts/` directory if absent; create `src/booking_agent/demo/__init__.py`
- [ ] T002 [P] Audit F001–F007 actual file tree and confirm all module paths referenced in plan.md project structure exist; document any discrepancies in a single comment block at the top of `docs/TECHNICAL.md`
- [ ] T003 [P] Create `.run/` directory (gitignored) for PID files used by run script stop subcommand; add `.run/` to `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The offline stub and polished seed must exist before smoke scenarios or documentation can reference real data.

**CRITICAL**: US2 (smoke scenarios) and US1 (run scripts) depend on the seed producing a stable demo database.

- [ ] T004 `src/booking_agent/demo/stubs.py` — implement `DemoLLM(BaseChatModel)` returning pre-scripted structured responses keyed by `(scenario_name, turn_index)`; must satisfy the same LangChain interface as the real LLM adapter so `smoke_demo.py` can inject it via `DEMO_MODE=true`
- [ ] T005 Polish `scripts/seed_demo.py` — extend/replace any earlier prototype to produce the full deterministic seed: ≥5 events across ≥2 venues, ≥3 categories (Concert, Sports, Conference), all 5 membership tiers with canonical discounts (non-member 0%/cap 4, Bronze 5%/cap 4, Silver 10%/cap 6, Gold 12%/cap 6, Platinum 15%/cap 8) and ticket caps, a fully-seated layout for at least one event, and one pre-paid sample booking with a recorded HMAC QR token and idempotent `idempotency_key`; all upserts use `on_conflict_do_nothing()` on stable natural keys
- [ ] T006 Verify seed idempotency by running `python scripts/seed_demo.py` twice against a fresh `booking.db` and asserting row counts are identical on both runs

**Checkpoint**: Stable seed in place — run scripts, smoke scenarios, and docs can now reference real data.

---

## Phase 3: User Story 1 — One-command setup and run (Priority: P1)

**Goal**: `./run.sh setup && ./run.sh demo` and the PowerShell equivalent complete end-to-end on a clean clone.

**Independent test.** On a clean venv: `./run.sh setup` then `./run.sh demo`; assert exit code 0 and smoke_demo prints booking-confirmed summary.

### Implementation for User Story 1

- [ ] T007 [US1] `run.sh` at repository root — POSIX bash script implementing subcommands: `setup` (pip install + alembic upgrade head + seed_demo.py, idempotent), `backend` (starts FastAPI on port 8000, writes PID to `.run/backend.pid`), `ui` (starts Streamlit on port 8501, writes PID to `.run/ui.pid`), `test` (runs pytest with coverage), `demo` (runs smoke_demo.py --all-scenarios), `stop` (kills PIDs in `.run/*.pid` and removes files); must detect missing required `.env` variables before any operation and exit non-zero with a human-readable list of missing keys; must detect Python < 3.11 and exit non-zero
- [ ] T008 [US1] `run.ps1` at repository root — Windows PowerShell 5.1+ equivalent of run.sh with identical subcommands; sets `$OutputEncoding = [System.Text.Encoding]::UTF8` and calls `chcp 65001` at startup; uses PID files in `.run\` for stop subcommand; same `.env` validation and Python version check as run.sh
- [ ] T009 [US1] Add port-conflict detection to both `run.sh` and `run.ps1`: before starting `backend` or `ui`, check whether ports 8000/8501 are in use; if so, print a clear error naming the port and exit non-zero
- [ ] T010 [US1] Manual smoke test of `run.sh setup` on Linux/macOS: run on a clean venv, confirm exit 0, confirm `alembic upgrade head` output visible, confirm seed row counts printed
- [ ] T011 [US1] Manual smoke test of `run.ps1 setup` on Windows 11: run on a clean venv, confirm exit 0, confirm Arabic event title prints without replacement characters

**Checkpoint**: Both run scripts work on their respective platforms; setup is idempotent.

---

## Phase 4: User Story 2 — Scripted headless demo scenarios (Priority: P1)

**Goal**: `python scripts/smoke_demo.py --all-scenarios` exits 0 with all 7 scenarios `[PASS]` when `DEMO_MODE=true`.

**Independent test.** Set `DEMO_MODE=true`; run `python scripts/smoke_demo.py --all-scenarios`; assert all 7 blocks print `[PASS]` and exit code is 0.

### Implementation for User Story 2

- [ ] T012 [US2] `scripts/smoke_demo.py` — implement the main entry point with `--scenario <name>` and `--all-scenarios` flags; wire `DEMO_MODE=true` to inject `DemoLLM` from `src/booking_agent/demo/stubs.py`; each scenario is a separate function returning `(status: str, detail: str)`; print `[PASS] <scenario>` or `[FAIL] <scenario>: <detail>`; exit 0 iff all mandatory scenarios pass
- [ ] T013 [US2] Implement scenario `single-ticket` in `scripts/smoke_demo.py`: search event → member lookup → compute_quote → place_seat_hold → HITL confirmation assert (no payment URL before approval) → payment stub → generate_ticket_pdf → assert QR token present
- [ ] T014 [US2] Implement scenario `multi-ticket-member` in `scripts/smoke_demo.py`: Platinum member, 4 Gold seats, assert discount = 12%, VAT = 15%, total matches hand-computed value from spec.md US1 scenario 1
- [ ] T015 [US2] Implement scenario `cap-exceeded` in `scripts/smoke_demo.py`: Bronze member (cap 4) attempts to book 5 tickets; assert `CapExceededError` raised and agent response contains polite refusal text
- [ ] T016 [US2] Implement scenario `hold-expiry` in `scripts/smoke_demo.py`: place a hold, use `freezegun` to advance time past 10 minutes, run `release_expired_holds()`, assert seats return to `available` and the agent notifies expiry
- [ ] T017 [US2] Implement scenario `duplicate-webhook` in `scripts/smoke_demo.py`: fire the same webhook payload twice via `handle_payment_webhook`; assert `tickets` table has exactly one row for the booking; assert second call returns 200 without error
- [ ] T018 [US2] Implement scenario `frustration-recovery` in `scripts/smoke_demo.py`: inject three consecutive rejection signals ("none of these", "not what I want", "meh") via `DemoLLM`; assert `classify_sentiment` returns `frustrated`; assert agent response changes category or asks a more open question rather than repeating the same events
- [ ] T019 [US2] Implement scenario `policy-rag` in `scripts/smoke_demo.py`: ask a refund policy question; assert agent response is grounded in venue FAQ content (contains at least one verbatim phrase from the RAG knowledge base) and does not contain hallucinated policy details
- [ ] T020 [US2] Run `python scripts/smoke_demo.py --all-scenarios` with `DEMO_MODE=true`; confirm all 7 scenarios print `[PASS]` and exit code is 0

**Checkpoint**: All 7 demo scenarios pass headlessly; `./run.sh demo` works end-to-end.

---

## Phase 5: User Story 3 — GUIDE.md and TECHNICAL.md (Priority: P2)

**Goal**: Both docs are complete and sufficient for their respective audiences to act on without source code.

**Independent test.** Team member dry-run: follow only `docs/GUIDE.md` to deliver a 60-second demo; separately, use `docs/TECHNICAL.md` to identify the files implementing the 3 named tool functions.

### Implementation for User Story 3

- [ ] T021 [P] [US3] `docs/GUIDE.md` — write: (1) "What it does" one-paragraph summary; (2) "Why it matters" section mapping to the 6 market gaps from `docs/proposal.md §2.4`; (3) "How to demo it cold" step-by-step guide (prerequisites → `run.sh setup` → `run.sh backend` → `run.sh ui` → navigate to localhost:8501 → type the opening message); (4) "60-second narration script" verbatim text a presenter can read aloud reproducing the exact agent interaction from `docs/proposal.md §4`; (5) "Troubleshooting" section covering the three most common failure modes (missing `.env`, port conflict, Unicode on Windows)
- [ ] T022 [P] [US3] `docs/TECHNICAL.md` — write: (1) "Architecture" section with ASCII diagram matching `Requirements.md §9`; (2) "Module layout" table mapping every `src/booking_agent/` subdirectory (config, db/, tools/, agent/, api/, fulfilment/, rag/, demo/) to its responsibility and the F-number that introduced it; (3) "API contracts" section listing all public tool signatures and FastAPI endpoint paths with HTTP methods; (4) "Testing strategy" section naming test files, coverage targets (≥85% on tools/ and db/), and pytest commands; (5) "Extending the system" guide with three subsections: adding a new event category, adding a new membership tier (names `db/models.py`, `db/enums.py`, `db/seed.py`, and the discount table in config), and switching the LLM provider
- [ ] T023 [US3] Dry-run validation of `docs/GUIDE.md`: a teammate who did not write the feature reads only the guide and delivers the 60-second demo; document any step that required consulting source code and fix the guide accordingly
- [ ] T024 [US3] Accuracy check of `docs/TECHNICAL.md` module layout: for each of `compute_quote`, `place_seat_hold`, and `handle_payment_webhook`, confirm the named file in the table matches the actual file in the repo; correct any mismatch

**Checkpoint**: Both docs are accurate, complete, and independently validated.

---

## Phase 6: User Story 4 — Evaluation harness (Priority: P2)

**Goal**: `python scripts/eval_harness.py` prints a complete §11 results table and exits 0 when all mandatory criteria pass.

**Independent test.** Run `python scripts/eval_harness.py`; assert output contains exactly one row per §11 criterion with status PASS, FAIL, or SKIP; assert exit code 0 when all mandatory items pass.

### Implementation for User Story 4

- [ ] T025 [US4] `scripts/eval_harness.py` — implement the harness skeleton: a `Criterion` dataclass (`id`, `section`, `description`, `is_stretch`, `run: Callable[[], tuple[str, str]]`); a `run_all()` function that collects results; a `render_table()` function using `rich.table.Table` with columns: ID, Section, Description, Status, Detail; exit 0 iff no mandatory criterion is FAIL
- [ ] T026 [US4] Implement Task Performance criteria (4 rows): books one ticket end-to-end (calls smoke scenario 1), disambiguates events (calls search_events with ambiguous query), applies correct discount per tier (calls compute_quote for all 5 tiers), quote math correct including VAT (asserts hand-computed totals)
- [ ] T027 [US4] Implement Agent Behavior criteria (4 rows): asks for missing info rather than guessing (scenario injects incomplete input), never issues payment URL without confirmation (asserts HITL gate fires), refuses cap exceeded politely (calls scenario cap-exceeded), picks correct tool for intent (asserts tool call log matches intent type)
- [ ] T028 [US4] Implement Tool Usage Quality criteria (3 rows): atomic holds (scenario hold-expiry proves all-or-nothing), webhook idempotency (scenario duplicate-webhook proves exactly-one-ticket), safe DB writes (asserts no orphaned hold or booking rows after scenario runs)
- [ ] T029 [US4] Implement RAG Quality criterion (1 row): policy question grounded in venue docs (calls scenario policy-rag, asserts verbatim phrase match)
- [ ] T030 [US4] Implement Memory Quality criteria (2 rows): cart/hold/approval state maintained within session (traces session state object through scenario 1), preference-weighted suggestions for returning user (calls recommend_events with seeded preference profile, asserts preferred category appears before non-preferred)
- [ ] T031 [US4] Implement User Experience criteria (3 rows): under-2-minute booking (times scenario 1 wall clock), inline rendering (asserts seat map and ticket card are returned as bytes/image objects), bilingual parsing (injects Arabic-English code-switched input, asserts correct intent extraction) — mark bilingual as SKIP if Arabic NLU is stretch in the delivered build
- [ ] T032 [US4] Implement Personalisation & Sentiment criteria (3 rows): preference-weighted suggestions improve relevance (asserts preferred category rank), sentiment classified correctly (asserts classify_sentiment returns `frustrated` on labelled frustration input), adaptive response on frustration (calls scenario frustration-recovery, asserts strategy change)
- [ ] T033 [US4] Implement Technical Quality criteria (4 rows): clean schema/modular tools (asserts all 13 tables exist via `alembic current`), docs exist and are non-empty (checks README, GUIDE, TECHNICAL file sizes > 1 KB), tests pass with coverage ≥ 85% (runs pytest --cov), demo reproducible from clone (asserts run.sh and run.ps1 exist and are executable)
- [ ] T034 [US4] Run `python scripts/eval_harness.py` against the seeded demo database; confirm all 24 criterion rows appear with status PASS or SKIP (no FAIL); confirm exit code 0

**Checkpoint**: Evaluation harness complete; all §11 criteria accounted for and passing.

---

## Phase 7: README and CHANGELOG (Polish & Cross-Cutting)

**Purpose**: Final prose documents that frame the entire project for graders.

- [ ] T035 [P] `README.md` at repository root — write: (1) one-paragraph description matching the resume statement in `Requirements.md §14`; (2) quickstart section with exactly four steps: clone, copy `.env.example` to `.env` and fill keys, run `./run.sh setup`, run `./run.sh demo`; (3) ASCII/Mermaid architecture diagram matching `Requirements.md §9`; (4) feature map table with columns Feature, Branch, Spec, Status for F001–F007 and F008; (5) configuration reference table with columns Variable, Required, Default, Description for every `.env` key including `DATABASE_URL`, `OPENAI_API_KEY` (or equivalent), `MOYASAR_SECRET_KEY`, `MOYASAR_PUBLISHABLE_KEY`, `HMAC_SIGNING_KEY`, `SMTP_*` vars, `DEMO_MODE`, `HOLD_TTL_MINUTES` (default 10), `VAT_RATE` (default 0.15); (6) the 60-second demo script narrative (same as in GUIDE.md); (7) a "Running tests" one-liner; (8) team attribution
- [ ] T036 [P] `CHANGELOG.md` at repository root — write in Keep-a-Changelog format: `## [1.0.0] - 2026-06-07` with subsections Added listing F001 Foundation DB & Tools, F002 Agent Orchestration, F003 Payment Webhook & Idempotency, F004 Ticket Fulfilment, F005 Personalisation & Sentiment, F006 RAG Venue FAQ, F007 Multi-Event Concurrency, F008 Demo Docs & Reproducibility; include the repo URL as the comparison link placeholder
- [ ] T037 Final integration check: run `./run.sh setup && ./run.sh demo` end-to-end on a clean venv; confirm exit 0; confirm README quickstart steps match exactly what was run; fix any discrepancy in README or run scripts
- [ ] T038 [P] Spell-check and link-check all four prose documents (README.md, CHANGELOG.md, docs/GUIDE.md, docs/TECHNICAL.md): all internal file paths must resolve in the repo, all section cross-references must name real sections

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1; BLOCKS US1, US2, US3, US4.
- **US1 (Phase 3)**: Depends on Phase 2 (seed must be stable before run scripts invoke it).
- **US2 (Phase 4)**: Depends on Phase 2 (seed) and T004 (offline stub). Can proceed in parallel with US3 after Phase 2.
- **US3 (Phase 5)**: Depends on Phase 2 (need real module paths to document). Can proceed in parallel with US2 and US4 after Phase 2.
- **US4 (Phase 6)**: Depends on Phase 2 and US2 (harness reuses smoke scenario callables). Must follow T012.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Blocked only by Phase 2. No dependency on US2, US3, US4.
- **US2 (P1)**: Blocked by Phase 2 and T004. No dependency on US1, US3, US4.
- **US3 (P2)**: Blocked by Phase 2. No dependency on US1, US2, US4 — can be drafted before scenarios are finalised.
- **US4 (P2)**: Blocked by Phase 2 and T012 (harness reuses scenario callables). Otherwise independent.

### Parallel Opportunities

- T001, T002, T003 can all run in parallel (Phase 1).
- T007 (run.sh) and T008 (run.ps1) are different files — fully parallel.
- T021 (GUIDE.md) and T022 (TECHNICAL.md) are different files — fully parallel.
- T026–T033 (harness criterion groups) can be implemented in parallel by different team members once T025 (harness skeleton) is complete.
- T035 (README) and T036 (CHANGELOG) are different files — fully parallel.

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational — seed + stub).
2. Complete Phase 3 (US1 — run scripts): one-command setup works.
3. Complete Phase 4 (US2 — smoke scenarios): headless demo works.
4. **STOP and VALIDATE**: `./run.sh setup && ./run.sh demo` exits 0 on both platforms.
5. Demo is already presentable at this point.

### Incremental Delivery

1. Phase 1 + Phase 2 → Stable seed and offline stub.
2. Phase 3 (US1) → Clean-clone demo works. Deliver/validate.
3. Phase 4 (US2) → All 7 scenarios pass. Deliver/validate.
4. Phase 5 (US3) → GUIDE + TECHNICAL complete. Deliver/validate.
5. Phase 6 (US4) → Eval harness complete. Deliver/validate.
6. Phase 7 (Polish) → README + CHANGELOG + final integration check.

### Parallel Team Strategy

With multiple contributors after Phase 2:

- Contributor A: US1 (run scripts) + Phase 7 final integration.
- Contributor B: US2 (smoke scenarios) + US4 (eval harness).
- Contributor C: US3 (GUIDE.md + TECHNICAL.md) + README + CHANGELOG.

---

## Notes

- [P] tasks = different files, no dependencies — safe to run in parallel.
- [Story] label maps task to user story for traceability.
- All checkboxes are unchecked; this feature is not yet implemented.
- `seed_demo.py` must be idempotent — test this explicitly (T006) before marking Phase 2 complete.
- The offline LLM stub (`DEMO_MODE=true`) must not require Ollama, a GPU, or a real API key — it is a deterministic in-repo fixture.
- VAT = 15%; hold TTL = 10 minutes; currency = SAR. These constants appear in the seed, smoke scenarios, eval harness assertions, and the README config table — all must be consistent.
- F008 adds no new database tables or API endpoints; if any task appears to require one, flag it as a scope violation and open a separate spec.
- `run.sh` and `run.ps1` must never require `sudo`/administrator privileges; any operation that would need elevated access is out of scope.
