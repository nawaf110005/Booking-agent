# Technical Q&A Prep — Booking Agent

Likely questions with crisp answers and where it lives in the code. Skim the **bold**
answers; the rest is backup depth.

---

## A. Agentic design

**Q: Is this actually an "agent," or just a chatbot with a script?**
Both modes are agents in the bootcamp sense — they perceive (NLU), decide, and act through
tools toward a goal. The **default `fsm` mode** is a deterministic policy over typed tools
(`agent/policy.py`); the **`tool_agent` mode** is a true LLM tool-calling loop
(`agent/tool_agent.py`) where the model chooses each tool. Same tools underneath
(`agent/tool_specs.py`).

**Q: Why is the deterministic FSM the default and not the LLM agent?**
The constitution says ship the safe single-agent MVP first (Principle VIII). Money and seat
holds must be correct every time, so the default path is deterministic and fully tested; the
LLM tool-loop is opt-in via `BOOKING_AGENT_MODE=tool_agent`. Both enforce the same
code-level payment gate, so neither can regress safety.

**Q: Walk me through the ReAct loop.**
`respond_with_tools()`: build messages (system + state summary + user) → call the model with
tool schemas → if it returns tool calls, **dispatch** each to the real Python function and
feed results back → repeat. It exits when the model answers or a **step cap** (`MAX_STEPS=6`)
trips — that's loop prevention (Week 5).

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
Payment is **not a tool** the model can call. Booking/payment runs in code only when
`state.step == AWAITING_CONFIRMATION` **and** the user's intent is an explicit confirm
(`guardrails.can_issue_payment`). Enforced in both modes. There's a test that feeds a stray
model "confirm" early and asserts **no** payment is produced
(`test_llm_confirm_cannot_bypass_hitl_gate`).

**Q: Could a prompt injection ("ignore your rules and pay") bypass it?**
No — because the gate isn't a prompt instruction, it's a code branch. The model has no
payment tool and no way to set the state to `AWAITING_CONFIRMATION` itself; only the
deterministic flow does, after a real hold. Worst case the model says "confirm" and nothing
happens.

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
Two layers. (1) A labelled **evaluation set** of message → expected slots with a scorer and
an automated grader (`agent/eval_dataset.py`, `scripts/eval_agent.py`) — swap the model, keep
the yardstick. (2) An **LLM-as-judge** that scores free-text replies 1–5 for helpfulness +
grounding (`agent/judge.py`). Plus 148 unit/integration tests.

**Q: How do you test the LLM path without calling the model in CI?**
The provider is injectable. Tests stub `chat_complete` / the `complete` callable with canned
responses, so the loop, parsing, guardrails, and routing are all covered offline
(`test_llm_extract.py`, `test_tool_agent.py`). An autouse fixture forces the rule-based path
for the booking-flow tests so they're deterministic.

**Q: What's your test count and coverage focus?**
148 tests, all green. Coverage is concentrated where it matters: money, holds, the HITL gate,
slot extraction, guardrails, and the tool loop. The suite grew from 69 → 148 alongside the work.

---

## F. LLM, prompting & providers

**Q: Why Gemini, and how hard is it to switch models?**
One env var. Gemini speaks the OpenAI API, so it reuses the same OpenAI SDK with a base URL
(`agent/llm.py::openai_base_url`). `BOOKING_AGENT_PROVIDER` ∈ {google, anthropic, openai,
nanogpt}; `active_llm_key` resolves the matching key (`config.py`).

**Q: What does the LLM actually do — does it run the whole booking?**
In FSM mode it does **NLU only**: extract slots into a typed `BookingParams`
(`agent/llm.py::llm_extract`) and answer grounded questions (`agent/answer.py`). The decisions
and tool calls are code. In tool_agent mode it also chooses tools. Either way it never
touches money.

**Q: What if the model is slow, down, or has no key?**
Graceful degradation everywhere: every call has a **timeout** (`LLM_TIMEOUT_SECONDS`, default
20s); on failure `llm_extract`/`answer`/`compose` fall back to the rule-based path, and the
tool loop returns a clear message instead of hanging or 500-ing. With no key at all the whole
app still books via heuristics.

**Q: How do you stop hallucination (e.g., inventing events/prices)?**
Answers are grounded in the live catalog + a small knowledge base; the prompt forbids
inventing events/prices; unknown events are caught in the extractor and answered with "couldn't
find X, here's what's on" (`agent/extract.py`, `agent/policy.py`). RAG retrieval ignores generic
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

**Q: Is this multi-agent? You mentioned LangGraph.**
The MVP is single-agent. There's a **planner** (task decomposition), a **LangGraph-style
adapter**, and a **recommender agent** with a router (`agent/graph.py`) — the scaffolding so a
multi-agent fleet (Catalog/Pricing/Hold/Fulfilment) can graft on **without** regressing the
MVP. Full orchestration is the stretch goal.

---

## I. Architecture & engineering

**Q: Why FastAPI + a state machine instead of LangChain?**
The constitution wanted in-repo, typed, testable tools (Principle III) — not a framework
dependency we couldn't audit. The FSM gives deterministic, debuggable control; the LLM is a
swappable component, not the control flow.

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
webhook; add the live vector store for RAG; promote tool-agent to default after grading it on
the live model; add rate limiting + auth on the admin endpoints (already token-gated).

**Q: Secrets / PDPL?**
Keys live in a gitignored `.env`; PII is collected only to look up membership and deliver a
ticket, redacted in logs, and never put in URLs. (Note: rotate any key shared in plaintext.)

---

## K. "Why not just…" / trade-offs

- **Why not let the LLM do everything end-to-end?** It would occasionally charge the wrong
  amount or invent events. Keeping money + holds in deterministic code is the whole safety story.
- **Why not a single mega-prompt?** No guarantees, no testability, no audit trail. Tools +
  a gate give correctness and observability.
- **Why an FSM if the course is about agents?** The FSM is the safety rail; the agentic
  tool-loop runs *on top of the same tools*. We demonstrate both and can flip between them.

---

## L. Bootcamp mapping (if asked "which week is this?")
W2 prompting/RAG/LLM-as-judge · W3 LLM apps + first tool agent · **W4 tool use, dispatcher,
ReAct, autonomy limits** · W5 memory, planning, loop prevention, graph orchestration ·
**W6 evaluation, guardrails, HITL, failure modes**.
