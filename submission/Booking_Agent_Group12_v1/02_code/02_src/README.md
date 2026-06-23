# Booking-Agent

> An AI concierge for live events in Saudi Arabia. Ask in chat, get your member
> discount applied automatically, pick a seat from a live map, hold it for 10
> minutes, **confirm before you pay**, and receive a signed PDF/QR ticket in
> your inbox — all in one conversation.

Capstone for the **Agentic AI Bootcamp**. Demonstrates tool-calling agents,
human-in-the-loop approval, atomic reservations under concurrency, payment
webhooks with idempotency, tamper-evident tickets, RAG, and per-user
personalisation + sentiment adaptation.

| | |
| --- | --- |
| **Stack** | Python 3.11 · FastAPI · SQLAlchemy 2 · **Next.js 14 + Tailwind** · Pillow · Moyasar (sandbox) |
| **LLM providers** | Nano-GPT (active) · Anthropic · OpenAI — rule-based fallback when no key |
| **Status** | **Built & live:** F001 tools · F002 LLM chat agent · **Next.js storefront** · sandbox payment + HMAC-QR tickets. **Specified:** real Moyasar webhook, personalisation, RAG. |
| **License** | MIT |

---

## What it does

The core loop, end to end, in one chat:

**Listen → Identify event → Quote (with member discount) → Select seats → Hold (10-min timer) → Confirm (HITL) → Pay → Deliver ticket.**

- 🔎 **Event search & disambiguation** from natural language ("Coldplay in Riyadh").
- 🪪 **Email-based membership** → tier discount + ticket cap applied automatically.
- 💸 **Exact quotes** — base, member discount, VAT 15%, total — computed in integer
  halalas so the math is reproducible to the halala.
- 🪑 **Visual seat selection** — a generated seat-map image (green=available,
  amber=held, grey=sold).
- ⏱️ **Atomic, 10-minute seat holds** — all-or-nothing; no two bookings can hold
  the same seat.
- ✅ **Confirmation before payment** — the agent shows the full summary and waits
  for explicit approval before issuing a payment link. *Non-negotiable
  [Constitution](.specify/memory/constitution.md) Principle I.*
- 💳 **Moyasar sandbox payment** + signature-verified, idempotent webhook *(F003)*.
- 🎫 **HMAC-signed QR PDF tickets** + email delivery *(F003)*.
- 🧠 **Preference learning + sentiment adaptation** *(F006)* — the WeBook-gap
  differentiators.

> **Implemented now (F001):** the schema, the seeded Saudi catalog, and the
> pre-payment tools (search, member lookup, pricing/quote, seat map, atomic
> holds), plus a FastAPI surface, a Streamlit chat UI, a CLI, and a full test
> suite. The conversational LLM agent is **F002**; payment + ticketing is
> **F003**. See the [feature map](#feature-map).

---

## Quickstart

Requires Python 3.11+, [`uv`](https://github.com/astral-sh/uv), and Node 18+ (for the Next.js UI).

### Recommended — one command (backend + Next.js frontend)

```powershell
.\run.ps1 full      # installs deps, seeds the DB, starts FastAPI :8000 + Next.js
```

Open the URL Next.js prints — **http://localhost:3000** (or **:3001** if 3000 is busy).
Click **Book with AI 🎫** (or any event's **Book**) and the agent runs search → member
discount → seat map → 10-min hold → **confirm** → sandbox pay → QR ticket.

> Two frontends ship: the **Next.js** app (`frontend/`, primary) and a **no-Node static
> site** served by the API at `http://localhost:8000` (`.\run.ps1 web`). Both use the same
> `/v1` API; `http://localhost:8000/docs` is the API reference.

### Manual

```powershell
uv venv --python 3.11
uv pip install -e ".[dev,api,ui,llm]"
uv run booking-agent init-db; uv run booking-agent seed
uv run pytest                                                # 69 tests
uv run uvicorn booking_agent.api.app:app --reload --reload-dir src   # API :8000
cd frontend; npm install; npm run dev                        # Next.js :3000
```

### LLM (active)

The agent is wired to **Nano-GPT** (`.env`: `BOOKING_AGENT_PROVIDER=nanogpt`,
`BOOKING_AGENT_MODEL=gpt-4o-mini`, `NANOGPT_API_KEY=…`) and uses it for natural-language
understanding, with a rule-based fallback if the LLM/network is unavailable. Switch to
`anthropic` or `openai` by changing the provider + key. `GET /v1/healthz` reports
`llm_configured`; the chat header shows **AI mode** when active.

> **Windows console:** set `$env:PYTHONUTF8 = "1"` if you see `UnicodeEncodeError`.

> **Windows console:** set `$env:PYTHONUTF8 = "1"` if you see `UnicodeEncodeError`.
> The CLI and demo set UTF-8 output automatically.

### CLI

```powershell
uv run booking-agent search "Coldplay"
uv run booking-agent quote 1 gold 4 --email nawaf@example.com
uv run booking-agent sweep         # release expired holds
```

---

## Architecture

```
   Chat UI (Streamlit)  ──►  FastAPI (/v1)
                                  │
                    Agent loop (LangChain) — F002
                                  │
   ┌──────────┬───────────┬──────────────┬───────────────┐
 Events     Pricing     Seat-map        Holds          Members
 tools      (quote)     renderer     (atomic+TTL)      lookup        ← F001 (built)
   └──────────┴───────────┴──────────────┴───────────────┘
                                  │
            Payments (Moyasar) + Fulfilment (PDF/QR/email)  — F003
                                  │
                    SQLite / PostgreSQL (SQLAlchemy 2)
        events · venues · seats · members · bookings · booking_items
        holds · payments · tickets · audit_log · user_preferences · interaction_log
                                  │
              Hold sweeper · RAG (venue FAQ, F007) · Personalisation+Sentiment (F006)
```

Money is integer halalas; the member discount and ticket cap are derived from
the member tier; seat holds are atomic with a 10-minute TTL. Each principle is
enforced in code and graded — see the [Spec-Driven Development](#spec-driven-development) table.

---

## Configuration

`Settings` in [`src/booking_agent/config.py`](src/booking_agent/config.py) reads `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./booking.db` | SQLAlchemy URL (Postgres works too) |
| `BOOKING_AGENT_PROVIDER` | `anthropic` | `anthropic` or `openai` (F002) |
| `BOOKING_AGENT_MODEL` | `claude-sonnet-4-6` | Model name |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | LLM key (optional; heuristic fallback) |
| `HOLD_TTL_MINUTES` | `10` | Seat-hold lifetime |
| `VAT_RATE` | `0.15` | Saudi VAT |
| `CURRENCY` | `SAR` | Display currency |
| `PAYMENT_GATEWAY` | `fake` | `fake` (offline) or `moyasar` (F003) |
| `MOYASAR_SECRET_KEY` / `MOYASAR_WEBHOOK_SECRET` | — | Moyasar sandbox (F003) |
| `TICKET_HMAC_KEY` | `dev-insecure-change-me` | QR signing key (F003) |
| `BOOKING_AGENT_ADMIN_TOKEN` | unset → admin disabled | Admin endpoints |

---

## Feature map

| Slice | What it adds | Spec | Status |
| --- | --- | --- | --- |
| **F001** | Schema, seeded catalog, core tools (search, member, quote, seat map, atomic holds), API, CLI, Streamlit UI, tests | [001-foundation-db-tools](specs/001-foundation-db-tools/spec.md) | ✅ Implemented |
| F002 | Agent: intent → extract → quote → seat → hold → **confirm** → respond; LLM + rule-based fallback | [002-agent-core](specs/002-agent-core/spec.md) | ✅ Implemented |
| F003 | Sandbox payment + HMAC-QR ticket built; real Moyasar webhook + PDF/email pending | [003-payment-fulfilment](specs/003-payment-fulfilment/spec.md) | ◑ Partial |
| F004 | FastAPI: sessions, chat, events, quote, holds, pay, ticket QR (admin/webhook pending) | [004-api](specs/004-api/spec.md) | ◑ Partial |
| **Web (Next.js)** | WeBook-style storefront + in-chat booking, primary UI (`frontend/`, :3000) | — | ✅ Implemented |
| **Web (static)** | No-Node fallback served by the API (`src/booking_agent/web/`, :8000) | — | ✅ Implemented |
| F005 | Streamlit chat with inline event/quote/seat/ticket cards | [005-streamlit-ui](specs/005-streamlit-ui/spec.md) | 📋 Specified |
| F006 | Preference learning + per-turn sentiment adaptation | [006-personalisation-sentiment](specs/006-personalisation-sentiment/spec.md) | 📋 Specified |
| F007 | RAG over venue FAQ / policy (BM25 default, Chroma optional) | [007-rag-venue-faq](specs/007-rag-venue-faq/spec.md) | 📋 Specified |
| F008 | Demo seed, docs, run scripts, evaluation harness | [008-demo-docs](specs/008-demo-docs/spec.md) | 📋 Specified |

---

## Project layout

```
src/booking_agent/
├── config.py              # Pydantic Settings
├── cli.py                 # booking-agent init-db|seed|search|quote|sweep
├── db/                    # SQLAlchemy base + 13 models + enums + seed
├── tools/                 # typed Python tools the agent calls
│   ├── events.py members.py pricing.py seatmap.py holds.py
│   ├── money.py           # exact minor-unit math (halalas, VAT)
│   └── schemas.py errors.py
├── api/                   # FastAPI factory + routers (health, events, quote, holds)
└── ui/                    # Streamlit chat (drives the core loop in-process)

migrations/                # Alembic (0001 builds the full schema)
specs/                     # spec-kit feature specs (spec/plan/tasks per slice)
docs/proposal.md           # business case + market research
.specify/memory/constitution.md   # the 8 governing principles
scripts/smoke_demo.py      # offline headless demo
Requirments.md             # full bootcamp-style requirements
```

---

## Spec-Driven Development

Built with [spec-kit](https://github.com/github/spec-kit). Every feature has a
`spec.md`, `plan.md`, and `tasks.md` under [`specs/`](specs/). The eight
principles in [`.specify/memory/constitution.md`](.specify/memory/constitution.md):

| Principle | Where it lives (F001) | How it's enforced |
| --- | --- | --- |
| **I. Confirmation Before Payment** *(non-negotiable)* | `ui/app.py` confirm gate; F002 policy | No payment link without explicit approval |
| **II. Atomic, Time-Bounded Holds** *(non-negotiable)* | [`tools/holds.py`](src/booking_agent/tools/holds.py) | All-or-nothing + 10-min TTL; tested in [`test_holds.py`](tests/test_tools/test_holds.py) |
| **III. Tools Are Python Functions** | [`tools/`](src/booking_agent/tools/) | No external ticketing SaaS; Moyasar isolated |
| **IV. Exact, Auditable Money** | [`tools/money.py`](src/booking_agent/tools/money.py) + [`pricing.py`](src/booking_agent/tools/pricing.py) | Integer halalas; tested to the halala in [`test_pricing.py`](tests/test_tools/test_pricing.py) |
| **V. Tamper-Evident Tickets** | `payments`/`tickets` schema; F003 | HMAC QR + idempotent webhook |
| **VI. Test-First for Data/Money** | [`tests/`](tests/) | Money + seat tools tested before agent wiring |
| **VII. Observable Reasoning** | `audit_log` + `interaction_log` | Every seat/booking transition logged |
| **VIII. MVP First, Multi-Agent Later** | single-agent loop | LangGraph reserved for the stretch |

Workflow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

---

## Testing

```powershell
uv run pytest                 # full suite
uv run pytest --cov           # coverage (gate 85%)
uv run ruff check src tests   # lint
uv run alembic -c migrations\alembic.ini upgrade head   # apply migrations
```

---

## Team

Nawaf Almufarej (lead) · Dana · Hessa · Refal — Agentic AI Bootcamp Capstone 2026.

## License

MIT — see [LICENSE](LICENSE).
