# Demo Video — Recording Script

> **Action required:** record a screen capture of the running app and export it as
> **`Booking_Agent_Group12_DemoVideo_v1.mp4`** into this folder, then delete the
> `*.PLACEHOLDER.txt` file. (A video can't be generated from code — it has to be
> recorded.) Target length **≈3–5 minutes**.

## Record with
- **macOS:** QuickTime Player → File → New Screen Recording (or `Cmd+Shift+5`).
- Export as **.mp4** (if QuickTime saves `.mov`, re-export or convert with
  `ffmpeg -i in.mov Booking_Agent_Group12_DemoVideo_v1.mp4`).

## Pre-flight (do once before recording)
```bash
cd <project>/02_code/02_src
uv venv --python 3.11 && uv pip install -e ".[dev,api,ui,llm,fulfilment]"
uv run booking-agent init-db && uv run booking-agent seed
./run.sh web            # serves the storefront at http://localhost:8000
```
- Optional live-LLM "AI mode": put any valid key in `.env`
  (`BOOKING_AGENT_PROVIDER` + matching key). Confirm at
  `http://localhost:8000/v1/healthz` → `"llm_configured": true`.
- **Safety net:** with no key the agent falls back to the deterministic rule-based
  path and still books end to end — the demo never hard-fails.

## The walkthrough (type the inputs **verbatim**)

1. **Landing (30s)** — scroll the page; pause on "By the numbers" (60–80%
   abandonment, 1 conversation, 10-min holds, 100% confirm-before-pay). Click
   **Book with AI**.
2. **Happy path (90s)** — type:
   `4 Gold tickets for Coldplay in Riyadh, nawaf@example.com`
   Narrate: it found the event, recognised the Platinum member, applied 15% off,
   priced exactly with 15% VAT. Then pick seats: `G3, G4, G5, G6` — point at the
   **atomic 10-minute hold** and the **confirm** card.
3. **Confirm → pay → ticket** — type `confirm`. Show payment → **signed QR ticket**.
   Stress: *no payment link is issued until you confirm.*
4. **Unknown event (30s)** — `I need a ticket for JB` — it says it can't find it and
   shows what *is* on, instead of hallucinating.
5. **Off-topic guardrail (20s)** — `write me code` — it declines and steers back.
6. **RAG mid-flow (30s)** — `is there parking at the venue?` — grounded answer, and
   it keeps your place in the booking.
7. **(Optional) reasoning trace** — run the offline smoke demo in a second terminal
   to show logged, email-redacted tool calls and the `awaiting_confirmation →
   payment` transition.

## One-line close
"From 'I want a ticket' to a QR ticket, in one conversation — and it can't spend
your money."

---
*Adapted from `02_code/02_src/docs/DEMO_SCRIPT.md`. The deck mentions Google
Gemini; the repository's active provider is set in `.env` — any configured
provider works, and the offline fallback guarantees the demo completes.*
