# Feature Specification: Demo, Docs & Reproducibility

**Feature Branch**: `008-demo-docs`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "Make the whole project demoable from a clean clone with one command and documented for graders. Covers: a polished deterministic seed (multi-event catalog + the 5 membership tiers + a fully-seated venue layout + one pre-paid sample booking so the ticket/QR demo works instantly); a comprehensive README (quickstart, architecture diagram, feature map linking to specs/001..007, configuration table, the 60-second demo script); a CHANGELOG; docs/GUIDE.md (non-technical walkthrough); docs/TECHNICAL.md (architecture deep-dive); scripted demo scenarios; run scripts run.ps1 and run.sh; and an evaluation harness/checklist enumerating the graded scenarios from Requirements §11."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One command sets up and runs the full stack on a clean clone (Priority: P1)

As a grader or collaborator who has just cloned the repo, I can run a single command (`./run.sh setup && ./run.sh demo` on Linux/macOS or `.\run.ps1 setup; .\run.ps1 demo` on Windows) and reach a fully seeded, running Booking-Agent demo — without editing any file except `.env` — within five minutes on a machine that has Python 3.11 and pip.

**Why this priority.** The Constitution and the proposal Appendix both name "reproducible from a clean clone against the Moyasar sandbox with one command" as a hard deliverable. Requirements §11 grades Technical Quality on exactly this. Nothing else in feature 008 matters if the cold-start path is broken.

**Independent test.** On a clean virtual environment with no prior state: run `./run.sh setup`, then `./run.sh demo`; assert the process exits 0 and the console prints a booking-confirmed summary including a QR token.

**Acceptance scenarios.**

1. **Given** a freshly cloned repository and a `.env` file with valid API keys, **When** `./run.sh setup` is executed, **Then** all Python dependencies are installed, the database is initialised with `alembic upgrade head`, and the demo seed is applied — all without interactive prompts.
2. **Given** setup has completed successfully, **When** `./run.sh demo` is executed, **Then** `scripts/smoke_demo.py` runs to completion with exit code 0, printing at minimum: event found, quote computed, hold placed, booking confirmed, QR token displayed.
3. **Given** setup has completed successfully, **When** `./run.sh backend` is executed, **Then** the FastAPI server starts and `GET /health` returns `{"status": "ok"}` within 10 seconds.
4. **Given** the backend is running, **When** `./run.sh ui` is executed, **Then** the Streamlit interface launches and is reachable on `http://localhost:8501`.
5. **Given** the user runs `./run.sh stop`, **Then** all background processes started by prior subcommands are terminated cleanly.

---

### User Story 2 — A scripted end-to-end demo runs headless with a demo key (Priority: P1)

As a grader evaluating the agent offline, I can run `./run.sh demo` and watch `scripts/smoke_demo.py` exercise all seven scripted scenarios in sequence — single-ticket, multi-ticket member, cap-exceeded refusal, hold-expiry, duplicate-webhook idempotency, frustration-recovery, and policy question via RAG — with the LLM configured via `DEMO_MODE=true` to use a deterministic offline stub if no real API key is present, so the demo never fails due to a missing key.

**Why this priority.** Graders must be able to evaluate all eight §11 criteria in one sitting without configuring a real payment account. A headless, reproducible scripted demo is the lowest-friction path to a complete evaluation.

**Independent test.** Set `DEMO_MODE=true` and run `python scripts/smoke_demo.py --all-scenarios`; assert all seven scenario blocks print `PASS` and the process exits 0.

**Acceptance scenarios.**

1. **Given** `DEMO_MODE=true` in `.env`, **When** `smoke_demo.py --scenario single-ticket` is run, **Then** the script walks the full booking flow (search → quote → hold → confirm → payment stub → ticket generation) and prints `[PASS] single-ticket`.
2. **Given** `DEMO_MODE=true`, **When** `smoke_demo.py --scenario cap-exceeded` is run, **Then** the script attempts to book more tickets than the member tier allows and confirms a polite refusal, printing `[PASS] cap-exceeded`.
3. **Given** `DEMO_MODE=true`, **When** `smoke_demo.py --scenario duplicate-webhook` is run, **Then** the script fires the same webhook payload twice and asserts exactly one ticket exists, printing `[PASS] duplicate-webhook`.
4. **Given** `DEMO_MODE=true`, **When** `smoke_demo.py --scenario frustration-recovery` is run, **Then** the script injects three consecutive rejection signals, asserts the agent changes category/question strategy, and prints `[PASS] frustration-recovery`.
5. **Given** `DEMO_MODE=true`, **When** `smoke_demo.py --all-scenarios` is run, **Then** all seven scenarios pass and the final line prints `All 7 scenarios passed`.

---

### User Story 3 — GUIDE.md and TECHNICAL.md let a non-author run and explain the demo (Priority: P2)

As a bootcamp instructor or non-technical stakeholder, I can read `docs/GUIDE.md` in under 10 minutes and understand what the agent does, why it matters, and how to narrate a live demo to an audience. As a technical reviewer, I can read `docs/TECHNICAL.md` and understand the architecture, the module layout, the API contracts, the testing strategy, and how to extend the system with a new event category or fulfilment channel.

**Why this priority.** Requirements §12 grades "GitHub repository + documentation + demo." Graders may not read source code — they read the docs. Clear, accurate documentation is direct scoring surface.

**Independent test.** Ask a team member who did not write a given feature to follow only `docs/GUIDE.md` and deliver a 60-second live demo to a non-technical audience. They should be able to do so without consulting source code.

**Acceptance scenarios.**

1. **Given** `docs/GUIDE.md` exists and is complete, **When** a non-author reads the "What it does" and "60-second demo script" sections, **Then** they can reproduce the exact agent interaction described in `docs/proposal.md §4` example without opening any `.py` file.
2. **Given** `docs/TECHNICAL.md` exists and is complete, **When** a technical reviewer reads the "Module layout" section, **Then** they can correctly identify which Python file implements `compute_quote`, `place_seat_hold`, and `handle_payment_webhook` without using search.
3. **Given** `docs/TECHNICAL.md` includes an "Extending the system" section, **When** a developer follows it to add a new membership tier, **Then** the only files they need to touch are the ones the guide names, in the order it names them.

---

### User Story 4 — The evaluation scenarios are enumerated and runnable (Priority: P2)

As a grader running the evaluation harness, I can open `scripts/eval_harness.py` (or a companion checklist document) and find every graded criterion from Requirements §11 mapped to a runnable scenario with an explicit pass/fail assertion, so I can score the submission methodically without improvising test cases.

**Why this priority.** Requirements §11 lists eight evaluation categories totalling the submission grade. An explicit harness reduces grader friction and ensures the team's implementation covers every criterion.

**Independent test.** Run `python scripts/eval_harness.py`; every criterion in §11 appears in the output with a status of PASS, SKIP (if the feature is stretch), or FAIL with a reason.

**Acceptance scenarios.**

1. **Given** the evaluation harness exists, **When** `python scripts/eval_harness.py` is run against the demo seed, **Then** it prints a table with one row per §11 criterion (Task Performance × 4, Agent Behavior × 4, Tool Usage Quality × 3, RAG Quality × 1, Memory Quality × 2, User Experience × 3, Personalisation & Sentiment × 3, Technical Quality × 4) and an overall result line.
2. **Given** the evaluation harness runs successfully, **When** all mandatory MVP criteria pass, **Then** the exit code is 0; if any mandatory criterion fails, the exit code is non-zero.
3. **Given** a criterion is a stretch goal (e.g., voice booking), **When** the harness encounters it, **Then** it prints `SKIP (stretch)` rather than `FAIL`, so a missing stretch goal does not fail the run.

---

### Edge Cases

- What happens when `.env` is missing or incomplete? `run.sh setup` must detect missing required variables (at minimum `DATABASE_URL`), print a human-readable error listing the missing keys, and exit non-zero — never hang or silently produce a corrupt database.
- What happens on Windows with a UTF-8 console? `run.ps1` must set `$OutputEncoding = [System.Text.Encoding]::UTF8` and `chcp 65001` so Arabic event titles and SAR symbol print without replacement characters.
- What happens when a port (8000, 8501) is already in use? The run scripts must detect the conflict, print a clear message naming the port, and exit non-zero rather than starting a second process silently.
- What happens when the seed has already been applied? `./run.sh setup` must be idempotent — running it twice must not duplicate events, members, or the pre-paid booking.
- What happens when `DEMO_MODE=true` but an actual `OPENAI_API_KEY` is also present? The offline stub takes precedence in demo mode; the real key is ignored during scripted scenarios.
- What happens on Python < 3.11? The setup script must detect the version, print a clear minimum-version error, and exit before attempting to install dependencies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `run.sh` and `run.ps1` scripts at the repository root, each supporting the subcommands `setup`, `backend`, `ui`, `test`, `demo`, and `stop`.
- **FR-002**: The `setup` subcommand MUST install Python dependencies, run `alembic upgrade head`, and execute `seed_demo.py` — all idempotently — without interactive prompts.
- **FR-003**: The `demo` subcommand MUST execute `scripts/smoke_demo.py --all-scenarios` and surface its exit code to the caller.
- **FR-004**: `scripts/seed_demo.py` MUST produce a deterministic, idempotent seed containing: a multi-event catalog (at minimum 5 events across 2 venues and at least 3 categories — Concert, Sports, Conference), all 5 membership tiers (non-member, Bronze, Silver, Gold, Platinum) with the canonical discount percentages and ticket caps from Requirements §10, a fully-seated venue layout for at least one event, and one pre-paid sample booking with a generated PDF ticket and QR token so the ticket/QR demo works without completing a live payment.
- **FR-005**: `scripts/smoke_demo.py` MUST implement the seven scripted demo scenarios: (1) single-ticket booking, (2) multi-ticket member booking, (3) cap-exceeded refusal, (4) hold-expiry, (5) duplicate-webhook idempotency, (6) frustration-recovery, (7) policy question via RAG. Each scenario MUST print `[PASS]` or `[FAIL]` and the overall run MUST exit 0 only when all mandatory scenarios pass.
- **FR-006**: `scripts/smoke_demo.py` MUST support `DEMO_MODE=true` to use an offline LLM stub so the demo runs without a real API key.
- **FR-007**: `scripts/eval_harness.py` MUST map every graded criterion in Requirements §11 to a runnable assertion and print a structured results table. It MUST exit 0 only when all mandatory (non-stretch) criteria pass.
- **FR-008**: `README.md` at the repository root MUST include: a one-paragraph description, a quickstart section (clone → configure `.env` → `./run.sh setup` → `./run.sh demo`), an ASCII/Mermaid architecture diagram, a feature map table linking F001–F007 to their spec files, a configuration reference table for all `.env` variables, and the 60-second demo script narrative.
- **FR-009**: `CHANGELOG.md` MUST exist at the repository root and record the initial 1.0.0 entry summarising all features F001–F007 with their dates.
- **FR-010**: `docs/GUIDE.md` MUST provide: a "What it does" section, a "Why it matters" section (pain points addressed), a step-by-step "How to demo it cold" section, and a 60-second narration script that a non-author can read aloud verbatim.
- **FR-011**: `docs/TECHNICAL.md` MUST provide: an architecture deep-dive, a module layout table mapping every `src/booking_agent/` subdirectory to its responsibility, all public API contracts (tool signatures, FastAPI endpoint paths and HTTP methods), the testing strategy and coverage targets, and an "Extending the system" guide covering at minimum: adding a new event category, adding a new membership tier, and switching the LLM provider.
- **FR-012**: `run.sh` and `run.ps1` MUST detect missing required `.env` variables and exit non-zero with a human-readable error before attempting any operation.
- **FR-013**: `run.ps1` MUST configure UTF-8 output encoding so Arabic and SAR symbols render correctly on Windows consoles.
- **FR-014**: All documentation files (README.md, CHANGELOG.md, docs/GUIDE.md, docs/TECHNICAL.md) MUST be written in English. Arabic phrases MAY appear in example interactions.

### Key Entities

- **DemoSeed**: The deterministic dataset produced by `seed_demo.py` — events, venues, seat layouts, seats, members (all 5 tiers), one pre-paid booking, one issued ticket with QR token.
- **SmokeScenario**: A named, self-contained test sequence in `smoke_demo.py` that exercises one end-to-end path and emits a structured pass/fail result.
- **EvalCriterion**: A row in the evaluation harness mapping a Requirements §11 graded item to one or more runnable assertions.
- **RunScript**: Either `run.sh` (POSIX) or `run.ps1` (Windows PowerShell) — entry point for all operational subcommands on a clean clone.

## Success Criteria *(mandatory)*

- **SC-001**: A developer who has never seen the repo can go from `git clone` to a running demo in under 5 minutes by following only the README quickstart — measured on a clean virtual machine with Python 3.11 and pip installed.
- **SC-002**: `./run.sh setup && ./run.sh demo` (or the PowerShell equivalent) completes with exit code 0 on both Linux/macOS and Windows 11 without manual intervention beyond creating `.env`.
- **SC-003**: `python scripts/smoke_demo.py --all-scenarios` with `DEMO_MODE=true` exits 0 with all 7 scenario blocks printing `[PASS]`.
- **SC-004**: `python scripts/eval_harness.py` prints a results table covering all 24 graded criteria from Requirements §11 (or marks stretch items as `SKIP`) and exits 0 when all mandatory criteria pass.
- **SC-005**: `docs/GUIDE.md` is sufficient for a non-author to deliver a 60-second live demo to a non-technical audience without consulting any `.py` file — verified by a teammate dry-run.
- **SC-006**: `docs/TECHNICAL.md` correctly names the implementing file for `compute_quote`, `place_seat_hold`, and `handle_payment_webhook` — verified by cross-referencing the actual source tree.
- **SC-007**: The demo seed is idempotent: running `./run.sh setup` twice produces the same database state as running it once (no duplicate rows, same pre-paid booking id).
- **SC-008**: `run.sh setup` detects a missing `DATABASE_URL` (or the equivalent required variable) and exits non-zero with a human-readable error in under 2 seconds.

## Assumptions

- F001–F007 are complete and their implementations are stable before F008 documentation is finalised; the docs describe the actual delivered system, not a planned one.
- The Moyasar sandbox credentials are available in `.env`; the demo seed's pre-paid booking uses a recorded sandbox webhook payload so the ticket/QR demo works offline.
- Python 3.11+ and pip are already installed on the grader's machine; `run.sh`/`run.ps1` do not manage Python installation itself.
- The repository uses `src/booking_agent/` as the package root (established in F001); all documentation references this path.
- VAT is 15% (Saudi rate, ZATCA-aligned) and the hold TTL is 10 minutes — these constants appear in the configuration reference table in README.md.
- The offline LLM stub for `DEMO_MODE=true` is a deterministic fixture, not a running local model; it does not require Ollama or any GPU.
- The CHANGELOG follows "Keep a Changelog" format (https://keepachangelog.com); version 1.0.0 is the initial release covering F001–F007.
- `run.sh` targets bash (POSIX); `run.ps1` targets Windows PowerShell 5.1+; neither requires administrator/sudo privileges.
- This feature (F008) is purely packaging, documentation, and scripting; it adds no new agent logic, database tables, or API endpoints beyond what F001–F007 deliver.
