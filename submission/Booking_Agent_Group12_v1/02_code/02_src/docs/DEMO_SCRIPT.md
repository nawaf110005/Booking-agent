# Live Demo Script — Booking Agent (Google Gemini)

A tight ~5-minute live demo for the 10-minute slot. Inputs are **exact** — type them
verbatim. Each step has a one-line "say this" so you can narrate while it runs.

---

## Pre-flight (do this 10 minutes before you present)

1. **Latest code + key**
   ```bash
   cd ~/Desktop/dev/Booking-agent
   git pull
   ```
   In `.env`: `BOOKING_AGENT_PROVIDER=google`, `BOOKING_AGENT_MODEL=gemini-2.5-flash`,
   and a **valid** `GOOGLE_API_KEY` (a real AI-Studio key starts with `AIza…`). Get one at
   https://aistudio.google.com/apikey if needed.
2. **Start it**
   ```bash
   bash run.sh web
   ```
   Open **http://localhost:8000**.
3. **Confirm AI mode is live:** open http://localhost:8000/v1/healthz — you want
   `"llm_configured": true` and `"model": "gemini-2.5-flash"`. Hard-refresh the page (Cmd+Shift+R).
4. **Have a second terminal open** for the optional observability trace (step 6).
5. **Safety net:** if Gemini hiccups on stage, the agent automatically falls back to the
   rule-based path and still books — the demo never hard-fails. (To force offline on
   purpose: blank `GOOGLE_API_KEY` and restart.)

> Rule of thumb: if the chat replies feel templated or you see a 401 in the terminal, the
> key is the problem — the booking still works, just less chatty.

---

## The demo (≈5 min)

### 1 · The landing page (30s)
- Scroll the page slowly. **Say:** "This is the pitch — no catalog dump. The idea: one
  conversation replaces a five-step checkout." Pause on **"By the numbers"** (60–80%
  abandonment, 1 conversation, 10-min holds, 100% confirm-before-pay).
- Click **"Book with AI 🎫"** to open the chat.

### 2 · Happy path — the core loop (90s)
Type:
```
4 Gold tickets for Coldplay in Riyadh, nawaf@example.com
```
- **Say:** "One sentence. It found the event, recognised me from my email as a Platinum
  member, applied 15% off, and priced it exactly — 3,128 SAR including 15% VAT." Point at
  the itemised quote + the seat map.

Type the seats:
```
G3, G4, G5, G6
```
- **Say:** "It placed an **atomic** 10-minute hold — all four seats or none — and now it
  **stops and asks me to confirm**. It will not charge until I say so." Point at the
  countdown + the confirmation card.

Type:
```
confirm
```
- **Say:** "Now — and only now — it issues payment, and I get a signed QR ticket." Show the
  payment → ticket.

### 3 · Edge case: an event we don't have (30s)
Type:
```
I need a ticket for JB
```
- **Say:** "We don't carry JB. Instead of ignoring me or hallucinating a fake show, it says
  it couldn't find it and shows what *is* on. This was a real bug I found and fixed."

### 4 · Guardrail: off-topic (20s)
Type:
```
write me code
```
- **Say:** "It declines clearly — 'I'm a ticket concierge' — and steers back. The model
  can't be talked into doing something off-task or inventing a catalog."

### 5 · Conversational + RAG, mid-flow (30s)
Type a venue question (the booking state is preserved):
```
is there parking at the venue?
```
- **Say:** "I can ask anything at any step. That answer is **grounded** in a small venue/FAQ
  retriever — RAG — not made up. And it didn't lose my place in the booking."

### 6 · (Optional, +30s) Show the reasoning trace
In the second terminal:
```bash
python scripts/agent_smoke.py
```
- **Say:** "Every tool call and state transition is logged — with the email **redacted**.
  This is what makes the agent debuggable and auditable." Point at `lookup_member email=n***`,
  `place_seat_hold`, and the `awaiting_confirmation → payment` move.

### 7 · (Optional, mention only) The agentic mode
- **Say:** "Today's default is a deterministic state machine for safety. Flip one env var —
  `BOOKING_AGENT_MODE=tool_agent` — and the **model** drives the tools in a ReAct loop, with
  the same payment gate enforced in code."

---

## If something breaks
- **Gemini 401 / slow:** keep going — it falls back to rule-based and still books. Say
  "running on the offline fallback now" and continue.
- **Port busy:** `bash run.sh web` again, or open the URL it prints (`:8001`).
- **Browser cached old page:** hard-refresh (Cmd+Shift+R).
- **Worst case:** `python scripts/agent_smoke.py` runs the whole booking in the terminal with
  zero network — a guaranteed end-to-end demo.

## One-line close
"From 'I want a ticket' to a QR ticket, in one conversation — and it can't spend your money."
