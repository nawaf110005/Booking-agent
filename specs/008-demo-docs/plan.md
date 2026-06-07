# Implementation Plan: Demo, Docs & Reproducibility

**Branch**: `008-demo-docs` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-demo-docs/spec.md`

## Summary

Package and document everything F001–F007 delivered so the project is
demoable from a clean clone with one command. This slice adds: polished
deterministic seed data (multi-event catalog, all 5 membership tiers,
fully-seated layout, one pre-paid booking with a real QR token), run
scripts for every platform, seven scripted smoke scenarios, a formal
evaluation harness mapped to Requirements §11, and the three prose documents
graders read (README, GUIDE.md, TECHNICAL.md). No new agent logic, database
tables, or API endpoints are introduced — this is pure packaging, scripting,
and documentation on top of the complete F001–F007 surface.

## Technical Context

**Language/Version**: Python 3.11+ (scripts); Bash (run.sh); PowerShell 5.1+ (run.ps1)

**Primary Dependencies**: All F001–F007 runtime deps (already in `pyproject.toml`); no new packages required. `rich` (already a dep) used for harness table output.

**Storage**: SQLite demo DB (`booking.db`); seed applied idempotently via `scripts/seed_demo.py`

**Testing**: pytest (existing suite); `smoke_demo.py` self-validates; `eval_harness.py` is the formal grading checklist

**Target Platform**: Linux/macOS (run.sh) + Windows 11 (run.ps1); offline-capable via `DEMO_MODE=true`

**Project Type**: Documentation + scripting layer over existing single Python project (`src/booking_agent/`)

**Performance Goals**: `./run.sh setup` completes in under 5 minutes on a standard laptop; `./run.sh demo` in under 60 seconds

**Constraints**: No new dependencies beyond what F001–F007 already pin; run scripts require no admin/sudo; demo must work without a real LLM key when `DEMO_MODE=true`

**Scale/Scope**: One repo, one demo database, seven scripted scenarios, ~24 graded evaluation criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | `smoke_demo.py` scenario 1 explicitly asserts the HITL confirmation step fires before any payment URL is generated; the scenario fails if the gate is absent. ✅ |
| II. Atomic, Time-Bounded Seat Holds | Scenario 4 (hold-expiry) exercises the 10-minute TTL and sweeper path end-to-end; the demo seed places holds with the canonical TTL. ✅ |
| III. Tools Are Python Functions | All scripts call `booking_agent` tools via the normal import path — no external ticketing SaaS introduced. The offline stub in `DEMO_MODE` is an in-repo fixture, not a third-party service. ✅ |
| IV. Exact, Auditable Money | `seed_demo.py` pre-paid booking is seeded with exact SAR minor-unit figures (base, discount, VAT 15%, total) matching the canonical quote math; scenario 2 (multi-ticket member) asserts quote correctness. ✅ |
| V. Tamper-Evident Tickets & Exactly-Once Fulfilment | The pre-paid sample booking in the seed carries a valid HMAC QR token; scenario 5 (duplicate-webhook) asserts exactly one ticket after two identical webhook deliveries. ✅ |
| VI. Test-First for Data & Money Operations | F008 adds no new money or seat tools; `eval_harness.py` and `smoke_demo.py` are integration/demo scripts, not tool implementations, so the test-first gate does not apply to this slice. ✅ |
| VII. Observable Reasoning | `smoke_demo.py` and `eval_harness.py` print structured output per scenario/criterion so graders can trace every assertion. The existing `audit_log` is exercised by the demo scenarios. ✅ |
| VIII. MVP First, Multi-Agent Later | No multi-agent code introduced; this slice documents and validates the single-agent MVP only. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/008-demo-docs/
├── spec.md              # Feature spec
├── plan.md              # This file
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
# Files added or polished by this feature (repository root and existing packages)

README.md                          # Comprehensive: quickstart, arch diagram, feature map, config table, 60-sec script
CHANGELOG.md                       # Keep-a-Changelog format; 1.0.0 entry covering F001–F007
run.sh                             # POSIX: setup | backend | ui | test | demo | stop
run.ps1                            # Windows PowerShell: same subcommands; sets UTF-8 encoding

docs/
├── GUIDE.md                       # Non-technical walkthrough + 60-second narration script
└── TECHNICAL.md                   # Architecture deep-dive, module layout, API contracts, testing strategy, extending

scripts/
├── seed_demo.py                   # Polished deterministic seed (replaces/upgrades any earlier prototype)
├── smoke_demo.py                  # 7 scripted demo scenarios + --all-scenarios + DEMO_MODE offline stub
└── eval_harness.py                # §11 grading harness: one row per criterion, exit code 0 on all-pass

src/booking_agent/
└── demo/
    ├── __init__.py
    └── stubs.py                   # Offline LLM stub used by smoke_demo when DEMO_MODE=true
```

**Structure Decision**: Single-project layout matching the F001 foundation. All new files live at the repo root (docs/, scripts/, run scripts) or in the existing `src/booking_agent/` package as a `demo/` subpackage for the offline stub. No new top-level directories beyond `docs/`.

## Phase 0 — Research / Decisions

- **Offline LLM stub design**: The stub in `src/booking_agent/demo/stubs.py` must satisfy the same interface as the real LangChain LLM adapter so `smoke_demo.py` can swap it in without changing agent code. Decision: implement `DemoLLM` as a LangChain `BaseChatModel` subclass returning pre-scripted structured responses keyed by scenario name and turn index. This keeps `DEMO_MODE` self-contained and reviewable.
- **Seed idempotency**: `seed_demo.py` uses upsert-on-conflict logic (SQLAlchemy `insert().on_conflict_do_nothing()`) keyed on stable natural keys (event slug, member email, seat composite key) so running it twice is safe. The pre-paid booking is keyed on a fixed `idempotency_key` constant in the seed file.
- **Harness structure**: `eval_harness.py` maps §11 criteria to Python callables. Each callable returns `(status, message)` where `status` is one of `PASS`, `FAIL`, or `SKIP`. The harness collects results, renders a `rich.table.Table`, and exits 0 iff no criterion is `FAIL`.
- **run.sh / run.ps1 subcommand dispatch**: Simple `case`/`switch` dispatch; each subcommand is a standalone function. No external process manager (systemd, PM2) required for the MVP demo — background processes are tracked via PID files written to `.run/`.
- **Windows UTF-8**: `run.ps1` sets `$OutputEncoding = [System.Text.Encoding]::UTF8` and calls `chcp 65001` before any output so Arabic titles and the SAR symbol render correctly.

## Phase 1 — Design Artifacts

- All documentation prose is drafted from the actual F001–F007 implementations; no speculative features described.
- `docs/TECHNICAL.md` module layout table is generated from the F001 plan.md project structure section, then extended with the later slices' additions.
- The 60-second demo script in `docs/GUIDE.md` follows the exact agent interaction example from `docs/proposal.md §4`, updated with real seat IDs and prices from the seed data.
- The evaluation harness criterion list is derived directly from Requirements §11, section by section, in order.

## Complexity Tracking

No constitution violations — table intentionally empty.
