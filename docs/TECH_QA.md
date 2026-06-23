# Technical Q&A Prep — Booking Agent

Likely questions with crisp answers and where it lives in the code. Skim the **bold**
answers; the rest is backup depth.

---

## A. Agentic design

**Q: Is this actually an "agent," or just a chatbot with a script?**
Yes — it's a **multi-agent system**. The **default `multi_agent` mode** is an orchestrator
(`agent/orchestrator.py`) that routes each turn through four role-based specialists
(`agent/specialists.py`) in booking order — catalog → membership → pricing → seating — each
a true LLM Reason–Act–Observe loop restricted to **only its own tools** (`agent/tool_specs.py`).
The **`tool_agent` mode** is the single-agent variant: one loop with the full tool set
(`agent/tool_agent.py`). Same tools underneath either way.

**Q: Why an orchestrator with role specialists and not one big agent?**
The constitution says ship a safe, correct MVP (Principle VIII). Scoping each specialist to
only its phase's tools narrows what the model can do wrong and makes each handoff testable.
With **no provider key the specialists run on a deterministic offline brain**
(`agent/offline_brain.py`), so the demo and the entire test suite run offline — *same agents,
swappable brain*. The single-agent `tool_agent` mode is kept for comparison. All paths enforce
the same code-level payment gate, so none can regress safety.

**Q: Walk me through the ReAct loop.**
It runs **per specialist**: build messages (system + state summary + user) → call the model
(or the offline brain) with that specialist's tool schemas → if it returns tool calls,
**dispatch** each to the real Python function and feed results back → repeat. A specialist
exits when its phase completes (the orchestrator hands off to the next) or a per-specialist
**step cap** trips — that's loop prevention (Week 5).

**Q: How does the model actually call your Python functions?**
Tools are advertised as OpenAI function-call schemas (`TOOL_SCHEMAS`). The model returns a
tool name + JSON args; `dispatch()` validates and runs the real F001 function, updates
conversation state, and returns a JSON result the model observes. Unknown/forbidden names
return an error result, not an action.

**Q: What stops it from looping forever or thrashing tools?**
A hard step cap per turn. On exhaustion it returns a safe "give me one detail at a time"
message. Tested in `test_tool_agent.py::test_loop_prevention_caps_steps`.

---

## B. Human-in-the-loop & safety

**Q: How do you *guarantee* it never charges without confirmation?**
Booking/payment is **no specialist's tool** — the model can never trigger a charge. It runs
in code only when `state.step == AWAITING_CONFIRMATION` **and** the user's intent is an
explicit confirm (`guardrails.can_issue_payment`). Enforced in every mode. There's a test
that feeds a stray model "confirm" early and asserts **no** payment is produced
(`test_llm_confirm_cannot_bypass_hitl_gate`).

**Q: Could a prompt injection ("ignore your rules and pay") bypass it?**
No — because the gate isn't a prompt instruction, it's a code branch. No specialist has a
payment tool, and the model has no way to set the state to `AWAITING_CONFIRMATION` itself;
only code does, after a real hold. Worst case the model says "confirm" and nothing happens.

**Q: What other guardrails exist?**
Tier **ticket-cap** enforcement before any quote (`guardrails.exceeds_cap`), **off-topic
refusal** (declines "write me code" and steers back), and **anti-hallucination** for unknown
events. All in `agent/guardrails.py` + tested.

---

## C. Money & correctness

**Q: How do you avoid floating-point money bugs?**
Everything is **integer halalas** (1 SAR = 100 halalas) with **half-up** integer math
(`tools/money.py`); percentages are integer basis points (1500 = 15% VAT). No float ever
enters the arithmetic, so a quote is reproducible to the halala.

**Q: Where does the discount come from — can a user fake it?**
No. The member tier and ticket cap are looked up from the `members` table by email
(`db/enums.py`, `tools/members.py`), never supplied by the client. Worked example: Gold ×4 =
3,200 → Platinum −15% = 2,720 → +15% VAT = **3,128.00 SAR**.

**Q: Is VAT correct per ZATCA?**
15% is applied as a separate line item on the net subtotal and the total shown at
confirmation equals what's charged.

---

## D. Concurrency & seat holds

**Q: Two users grab the same seats at the same time — what happens?**
`place_seat_hold()` is **all-or-nothing**: if any requested seat isn't available it raises
`SeatUnavailableError` and holds nothing. The DB write is the arbiter, so only one booking
can hold a given seat. Holds carry a fixed **10-minute TTL**; a sweeper releases expired ones
(`tools/holds.py`, `booking-agent sweep`).

**Q: How is "atomic" actually enforced — DB lock or app logic?**
A single transaction checks availability and writes the holds together; on any conflict it
rolls back. Tests in `tests/test_tools/test_holds.py` (TTL/expiry use `freezegun`).

---

## E. Evaluation & testing

**Q: How do you evaluate an *agent* — outputs aren't deterministic?**
A labelled **evaluation set** of message → expected slots with a scorer and an automated
grader (`agent/eval_dataset.py`, `scripts/eval_agent.py`) — swap the model, keep the
yardstick. Plus 181 unit/integration tests covering the booking flow, guardrails, and tools.

**Q: How do you test the LLM path without calling the model in CI?**
The provider is injectable. Tests stub `chat_complete` / the `complete` callable with canned
responses, so the loop, parsing, guardrails, and routing are all covered offline
(`test_llm_extract.py`, `test_tool_agent.py`, `test_orchestrator_flow.py`). An autouse fixture
forces the offline brain for the booking-flow tests so they're deterministic.

**Q: What's your test count and coverage focus?**
181 tests, all green against an 85%+ coverage gate. Coverage is concentrated where it matters:
money, holds, the HITL gate, slot extraction, guardrails, and the per-specialist tool loop.
The suite grew from 69 → 181 alongside the work.

---

## F. LLM, prompting & providers

**Q: Which model, and how hard is it to switch?**
One env var. The active config is **nano-gpt** (an OpenAI-compatible proxy) serving
`gemini-2.5-flash-preview-04-17`, so it reuses the same OpenAI SDK with a base URL
(`agent/llm.py::openai_base_url`). `BOOKING_AGENT_PROVIDER` ∈ {nanogpt, anthropic, openai,
google}; `active_llm_key` resolves the matching key (`config.py`). Direct Google Gemini is
kept as a backup — we moved to nano-gpt after the free tier hit quota limits.

**Q: What does the LLM actually do — does it run the whole booking?**
In `multi_agent` mode the **specialists drive the tools**: each role specialist reasons and
calls the F001 tools for its phase, with NLU/slot extraction (`agent/llm.py::llm_extract`) and
the concierge Q&A (`agent/answer.py`) as supporting roles. The dangerous decisions stay in
code. In `tool_agent` mode a single agent chooses tools. Either way the model never touches
money.

**Q: What if the model is slow, down, or has no key?**
Graceful degradation everywhere: every call has a **timeout** (`LLM_TIMEOUT_SECONDS`, default
20s); on failure `llm_extract`/`answer`/`compose` fall back to deterministic logic, and with
no key at all the specialists run on the **offline brain** (`agent/offline_brain.py`) so the
whole app still books — no network required.

**Q: How do you stop hallucination (e.g., inventing events/prices)?**
Answers are grounded in the live catalog + a small knowledge base; the prompt forbids
inventing events/prices; unknown events are caught in the extractor and answered with "couldn't
find X, here's what's on" (`agent/extract.py`, `agent/answer.py`). RAG retrieval ignores generic
words like "ticket" so it can't misfire.

**Q: Cost / latency?**
Flash-class model, short prompts, `temperature=0`, bounded by the timeout. NLU is one short
call per turn; dynamic replies add an optional second call (toggle off with
`BOOKING_AGENT_DYNAMIC_REPLIES=false`).

---

## G. RAG, personalization, memory

**Q: How does RAG work — which vector DB?**
None — it's a dependency-free, stopword-filtered **token-overlap retriever** over a small
venue/FAQ knowledge base (`agent/rag.py`). The `retrieve()` signature mirrors a real
retriever, so swapping in Chroma/FAISS later is a drop-in. Kept simple because the KB is tiny.

**Q: How is personalization done — and is it private?**
The agent asks your interest and filters discovery instead of dumping the catalog
(`agent/interests.py`); preferences and past bookings persist across sessions keyed by email
(`agent/profiles.py`, `agent/memory.py`). In logs, emails are **redacted**. It's in-memory for
the demo; Redis/DB is the documented upgrade.

---

## H. Observability & multi-agent

**Q: What exactly do you log, and how is it PII-safe?**
Every tool call and state transition → a structured, bounded event log with emails masked
(`agent/observability.py`). It's what powers the "what did the agent do?" trace and failure
diagnosis. See it live with `scripts/agent_smoke.py`.

**Q: Is this multi-agent?**
Yes — it's implemented. The default is an **orchestrator** (`agent/orchestrator.py`) that
routes each turn through four role specialists — **catalog / membership / pricing / seating**
(`agent/specialists.py`) — each scoped to only its own tools and handing off as its phase
completes. Full orchestration is no longer a stretch goal; it's the shipped default.

---

## I. Architecture & engineering

**Q: Why FastAPI + in-repo tools instead of LangChain?**
The constitution wanted in-repo, typed, testable tools (Principle III) — not a framework
dependency we couldn't audit. The orchestrator gives debuggable, observable control over the
specialists; the LLM "brain" is a swappable component (swap in the offline brain with no key),
not the control flow.

**Q: How is conversation state managed?**
A per-session `ConversationState` dataclass (`agent/state.py`) in an in-memory session store
(`agent/store.py`). Each turn is one structured response (`AgentResponse`, FR-010) the UI
renders as cards — never an untyped blob.

**Q: Two frontends — why?**
A Next.js storefront (primary) and a no-Node static site, both on the same `/v1` API, plus a
CLI. The static site means the demo runs with zero build step.

---

## J. Security, production, scaling

**Q: Is payment real?**
No — Moyasar **sandbox** for the demo, isolated behind one adapter with a fake implementation
so tests run offline. The real webhook is signature-verified + idempotent by design (exactly
one ticket per booking).

**Q: Ticket fraud — can I screenshot a QR and get in?**
No. The QR encodes a server-signed **HMAC token** (booking id + seats + nonce), verified at
scan time — not a bare booking id (`fulfilment/qr.py`).

**Q: How would you take this to production?**
Swap the in-memory session/preference/memory stores for Redis/Postgres; wire the real Moyasar
webhook; add the live vector store for RAG; grade the live-model specialists against the
offline brain on the eval set before each release; add rate limiting + auth on the admin
endpoints (already token-gated).

**Q: Secrets / PDPL?**
Keys live in a gitignored `.env`; PII is collected only to look up membership and deliver a
ticket, redacted in logs, and never put in URLs. (Note: rotate any key shared in plaintext.)

---

## K. "Why not just…" / trade-offs

- **Why not let the LLM do everything end-to-end?** It would occasionally charge the wrong
  amount or invent events. Keeping money + holds in deterministic code is the whole safety story.
- **Why not a single mega-prompt?** No guarantees, no testability, no audit trail. Tools +
  a gate give correctness and observability.
- **Why a deterministic offline brain if the course is about agents?** It's the safety / no-key
  rail: the *same* role specialists run on it when no provider key is set, so the demo and test
  suite are fully offline and reproducible — same agents, swappable brain. The live LLM brain
  runs the identical orchestration on top.

---

## L. Bootcamp mapping (if asked "which week is this?")
W2 prompting/RAG/LLM-as-judge · W3 LLM apps + first tool agent · **W4 tool use, dispatcher,
ReAct, autonomy limits** · W5 memory, planning, loop prevention, graph orchestration ·
**W6 evaluation, guardrails, HITL, failure modes**.
