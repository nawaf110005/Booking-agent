# Booking-Agent vs. the Agentic AI Bootcamp — Gap Analysis

*What you've covered, what's missing, and what to add — focused on your two concerns:
testing/best-practice, and the agent feeling like a hardcoded `if`-statement.*

Generated 2026-06-15. Course read live from
`sda.weclouddata.com` (Agentic AI Bootcamp – May 2026). Code read from this repo.

---

## TL;DR

Your capstone is **well-built as software** — clean tools, exact money math, atomic
holds, a real HITL payment gate, 95 passing tests. But measured against the *agentic*
parts of the course it has two real gaps, and you diagnosed both correctly:

1. **It isn't really "an agent" yet — it's a slot-filling state machine with an LLM
   bolted on for parsing.** The LLM never decides anything or calls a tool. Your
   `policy.py` does, through ~500 lines of hand-written branching. That's the
   "if-statement / not dynamic" feeling. The course's Week 3–4 (tool agents, ReAct,
   tool dispatchers) is exactly the pattern you're missing — and you're at **0%** there.

2. **Your tests never exercised the LLM at all.** A single fixture
   (`conftest._force_heuristic`) disabled the model in *every* test, so the whole
   nano-gpt path was untested, and there was no evaluation set, no guardrail tests, and
   no observability. The course's Week 6 (Agent Evaluation, Guardrails & Safety) covers
   this — also at **0%**.

This session already (a) wired nano-gpt/Llama into the project and (b) closed the most
important slice of gap #2 with 12 new LLM-path tests, including an offline eval harness
and a human-in-the-loop guardrail test. The rest is laid out below as a ranked plan.

---

## Where you are in the course

Overall progress **17%** (29 / 210 mandatory). The chapters that map to your two
complaints are the two you haven't started.

| Chapter | Status | Relevance to your gaps |
|---|---|---|
| W1 – Welcome / Environment | ✅ done | — |
| W2 – Generative AI, Prompting & RAG | 22/49 | Prompt eng., **LLM-as-a-Judge**, **RAG eval (Ragas, Evidently)** |
| W3 – LLM Apps & Deployment | **0/47** | **LangChain**, **LLM Evals + basic metrics**, FastAPI/Streamlit, **Building your first *tool* agent** |
| W4 – Agentic AI Foundations & **Tool Use** | **0/34** | **The fix for gap #1**: ReAct loop, tool schemas, tool dispatcher, guardrails |
| W5 – Multi-Agent Systems & Orchestration | **0/48** | Memory, planning, LangGraph (your Constitution's stretch goal) |
| W6 – Agent **Reliability, Evaluation & Safety** | **0/15** | **The fix for gap #2**: failure modes, agent evaluation, guardrails |
| Capstone | 0/10 | This project |

The good news: your repo already *over-delivers* on Week 1–3 software fundamentals
(FastAPI surface, typed tools, migrations, tests, even a Next.js UI). The missing 280h
is almost entirely the **agentic** middle — Weeks 4–6 — which is also where your
instincts are telling you something's off.

---

## Gap #1 — "The agent feels like an `if`-statement"

You're right, and here's the precise reason.

**What you have.** `agent/policy.py::respond()` is a deterministic finite-state machine:

```
GREETING → EVENT_SELECTION → NEED_EMAIL → CATEGORY_SELECTION → NEED_QUANTITY
        → SEAT_SELECTION → AWAITING_CONFIRMATION → PAYMENT → CONFIRMED
```

Every transition is hand-coded branching. The LLM's *only* jobs are:

- **`agent/llm.py::llm_extract()`** — read one user message and emit a fixed JSON of
  slots (`intent, event_query, city, quantity, category, seat_ids, email`). It is
  *forced* into that schema by the system prompt and never sees the tools.
- **`agent/answer.py`** — answer FAQ-style questions, grounded in static facts.

So the model **parses**, and your code **decides and acts**. Tools (`search_events`,
`compute_quote`, `place_seat_hold`, …) are called by the FSM, never by the model. That
is a classic slot-filling dialog system — robust and demo-safe, but not "agentic," and
it can only ever feel as dynamic as the branches you wrote. Hence the rigidity.

**Worth saying:** this is partly *by design*. Your own `specs/002-agent-core` (FR-001)
mandates a deterministic state machine, and Constitution Principle VIII says "single
agent MVP first." The FSM is not a bug — it's a great safety rail for money and seat
holds. The gap is that the course wants the **model** to drive tool selection within
guardrails, and you've never built that path.

**What the course teaches as the fix** (all currently 0%):

| Course item (chapter) | What it gives you |
|---|---|
| W3 · *Demo: Building a Minimal Tool Agent* · *Exercise: Build Your First Tool Agent* / *Add a Third Tool* | The smallest real tool-calling loop |
| W4 · *Designing Tool Systems* · *Demo: Tool Schema and Structured Arguments* | Turn your F001 functions into model-callable tool schemas |
| W4 · *Demo: Tool Dispatcher Architecture* | Route a model's tool choice to the right function |
| W4 · *Demo: Reason–Act–Observe Loop* | The ReAct pattern — the engine that makes it feel dynamic |
| W4 · *Demo: Autonomy Limits and Guardrails* | How to let the model drive **without** losing the HITL gate |

The target architecture (Tier 2 below) is: **the model chooses and fills tools via
function-calling; the FSM/guardrails stay in code for anything that touches money or
holds.** You keep every safety property and gain the dynamic feel.

---

## Gap #2 — Testing & best-practice "as per the course"

Your tool-level testing is genuinely strong (Constitution VI, "test-first for data &
money," is well honored). The gaps are specifically around the **agent + the LLM**:

**1. The LLM path had zero test coverage.** `tests/conftest.py` has an *autouse*
fixture, `_force_heuristic`, that monkeypatches `llm_available → False` in every single
test. Everything you've been testing is the rule-based fallback. `llm_extract`,
`chat_complete`, the nano-gpt integration, and `answer.py`'s LLM branch were never run
under test. → *Fixed this session (see below).*

**2. No evaluation set / no metrics.** There was no labelled dataset of
message → expected-intent/slots, no accuracy number, no LLM-as-judge for the free-text
replies. The course makes this a whole sub-chapter: W6 *Designing Evaluation Tasks →
Automated Evaluation Workflow → Build an Evaluation Set → Evaluate the Agent System*,
plus W3 *LLM Evals / Evals Basic Metrics* and W2 *Optimizing LLM-as-a-Judge Prompts*.
→ *Seeded this session.*

**3. No guardrail/safety tests.** Nothing asserted the model *can't* do the dangerous
thing (issue payment early, exceed the cap, answer off-topic, be prompt-injected via the
email/seat fields). The course: W6 *Guardrails and Safety · Human-in-the-Loop Control ·
Test Guardrails*. → *HITL bypass test added this session.*

**4. No observability — and it's in your own spec.** Constitution VII ("Observable
Reasoning") and FR-011/FR-012 require logging every tool call (name, args, output, turn
id) and persisting state transitions + per-turn sentiment to an interaction log. None of
that is implemented. The course frames it as W4 *Debugging and Controlling Agents* and
W6 *Failure Diagnosis Workflow*.

---

## What I changed this session

**Wired nano-gpt / Llama into the project** (you asked to use it):

- `.env` (gitignored) → `BOOKING_AGENT_PROVIDER=nanogpt`,
  `BOOKING_AGENT_MODEL=meta-llama/llama-3.3-70b-instruct`, and your `NANOGPT_API_KEY`.
- `.env.example` updated to show the Llama/nano-gpt path as first-class.
- `scripts/nanogpt_check.py` — run it on your machine to **list the exact callable Llama
  model IDs for your account**, smoke-test the key, and run `llm_extract` once. (The
  build sandbox here can't reach nano-gpt.com, so this is the verification step for you.)

> ⚠️ **Rotate this key.** It was shared in plaintext, so treat it as compromised: create
> a new key at nano-gpt.com and replace it in `.env`. The file is gitignored and was not
> committed; I did not store the key anywhere else.

> ℹ️ **Model ID caveat.** `meta-llama/llama-3.3-70b-instruct` is the canonical-looking
> ID; nano-gpt's catalog changes, so confirm with `scripts/nanogpt_check.py` and swap if
> it 404s. Known-good tool-calling fallbacks from their docs: `deepseek/deepseek-v3.2`,
> `openai/gpt-5.2`. For Tier 2 (tool-calling) pick a model whose `/models?detailed=true`
> entry has `capabilities.tool_calling = true`.

**Added 12 LLM-path tests** (suite now **95 passing**), the start of gap #2:

- `tests/test_agent/test_llm_extract.py` — JSON parsing, seat-ID coercion, prose-wrapped
  JSON (common with Llama), malformed-JSON fallback, provider-exception fallback,
  unconfigured → `None`.
- `tests/test_agent/test_llm_eval.py` — a small **evaluation set + scorer** that runs
  offline (stubbed model) and a test proving the scorer actually catches a regression.
  This is the W6 pattern; point it at the live model by removing the stub.
- `tests/test_agent/test_llm_policy.py` — the LLM-driven booking path, the rule that a
  question isn't downgraded into a booking, graceful fallback when the model returns
  `None`, and the **HITL guardrail**: a stray `intent=confirm` from the model cannot
  issue a payment unless the state is `AWAITING_CONFIRMATION` (Constitution I).

---

## What you can add next (ranked)

You chose "just wire the key for now," so Tier 2's architecture work is a **roadmap**,
not done — but it's the answer to "make it dynamic."

### Tier 1 — closes gap #2, low effort, high signal

1. **Grow the evaluation set.** Expand `EVAL_SET` in `test_llm_eval.py` to cover every
   intent, the Arabic/English mix, and the edge cases your spec already enumerates
   (cap exceeded, hold expiry, malformed seats). Add an **LLM-as-judge** scorer for the
   free-text replies. *Course: W6 Build/Evaluate the Agent System; W2 LLM-as-a-Judge.*
2. **More guardrail tests + a tiny `guardrails.py`.** Add tests for cap enforcement,
   off-topic refusal, and prompt-injection on the email/seat fields; centralize the
   checks the FSM already does. *Course: W6 Guardrails & Safety, Test Guardrails.*
3. **Observability (your own FR-011/FR-012).** Log every tool call + state transition to
   an append-only interaction log; add per-turn sentiment. Unlocks the W6
   *Failure Diagnosis* workflow and is required by your Constitution. *Course: W4
   Debugging & Controlling Agents.*
4. **Test the `answer.py` LLM branch** — still only tested in rule-based mode.

### Tier 2 — closes gap #1, makes it genuinely dynamic (bigger)

5. **Add a real tool-calling mode.** Wrap your F001 functions as tool schemas and let the
   model select/fill them via function-calling, in a Reason–Act–Observe loop. Keep the
   FSM as the guardrail for money/holds, and ship it as a **switchable mode** so the MVP
   never regresses (Constitution VIII). *Course: W3 Build Your First Tool Agent; W4
   Designing Tool Systems, Tool Schema & Structured Arguments, Tool Dispatcher, ReAct.*
6. **Dynamic replies.** Replace the canned reply templates in `policy.py` with
   model-generated, context-grounded text (as `answer.py` already does). Even inside the
   FSM this removes most of the "scripted" feeling.
7. **Typed `AgentResponse` union (FR-010)** — you currently return a loose dict.

### Tier 3 — course breadth, later

8. **RAG for venue/FAQ** (your spec 007) → W2/W3 RAG + Ragas/Evidently eval.
9. **Memory, planning, multi-agent** (Constitution VIII stretch) → W5 (Agent Memory,
   Planning & Task Decomposition, Loop Prevention, Graph-Based/LangGraph orchestration).

---

## How to verify the wiring (on your machine)

```bash
# from the repo root, with your venv active
python scripts/nanogpt_check.py
```

It prints the resolved provider/model, the Llama IDs your key can call, a one-line chat
smoke-test, and a sample `llm_extract`. If the chat call fails with a model error, pick
an ID from the printed list and update `BOOKING_AGENT_MODEL` in `.env`. Then:

```bash
uv run uvicorn booking_agent.api.app:app --reload --reload-dir src
# GET /v1/healthz should report llm_configured: true; the chat header shows "AI mode".
```

---

## Appendix A — your spec vs. what's built (best-practice items)

These are *your own* requirements (Constitution + `specs/002-agent-core`) that the course
also grades; the unbuilt ones are concrete "what to add."

| Requirement | Course tie-in | Status |
|---|---|---|
| FR-001 deterministic FSM | W4 control | ✅ built (`policy.py`) |
| FR-005 cap enforcement | W4 guardrails | ✅ built (untested via LLM) |
| FR-007 HITL gate before payment | W6 HITL control | ✅ built + now guardrail-tested |
| FR-013 graceful heuristic fallback | W4 robustness | ✅ built + now tested |
| FR-003/004 typed slots + missing-field clarify | W3 tool agent | ⚠️ partial (no `missing_fields`) |
| FR-010 typed `AgentResponse` union | best practice | ❌ returns dict |
| FR-011 tool-call logging | W4 debugging | ❌ not built |
| FR-012 per-turn sentiment + interaction log | W6 eval | ❌ not built |
| FR-014 LangGraph adapter stub | W5 orchestration | ❌ not built |
| Real tool-calling / ReAct | **W4 (core)** | ❌ not built — gap #1 |
| Agent evaluation set | **W6 (core)** | ⚠️ seeded this session |

## Appendix B — course items most relevant to you (labs & slides, videos omitted)

**W4 – Agentic AI Foundations & Tool Use:** Debugging and Controlling Agents · Reason–Act–Observe
Loop (demo) · Fix a Broken Agent · Designing Tool Systems · Tool Schema and Structured
Arguments · Tool Dispatcher Architecture · Build Three Agent Tools · Task-Oriented Agent
Workflow · Autonomy Limits and Guardrails · Build a Task Agent · Add Guardrails ·
Evaluating Agent Behavior.

**W6 – Reliability, Evaluation & Safety:** Agent Failure Modes · Common Agent Failure Cases ·
Failure Diagnosis Workflow · Agent Evaluation · Designing Evaluation Tasks · Automated
Evaluation Workflow · Build an Evaluation Set · Evaluate the Agent System · Guardrails and
Safety · Guardrail Design Patterns · Human-in-the-Loop Control · Test Guardrails.

**W3 – LLM Apps & Deployment:** LangChain (intro → FAISS → document chat → QA labs) · LLM
Evals + Evals Basic Metrics · FastAPI/Streamlit · Introduction to Agent · Building a
Minimal Tool Agent · Build Your First Tool Agent · Add a Third Tool.

**W2 – GenAI, Prompting & RAG (for eval tooling):** Prompt Engineering · Optimizing LLM-as-a-Judge
Prompts · RAG Evaluation with Ragas · RAG Evaluation with Evidently · LLM-as-a-Jury.

**W5 – Multi-Agent (stretch):** Role-Based Agent Design · Agent Memory (conversation +
vector store) · Planning & Task Decomposition · Loop Prevention · Graph-Based Agent
Workflow (LangGraph) · Multi-Agent Conversation Patterns.
