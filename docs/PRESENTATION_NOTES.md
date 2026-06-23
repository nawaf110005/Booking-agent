# Presentation Notes — Booking-Agent (Tazkara)

Talk track for the capstone. Each section is a pain point: what hurt, the struggle
to see it, how we fixed it, and the proof to show on screen. Full technical detail:
[`COURSE_GAP_ANALYSIS.md`](COURSE_GAP_ANALYSIS.md); change-by-change worklog:
[`IMPLEMENTATION_LOG.md`](IMPLEMENTATION_LOG.md).

## 30-second pitch

Tazkara turns "I want a ticket" into a paid, QR-ticketed booking in one chat —
member discount applied, seats held atomically for 10 minutes, and an explicit
confirm before any payment. The capstone's hard part isn't the booking; it's making
the *agent* trustworthy: tested, observable, and safe. This phase closed that gap.

## Headline numbers (before → after)

| Metric | Before | After |
|---|---|---|
| Tests | 83 | **161** (the AI / agent path is now tested, not mocked out) |
| AI / LLM path under test | **0%** (mocked out of every test) | specialists, eval set, Q&A, guardrails, tool loop |
| Agent architecture | hardcoded FSM only | **multi-agent orchestrator + role specialists** (FSM deleted) |
| Evaluation set | none | **14 labelled cases** + automated grader |
| Safety tests (HITL, cap, autonomy) | none | HITL-bypass + cap + "model can't pay" + loop-prevention |
| Observability | none | tool-call + state-transition log, PII-redacted |
| LLM provider wired | key-less fallback only | **nano-gpt / Gemini (gemini-2.5-flash-preview-04-17)** (graceful fallback kept) |

---

## Pain point 1 — "It's not an agent, it's a big `if` statement"

- **It was a fair hit — so we deleted the `if` statement.** The old default was a ~730-line
  state machine (`agent/policy.py`) where the LLM only extracted slots and hand-coded `if`
  branches did all the deciding and tool-calling. The model *parsed*; the code *acted*.
  That's a slot-filling dialog manager, not an agent. **We removed it entirely** — there is
  no FSM in the codebase anymore.
- **What replaced it — a real multi-agent system (Week 5).** `agent/orchestrator.py`
  coordinates a team of **role-based specialists** (`agent/specialists.py`):
  **catalog → membership → pricing → seating**. Each specialist is an LLM
  **Reason–Act–Observe loop** restricted to *only* its own tools (`agent/tool_specs.py`);
  the orchestrator routes the turn through them in booking order and **hands off** as each
  phase completes. The model picks the tools — our code just coordinates and presents.
- **It still can't spend your money.** Booking/payment is **no specialist's tool** — it's
  executed in code only after an explicit user "confirm" at the gate
  (`guardrails.can_issue_payment`, Constitution I). Each specialist has a loop cap
  (Week 5: loop prevention).
- **And it still runs with no key.** The specialists' "brain" — the injected
  `complete(messages, tools)` — is the real LLM when a key is set, else a **deterministic
  offline brain** (`agent/offline_brain.py`). So the demo and the **entire 161-test suite
  run offline**. The FSM's deterministic logic didn't vanish — it became a *model the agent
  calls*, not the agent itself. Same agents, swappable brain.
- **Proof to show (great live demo).** `python scripts/agent_smoke.py` books end-to-end
  offline and prints the trace — you can literally watch each specialist take its turn:
  ```
  tool  t1  search_events  {'agent': 'catalog', ...}
  tool  t1  lookup_member  {'agent': 'membership', 'args': '{"email": "n***@example.com"}'}
  tool  t1  quote_price    {'agent': 'pricing', ...}
  tool  t2  hold_seats     {'agent': 'seating', 'args': '{"seat_ids": ["G3","G4","G5","G6"]}'}
  move  t2  seat_selection -> awaiting_confirmation
  tool  t3  create_booking {...}        # ← in code, only after the user confirms
  ```
- **Talk-track line.** "We didn't just admit our agent was a state machine — we deleted the
  state machine and built a multi-agent team: an orchestrator that hands each turn to a
  catalog, membership, pricing, and seating specialist, each an LLM tool-loop. It still
  can't take payment, because that's kept in code behind a human confirm — and it still
  runs offline, because the specialists' brain is swappable."
- **If asked 'what runs by default?'** The multi-agent orchestrator — `booking_agent_mode`
  defaults to `"multi_agent"`. `tool_agent` (one agent, full tool set) is kept as an
  alternative for comparison.

## Pain point 2 — "Our tests never tested the AI"

- **The pain.** 80-plus passing tests gave false confidence: none of them ran the model.
- **The struggle.** One line in `tests/conftest.py` — an autouse `_force_heuristic`
  fixture — disabled the LLM in *every* test. The whole nano-gpt path (extraction, JSON
  parsing, the grounded-Q&A branch) had zero coverage. Finding that one fixture was the
  "aha".
- **The fix.** Six new test files that turn the model back on (with a stubbed provider,
  so it's fast and offline): slot-extraction parsing/coercion/failure handling, the
  grounded-Q&A LLM branch, and a reusable **evaluation set** with an accuracy scorer
  (Week 6 "Build / Evaluate an Evaluation Set").
- **Proof to show.** `pytest -q` → 161 passing; open `tests/test_agent/test_llm_*.py`.

## Pain point 3 — "We couldn't see what the agent did"

- **The pain.** When a booking misbehaved, there was no trace to debug — and our own
  constitution (Principle VII) *required* observable reasoning.
- **The struggle.** Logging had to capture tool calls and state moves **without leaking
  PII** (buyer emails) — a PDPL concern, and a graded item.
- **The fix.** `agent/observability.py`: every tool call and state transition is recorded
  as a structured event, emitted to logs and a ring buffer, with emails auto-redacted.
- **Proof to show (great live demo).** `python scripts/agent_smoke.py` prints the trace —
  each tool call is tagged with the specialist that made it:
  ```
  tool  t1  search_events  {'agent': 'catalog', ...}
  tool  t1  lookup_member  {'agent': 'membership', 'args': '{"email": "n***@example.com"}'}
  tool  t1  quote_price    {'agent': 'pricing', ...}
  tool  t2  hold_seats     {'agent': 'seating', 'args': '{"seat_ids": ["G3","G4","G5","G6"]}'}
  move  t2  seat_selection -> awaiting_confirmation
  move  t3  awaiting_confirmation -> payment
  ```

## Pain point 4 — "Where's the safety net?"

- **The pain.** The "never charge without confirmation" rule lived implicitly inside the
  state machine; nothing *proved* it and nothing tested an attempt to break it.
- **The fix.** `agent/guardrails.py` centralizes the rules (payment only at the
  confirmation gate, tier-cap enforcement) as pure, testable predicates — plus a test
  that a stray `confirm` from the model **cannot** jump the payment gate (Week 6 "Test
  Guardrails", Constitution I).
- **Talk-track line.** "We can point to the exact function that says 'no payment before
  confirmation,' and the test that tries to break it and fails."

## Pain point 5 — "It feels scripted"

- **The fix.** `agent/compose.py` adds opt-in dynamic phrasing: with a flag on, the
  model rewrites the reply *wording* while every number, seat code, and the structured
  payload stay identical — so it reads naturally without risking correctness. Off by
  default, so behavior and tests are unchanged until we choose to enable it.

## Pain point 6 — "We hadn't actually plugged in a model"

- **The fix.** Wired the agent to **nano-gpt / Gemini (`gemini-2.5-flash-preview-04-17`)**
  (`.env`, `.env.example`, `scripts/nanogpt_check.py` to confirm the exact model id + test
  the key). The keyless heuristic fallback is preserved, so the demo always runs offline.

---

## Live demo script

1. `pytest -q` → **161 passed** — proof it's tested, now *including* the agent path
   (specialists, tool loop, guardrails), not mocked out.
2. `python scripts/agent_smoke.py` → a full booking → ticket on the **offline brain**,
   printing the observable reasoning trace where every tool call is tagged with the
   specialist that made it (catalog → membership → pricing → seating), plus the state
   transitions, PII-redacted. Proof it's a real multi-agent system, observable, safe, and
   runs with **no key**.
3. **On the real LLM:** run the app with a provider key (default `multi_agent` mode), then
   book through the chat — the same orchestrator hands each turn to the specialists, but
   now the *model* picks each tool. The trace looks the same; the brain is just live.
4. `python scripts/eval_agent.py` → grades the live model on the eval set and prints
   accuracy (proof it's measurable). *(Needs a machine that can reach the provider.)*

## How this maps to the course (for Q&A)

- **Week 3** — build-your-first-tool-agent foundations, LLM evals, FastAPI/Streamlit.
- **Week 4** — tool systems, ReAct, tool dispatcher (`tool_specs.py`), autonomy guardrails
  — each specialist is a Reason–Act–Observe loop over a restricted tool set; observability
  tags every call with the agent that made it.
- **Week 5** — **multi-agent orchestration**: role-based specialists (`specialists.py`) +
  an orchestrator that routes and hands off between them (`orchestrator.py`), conversation
  memory (`state.py`) + long-term memory (`memory.py`), and per-specialist loop prevention.
- **Week 6** — agent evaluation, guardrails & safety, human-in-the-loop, observability —
  the payment gate stays in code, no specialist can take payment.

## If asked "what's next?"

An LLM-as-judge scorer for the free-text replies; a task-level eval that scores the whole
agent trajectory (did it call the right tools, never charge without confirm) rather than
just NLU; persisted sentiment per turn; and richer specialist hand-offs (e.g. a recommender
agent in the discovery phase).
