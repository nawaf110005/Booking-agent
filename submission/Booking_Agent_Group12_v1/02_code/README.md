# Booking-Agent ("Tazkara") — Setup & Run

A chat-first AI concierge for booking live-event tickets in Saudi Arabia. One
conversation carries a user through:

**search → identify member (by email) → quote (member discount + 15% VAT) →
seat map → atomic 10-minute hold → confirm (human-in-the-loop) → pay → signed QR ticket.**

> **Team (Group 12):** Nawaf Almufarej · Dana · Hessa · Refal — Agentic AI Bootcamp Capstone.

---

## 1. Project Summary

Booking-Agent is an agentic booking assistant: the user talks to it in natural
language (Arabic/English) and it drives the whole ticket purchase inside a single
chat thread. It runs in two modes:

- **`fsm` (default)** — a deterministic state machine over typed Python tools
  (the MVP that every test exercises).
- **`tool_agent`** — a genuinely agentic LLM Reason–Act–Observe loop where the
  model chooses tools, with a loop-prevention cap. Falls back to the FSM when no
  LLM key is configured.

In **both** modes the dangerous action (creating the booking / issuing payment)
is kept out of the model's reach and executed in code **only** after an explicit
user "confirm" — the non-negotiable human-in-the-loop gate.

Key properties:
- **Exact money** — all amounts are integer halalas (1 SAR = 100 halalas) and
  percentages are integer basis points; no float ever enters the arithmetic.
- **Atomic seat holds** — all-or-nothing with a 10-minute TTL; two bookings can
  never hold the same seat.
- **Tamper-evident tickets** — the QR encodes an HMAC-signed token, not a bare
  booking id.

### Folder layout (this `02_code/`)

```
02_code/
├── 01_data/        # Seeded SQLite DB + CSV exports of the demo catalog
├── 02_src/         # The full, runnable project (run everything from here)
├── 03_assets/      # Generated visuals (seat maps, sample QR ticket)
├── requirements.txt
└── README.md       # this file
```

The runnable project lives in **`02_src/`**. The code is a Python `src`-layout
package (`02_src/src/booking_agent/`) plus a Next.js frontend (`02_src/frontend/`).

---

## 2. Requirements

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (recommended) — or plain `pip`
- **Node 18+** (only for the Next.js storefront; the project also ships a
  no-Node static site served by the API)
- An **LLM API key** is *optional* — without one, the agent degrades gracefully
  to a deterministic rule-based path (and the entire test suite runs offline).

All Python dependencies are pinned in [`requirements.txt`](requirements.txt) and
declared in [`02_src/pyproject.toml`](02_src/pyproject.toml).

---

## 3. Installation

```bash
cd 02_src

# Recommended (uv): venv + install with the extras needed to run + test
uv venv --python 3.11
uv pip install -e ".[dev,api,ui,llm,fulfilment]"

# OR plain pip, using the pinned file at the 02_code root:
#   python -m venv .venv && source .venv/bin/activate
#   pip install -r ../requirements.txt && pip install -e .
```

Initialise and seed the database (idempotent):

```bash
uv run booking-agent init-db
uv run booking-agent seed
```

---

## 4. Run the Project

All commands run from **`02_src/`**.

```bash
# One-command demo: FastAPI backend (:8000) + Next.js frontend (:3000)
./run.sh full            # macOS/Linux
#  .\run.ps1 full        # Windows

# Backend only — serves the no-Node static storefront at http://localhost:8000
./run.sh web

# API standalone (interactive docs at http://localhost:8000/docs)
uv run uvicorn booking_agent.api.app:app --reload --reload-dir src
```

Then open the printed URL (Next.js: **http://localhost:3000**), click
**Book with AI**, and run the full loop: search → member discount → seat map →
10-minute hold → **confirm** → sandbox pay → QR ticket.

### CLI

```bash
uv run booking-agent search "Coldplay"
uv run booking-agent quote 1 gold 4 --email nawaf@example.com
uv run booking-agent sweep          # release expired seat holds
```

### Offline demo + tests (no network / no key)

```bash
python scripts/smoke_demo.py        # headless end-to-end loop
uv run pytest -q                    # full suite — 159 tests, all passing
```

> The `01_data/` exports and `03_assets/` visuals were generated from the
> project's own seed and renderers by `02_src/scripts/gen_submission_assets.py`.

---

## 5. API Keys & Environment Variables

Configuration is read from a `.env` file (see [`02_src/.env.example`](02_src/.env.example)).
**No real key ships in this submission** — copy the example and add your own if you
want the live-LLM path:

```bash
cd 02_src && cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./booking.db` | SQLAlchemy URL (Postgres works too) |
| `BOOKING_AGENT_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `nanogpt` |
| `BOOKING_AGENT_MODEL` | `claude-sonnet-4-6` | Model name |
| `BOOKING_AGENT_MODE` | `fsm` | `fsm` (deterministic) or `tool_agent` (agentic LLM loop) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `NANOGPT_API_KEY` | — | LLM key (**optional**; rule-based fallback if absent) |
| `HOLD_TTL_MINUTES` | `10` | Seat-hold lifetime |
| `VAT_RATE` | `0.15` | Saudi VAT |
| `PAYMENT_GATEWAY` | `fake` | `fake` (offline) or `moyasar` (sandbox) |
| `TICKET_HMAC_KEY` | `dev-insecure-change-me` | QR signing key |

`GET /v1/healthz` reports whether an LLM key is configured.

---

## 6. Known Issues / Limitations

- **Demo payment is a sandbox/fake gateway.** The live Moyasar webhook
  (signature verification + idempotency) is specified and partly wired but not
  fully integrated; the demo uses the offline `fake` gateway by default.
- **PDF ticket + email delivery** are scaffolded — the QR token signing and PNG
  rendering work (see `03_assets/ticket_qr_sample.png`), but ReportLab PDF
  layout and SMTP send are not yet completed.
- **Personalisation + sentiment (F006)** and **RAG venue-FAQ (F007)** are
  specified under `02_src/specs/` but not built into the default flow.
- **Sessions are in-memory** (`SESSION_STORE`) — conversational state is not
  persisted across a server restart.
- The agent's `tool_agent` mode requires an LLM key; with no key it
  automatically uses the deterministic FSM path.
- Seat-map PNGs use Pillow's built-in font, so a few display glyphs (e.g. the
  em-dash in the title) may render as boxes — cosmetic only.

> **All code is error-free and the full test suite (159 tests) passes** —
> verified with `uv run pytest -q`.
