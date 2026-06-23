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
| Tests | 83 | **115** (+32, 8 new test files) |
| AI / LLM path under test | **0%** (mocked out of every test) | extractor, eval set, Q&A, guardrails, tool loop |
| Agent architecture | hardcoded FSM only | FSM **+ opt-in LLM tool-calling mode** |
| Evaluation set | none | **14 labelled cases** + automated grader |
| Safety tests (HITL, cap, autonomy) | none | HITL-bypass + cap + "model can't pay" + loop-prevention |
| Observability | none | tool-call + state-transition log, PII-redacted |
| LLM provider wired | key-less fallback only | **nano-gpt / Llama** (graceful fallback kept) |

---

## Pain point 1 — "It's not an agent, it's a big `if` statement"

- **The pain.** The chat worked, but it felt rigid and scripted. Every path was
  hand-coded; the model wasn't really "deciding" anything.
- **The struggle / what we found.** The LLM was boxed in: its only job was to read a
  message and emit a fixed JSON of slots (`agent/llm.py`). All the deciding and all the
  tool calls happen in a ~500-line state machine (`agent/policy.py`). So the model
  *parses*; our code *acts*. That's a classic slot-filling dialog system, not a
  tool-calling agent — exactly the difference the course draws in Week 4 (ReAct, tool
  dispatchers).
- **The fix — we built a real tool-calling agent mode.** `agent/tool_specs.py` exposes
  our F001 tools as model-callable function schemas; `agent/tool_agent.py` runs a
  Reason–Act–Observe loop where the **model** chooses the tool each step and we execute
  it. Two safety properties make it demo-safe: the payment/booking step is **not** a
  tool (the model literally cannot trigger a charge — it's handled in code only after an
  explicit "confirm"), and a step cap prevents infinite loops. It's opt-in
  (`BOOKING_AGENT_MODE=tool_agent`); the deterministic FSM stays the default so the MVP
  can't regress. Eight offline tests cover the loop, the autonomy guardrail, and loop
  prevention.
- **Talk-track line.** "We didn't just admit our agent was a state machine — we built
  the agentic version: the model drives the tools in a ReAct loop, but it still can't
  spend your money, because we kept payment out of its hands and behind a human confirm."

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
- **Proof to show.** `pytest -q` → 107 passing; open `tests/test_agent/test_llm_*.py`.

## Pain point 3 — "We couldn't see what the agent did"

- **The pain.** When a booking misbehaved, there was no trace to debug — and our own
  constitution (Principle VII) *required* observable reasoning.
- **The struggle.** Logging had to capture tool calls and state moves **without leaking
  PII** (buyer emails) — a PDPL concern, and a graded item.
- **The fix.** `agent/observability.py`: every tool call and state transition is recorded
  as a structured event, emitted to logs and a ring buffer, with emails auto-redacted.
- **Proof to show (great live demo).** `python scripts/agent_smoke.py` prints the trace:
  ```
  tool  t1  lookup_member  {'email': 'n***@example.com', 'tier': 'platinum', ...}
  tool  t2  place_seat_hold {'seats': ['G3','G4','G5','G6']}
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

- **The fix.** Wired the agent to **nano-gpt / Llama** (`.env`, `.env.example`,
  `scripts/nanogpt_check.py` to confirm the exact model id + test the key). The keyless
  heuristic fallback is preserved, so the demo always runs offline.

---

## Live demo script (3 commands)

1. `pytest -q` → **115 passed** (proof it's tested).
2. `python scripts/agent_smoke.py` → a full booking → ticket **and** the observable
   reasoning trace (proof it's observable + safe).
3. `python scripts/eval_agent.py` → grades the live Llama model on the eval set and
   prints accuracy (proof it's measurable). *(Run on a machine that can reach
   nano-gpt.com.)*
4. Optional: set `BOOKING_AGENT_MODE=tool_agent` to show the model driving the tools in
   a ReAct loop — same booking, but the LLM picks each step.

## How this maps to the course (for Q&A)

- **Week 3** — built-your-first-tool-agent foundations, LLM evals, FastAPI/Streamlit.
- **Week 4** — tool systems, ReAct, tool dispatcher, autonomy guardrails — the new
  tool-calling mode, plus the observability we shipped.
- **Week 5** — loop prevention (the step cap in the tool loop).
- **Week 6** — agent evaluation, guardrails & safety, human-in-the-loop — the core of
  this phase.

## If asked "what's next?"

Promote the tool-agent from opt-in to default once it's graded against the live model;
an LLM-as-judge scorer for the free-text replies; persisted sentiment per turn; and the
RAG venue/FAQ feature — all scoped in the gap analysis.
