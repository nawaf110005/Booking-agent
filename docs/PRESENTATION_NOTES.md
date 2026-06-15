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
| Tests | 83 | **107** (+24, 6 new test files) |
| AI / LLM path under test | **0%** (mocked out of every test) | extractor, eval set, Q&A, guardrails |
| Evaluation set | none | **14 labelled cases** + automated grader |
| Safety tests (HITL, cap) | none | HITL-bypass + cap + guardrail unit tests |
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
- **The fix (this phase) + the honest roadmap.** We kept the state machine as the
  safety rail (it's what guarantees we never double-charge or skip confirmation) and
  hardened everything around it. The genuine "make the model drive the tools" refactor
  (ReAct loop + tool schemas) is scoped and deferred — documented as Tier 2 in the gap
  analysis so we ship trust first, dynamism next.
- **Talk-track line.** "We were honest that our agent was deterministic. So we made the
  deterministic core *provably* safe and observable — and mapped the path to a real
  tool-calling agent rather than hand-waving it."

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

1. `pytest -q` → **107 passed** (proof it's tested).
2. `python scripts/agent_smoke.py` → a full booking → ticket **and** the observable
   reasoning trace (proof it's observable + safe).
3. `python scripts/eval_agent.py` → grades the live Llama model on the eval set and
   prints accuracy (proof it's measurable). *(Run on a machine that can reach
   nano-gpt.com.)*

## How this maps to the course (for Q&A)

- **Week 3** — built-your-first-tool-agent foundations, LLM evals, FastAPI/Streamlit.
- **Week 4** — tool systems, ReAct, debugging/observability (the deferred dynamism +
  the observability we shipped).
- **Week 6** — agent evaluation, guardrails & safety, human-in-the-loop — the core of
  this phase.

## If asked "what's next?"

The tool-calling/ReAct refactor (let the model choose tools, FSM stays as guardrail),
an LLM-as-judge scorer for the free-text replies, persisted sentiment per turn, and the
RAG venue/FAQ feature — all scoped in the gap analysis.
