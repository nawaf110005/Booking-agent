# Booking-Agent ("Tazkara") — Capstone Submission · Group 12

A chat-first AI concierge that books live-event tickets in Saudi Arabia in **one
conversation**: search → member discount → seat map → atomic 10-minute hold →
**confirm before pay** → signed QR ticket.

**Team:** Nawaf Almufarej (lead) · Dana · Hessa · Refal — Agentic AI Bootcamp Capstone.

## What's in this folder

| Folder | Contents |
| --- | --- |
| [`01_proposal/`](01_proposal/) | The original project proposal (PDF) — what we planned to build. |
| [`02_code/`](02_code/) | The full, runnable project: `01_data/` (seeded catalog + CSVs), `02_src/` (source — run from here), `03_assets/` (generated visuals), `requirements.txt`, and `README.md` with setup/run steps. |
| [`03_project_report/`](03_project_report/) | The final report (PDF, 3 pages): what we built, who for, how it works, AI components, what worked, what's incomplete, next steps. |
| [`04_presentation/`](04_presentation/) | The slide deck (`.pptx`) and the demo-video recording script. **The `.mp4` still needs to be recorded** (see the placeholder + script in that folder). |

## Quick start

```bash
cd 02_code/02_src
uv venv --python 3.11 && uv pip install -e ".[dev,api,ui,llm,fulfilment]"
uv run booking-agent init-db && uv run booking-agent seed
./run.sh full         # backend :8000 + Next.js :3000   (or ./run.sh web for :8000 only)
uv run pytest -q      # 159 tests, all passing
```

Full instructions, environment variables, and known issues: [`02_code/README.md`](02_code/README.md).

## Status at a glance

- ✅ End-to-end booking loop (both UIs + CLI), human-in-the-loop payment gate, exact
  integer-halala money, atomic seat holds, HMAC-signed QR tokens — **159 tests pass**.
- ◑ Live Moyasar webhook + PDF/email ticket delivery: partly wired (demo uses an
  offline gateway).
- 📋 Personalisation/sentiment (F006) and RAG venue-FAQ (F007): specified, not in the
  default flow yet.
