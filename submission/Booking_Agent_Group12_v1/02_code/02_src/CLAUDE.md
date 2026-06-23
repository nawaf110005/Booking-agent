# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Booking-Agent ("Tazkara") is a chat-first AI concierge for booking live-event
tickets in Saudi Arabia. One conversation carries a user through:
**search → identify member (by email) → quote (with member discount + 15% VAT) →
seat map → atomic 10-min hold → HITL confirmation → payment → signed QR ticket.**

Python 3.11 backend (FastAPI + SQLAlchemy 2 + Typer CLI), Next.js 14 frontend,
SQLite by default (Postgres-compatible). Built with [spec-kit](https://github.com/github/spec-kit);
features are sliced F001–F008 under `specs/`.

## Commands

Tooling is [`uv`](https://github.com/astral-sh/uv). The `run.sh` (macOS/Linux) and
`run.ps1` (Windows) launchers wrap the common flows.

```bash
./run.sh setup          # uv venv + install .[dev,api,ui,llm] + init-db + seed
./run.sh full           # backend :8000 + Next.js :3000 (recommended demo)
./run.sh web            # backend only; serves the static site at :8000
./run.sh test           # pytest -q
./run.sh fresh          # wipe booking.db and re-seed (resets sold seats)

# Direct equivalents
uv run pytest                                   # full suite (~139 tests)
uv run pytest tests/test_agent/test_policy_flow.py            # one file
uv run pytest tests/test_tools/test_holds.py::test_name -q    # one test
uv run pytest --cov                             # coverage (fail_under = 85)
uv run ruff check src tests                     # lint
uv run mypy src                                 # type check (non-strict)
uv run alembic -c migrations/alembic.ini upgrade head         # migrations

# CLI (entry point: booking_agent.cli:app)
uv run booking-agent init-db          # create tables (idempotent)
uv run booking-agent seed             # load deterministic demo catalog
uv run booking-agent search "Coldplay"
uv run booking-agent quote 1 gold 4 --email nawaf@example.com
uv run booking-agent sweep            # release expired seat holds

# Offline demo + live-model eval
python scripts/smoke_demo.py          # headless end-to-end loop, no network/key
python scripts/eval_agent.py          # grades the live LLM on the eval set (needs a key)

# Frontend (frontend/)
cd frontend && npm install && npm run dev   # Next.js :3000
npm run type-check                          # tsc --noEmit
```

The API factory is `booking_agent.api.app:app`; run it standalone with
`uv run uvicorn booking_agent.api.app:app --reload --reload-dir src`. Interactive
API docs at `http://localhost:8000/docs`.

## Architecture

### The agent turn pipeline
Every chat turn enters through `agent/__init__.py:handle(db, state, message)`,
which dispatches on `settings.booking_agent_mode`:

- **`fsm` (default)** — `agent/policy.py:respond()` is a deterministic state
  machine over the F001 tools. It extracts slots, advances as far as the message
  allows, and asks for the first missing slot (event → email → category →
  quantity → seats → confirm). This is the MVP and what every test exercises.
- **`tool_agent`** — `agent/tool_agent.py:respond_with_tools()` is the genuinely
  agentic path: an LLM Reason–Act–Observe loop where the model chooses tools
  (`agent/tool_specs.py:dispatch`) with a `MAX_STEPS` loop-prevention cap.
  Falls back to the FSM if no provider key is configured.

In **both** modes the dangerous action (creating the booking / issuing payment)
is kept out of the model's reach and executed in code **only** after an explicit
user "confirm" from the `AWAITING_CONFIRMATION` step — the non-negotiable
human-in-the-loop gate (`agent/guardrails.py:can_issue_payment`).

`ConversationState` (`agent/state.py`) is per-session short-term memory; steps
are the string constants in that module. Sessions live in an in-memory
`SESSION_STORE` (`agent/store.py`) — not persisted across process restarts.

### NLU: LLM with deterministic fallback
`agent/llm.py:llm_extract()` calls the configured provider for slot extraction;
`agent/extract.py:heuristic_extract()` is a pure rule-based fallback. The policy
merges both but lets the heuristic's strong intents (ask/cancel/confirm) win.
Other LLM-touched concerns are isolated modules: `compose.py` (reply rephrasing),
`answer.py` (Q&A / chit-chat), `sentiment.py`, `interests.py`, `rag.py`,
`judge.py`. `graph.py` is a dependency-free LangGraph-shaped shim reserved for
the multi-agent stretch.

### Money is always exact (Constitution IV)
All amounts are **integer halalas** (1 SAR = 100 halalas); percentages are
integer **basis points** (1500 = 15%). No float ever enters the arithmetic —
`tools/money.py` does half-up integer math, `to_sar`/`sar_str` are display-only.
Member tier → discount bps and ticket cap are defined once in `db/enums.py`
(`TIER_DISCOUNT_BPS`, `TIER_CAP`, `discount_bps_for`, `cap_for`).

### Atomic seat holds (Constitution II)
`tools/holds.py:place_seat_hold()` is all-or-nothing with a 10-minute TTL: if any
requested seat is unavailable it raises `SeatUnavailableError` and holds nothing.
`release_expired_holds()` is the sweeper (also the `booking-agent sweep` CLI).

### Tools layer (`tools/`)
Plain typed Python functions the agent calls — `events`, `members`, `pricing`,
`seatmap` (Pillow-rendered PNG), `holds`, `booking`, `payments`, plus `money`,
`schemas`, `errors`. No external ticketing SaaS (Constitution III). Tool errors
are a typed hierarchy in `tools/errors.py` (`NotFoundError`, `SeatUnavailableError`,
`CapExceededError`, `ValidationToolError` ⊂ `ToolError`).

### API (`api/`)
`api/app.py:create_app()` mounts `/v1` routers (`health`, `chat`, `events`,
`quote`, `holds`, `pay`) and maps the tool-error hierarchy to HTTP codes
(404/409/422/400). The Next.js storefront (`frontend/`, primary) and a no-Node
static site (`web/static`, served at `/`) both consume the same `/v1` API; the
chat endpoint returns the `AgentResponse` shape from `agent/responses.py`.

### Persistence (`db/`)
SQLAlchemy 2 models in `db/models.py` (13 tables: events/venues/seats/members/
bookings/booking_items/holds/payments/tickets/audit_log/user_preferences/
interaction_log). `db/seed.py` loads a deterministic Saudi catalog. Alembic
migration `migrations/versions/0001_initial.py` builds the full schema;
`init-db`/the API lifespan use `create_all` for convenience.

## Conventions & gotchas

- **Config**: `config.py:Settings` (pydantic-settings) reads `.env` once at
  import; downstream code imports the `settings` singleton. Tests override by
  constructing `Settings(...)` and patching the binding.
- **Tests run fully offline.** `tests/conftest.py` has an autouse fixture that
  forces `llm_available()` to `False` everywhere, so the suite exercises the
  deterministic heuristic path regardless of keys in `.env`. Use the `seeded` /
  `coldplay_riyadh_id` fixtures (in-memory SQLite via `StaticPool`).
- **Test-first for data/money** (Constitution VI): money and seat-hold tools have
  tests before any agent wiring; TTL/expiry tests use `freezegun`.
- **LLM provider** is set by `BOOKING_AGENT_PROVIDER` (`anthropic` | `openai` |
  `nanogpt`, the OpenAI-compatible proxy currently active) + the matching key.
  `settings.llm_configured` / `GET /v1/healthz` report whether a key is present;
  with none, everything degrades to the rule-based fallback. Keep any single LLM
  call bounded by `llm_timeout_seconds` so a slow provider fails fast.
- **Ruff** line-length is 100 but `E501` is ignored; non-ASCII display glyphs
  (×, —, arrows, Arabic) are intentional and the relevant RUF rules are disabled.
- **Constitution** (`.specify/memory/constitution.md`) defines 8 governing
  principles; the non-negotiables (I: confirm before payment, II: atomic holds)
  are enforced in code via `agent/guardrails.py` and `tools/holds.py`. Don't
  weaken those gates.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
