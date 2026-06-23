# Tazkara vs. the WeCloudData Agentic AI Bootcamp — Gap Analysis & Plan

*What the course teaches, where your project diverges, and a simple ordered plan to align it.*
*Scope: Weeks 4–6 (Tool Use → Multi-Agent → Reliability). Decision taken: promote the existing `tool_agent` to default and simplify/retire the FSM.*

> **Updated 2026-06-23.** This supersedes the 2026-06-15 draft of this file, which predated the now-implemented tool agent. Back then the course's tool-calling agent was genuinely *missing* (0% / "not built"). It now exists (`tool_agent.py`, `tool_specs.py`, `guardrails.py`, `observability.py`, + 8 dedicated tests; suite is 162). So the story has flipped from *"build the agent"* to *"make the agent you already built the default."*

> ## ✅ STATUS: DONE — and we went further than this plan.
> The FSM was **not** kept as a fallback; it was **deleted**. `agent/policy.py` is gone.
> The default is now a **multi-agent orchestrator** (`agent/orchestrator.py`) routing each
> turn through **role-based specialists** (`agent/specialists.py`: catalog → membership →
> pricing → seating), each an LLM tool-loop over its own tools. The no-key safety net is no
> longer a state machine — it's a deterministic **offline brain** (`agent/offline_brain.py`)
> that plays the *model* the same agent loop calls, so the demo and all **161 tests run
> offline**. This satisfies Week-5 multi-agent orchestration for real, not as a stub. The
> rest of this document is kept as the historical analysis that led here.

---

## TL;DR (read this first)

Your instinct is correct: **the course never builds an agent as a hand-coded state machine.** Across Weeks 3–6 the course's definition of "an agent" is one thing — *an LLM that reasons, picks a tool, observes the result, and loops* (Reason–Act–Observe). Your project's **default** path (`agent/policy.py`, the FSM) is *not* that. In the FSM the LLM is demoted to a slot-extractor and all the decisions are hard-coded `if` branches.

But here's the good news, and the reason this is a small job, not a rewrite: **you already built the course's agent.** It lives in `agent/tool_agent.py` + `agent/tool_specs.py` + `agent/guardrails.py`, it's genuinely good, and it's already unit-tested. It's just switched **off by default**, sitting behind the FSM.

So the gap is not "missing concepts." The gap is **which path is the product.** The course wants the tool-calling loop to *be* the agent; your repo treats it as an optional mode. The plan below flips that — and most of the FSM's 700+ lines simply melt away, because they only existed to make a script *feel* like an agent.

---

## 1. How the course defines "an agent"

The curriculum builds one idea, deepening it each week:

| Week | Theme | The core idea the course teaches |
|------|-------|----------------------------------|
| 3 (end) | *Building your first agent* | Convert a RAG pipeline into an agent; build a **Minimal Tool Agent** (a loop + a couple of tools) |
| 4 | *Agentic AI Foundations & Tool Use* | The **Reason–Act–Observe loop**; **tool schemas + structured arguments**; a **tool dispatcher**; **autonomy limits & guardrails** |
| 5 | *Multi-Agent Systems & Orchestration* | **Role-based agents**, **memory** (conversation + vector store), **planning / task decomposition**, **loop prevention**, **graph orchestration** |
| 6 | *Agent Reliability, Evaluation & Safety* | **Failure modes**, **agent evaluation** (task-level), **guardrails & human-in-the-loop**, **observability & monitoring** |

Notice what is *absent*: there is no "finite state machine," no "slot-filling dialog manager," no hand-written `if step == NEED_EMAIL` lesson. The course's agent **decides for itself** what to do next; it is not told by a flowchart.

That is the single lens for the whole gap analysis below.

---

## 2. The one real gap

> **Your default agent is the FSM. The course's agent is the tool-calling loop. You have both — you just need to swap which one is in charge.**

Concretely, today:

- `config.py` → `booking_agent_mode` defaults to **`"fsm"`**.
- `agent/__init__.py:handle()` routes to `policy.respond()` (the FSM) unless the mode is `tool_agent` **and** a key is configured.
- All of your "agent behaviour" that a grader will look at — and that you'll demo — runs through `policy.py`, which is **not** what the course taught.

Everything else in this document is a consequence of that one fact.

---

## 3. Concept-by-concept coverage (Weeks 4–6)

Legend: ✅ present & course-aligned · 🟡 partial / stubbed · ⛔ missing

### Week 4 — Tool Use (the heart of the course)

| Course concept | Where it is in your repo | Status |
|---|---|---|
| Reason–Act–Observe loop | `tool_agent.py:respond_with_tools()` — real loop, feeds tool results back, repeats | ✅ (but off by default) |
| Tool schema & structured arguments | `tool_specs.py:TOOL_SCHEMAS` — 6 OpenAI-style function schemas | ✅ |
| Tool dispatcher architecture | `tool_specs.py:dispatch()` + `_ALLOWED` registry | ✅ |
| Autonomy limits & guardrails | `guardrails.py`; **payment is deliberately *not* a tool** the model can call | ✅ (exemplary) |
| Task-oriented agent (real task) | The full booking task | 🟡 — the *tool agent* does it well, but the **FSM** runs it by default |
| Debugging / controlling agents | `observability.py` — structured tool & transition logs, PII-redacted | ✅ |
| Mini-project: *evaluating agent behaviour* | — | 🟡 — see Week 6; your eval grades NLU, not behaviour |

**Week 4 verdict:** you have effectively *all* of it. It's just not the path you ship.

### Week 5 — Multi-Agent & Orchestration

| Course concept | Where it is in your repo | Status |
|---|---|---|
| Loop prevention | `tool_agent.py:MAX_STEPS = 6` | ✅ |
| Conversation memory | `state.py:ConversationState.history` (bounded to 40 turns) | ✅ |
| Long-term memory (vector store) | `memory.py:BookingMemory` — in-memory dict keyed by email | 🟡 — works, but it's a dict, not the vector store the course teaches |
| Planning / task decomposition | `graph.py:plan_booking()` / `BOOKING_PLAN` | 🟡 — a *hard-coded* list, not a planner that decomposes dynamically |
| Role-based / multi-agent | `graph.py:MultiAgentGraph`, `RecommenderAgent` | 🟡 — a dependency-free shim, not a real orchestrated system |
| Graph framework (LangGraph) | `graph.py:AgentGraph` | 🟡 — same shim; no real `StateGraph` |

**Week 5 verdict:** scaffolded to the right vocabulary, but mostly **stubs**. Fine for an MVP; only deepen these if you want explicit Week 5 credit.

### Week 6 — Reliability, Evaluation & Safety

| Course concept | Where it is in your repo | Status |
|---|---|---|
| Guardrails & safety | `guardrails.py:can_issue_payment()` | ✅ |
| Human-in-the-loop control | confirm/cancel handled in **code** at `AWAITING_CONFIRMATION`, never by the model | ✅ (exemplary) |
| Observability & monitoring | `observability.py` — ring buffer + stdlib logging | ✅ |
| Agent failure modes | model-timeout/exception handling in `tool_agent.py`; forbidden-tool refusal | 🟡 — handled, but no documented *catalogue* of failure cases |
| Agent **evaluation** | `eval_dataset.py` + `scripts/eval_agent.py` | 🟡 — **grades slot-extraction accuracy, not task success** |

**Week 6 verdict:** safety and observability are strong. The weak spot is **evaluation**: the course's "Designing Evaluation Tasks / Evaluate the Agent System" means *did the agent complete the booking, call the right tools, and respect the gate?* — yours measures *did the LLM parse the sentence correctly?* Different question.

---

## 4. What this means in plain terms

- You are **not behind** on the course's core ideas — you implemented the Week 4 agent and the Week 6 safety story properly.
- You **over-built** the wrong thing: the FSM (`policy.py`, 729 lines) plus a fleet of helpers (`compose.py` reply-rephrasing, `answer.py` Q&A, `interests.py` discovery, `_stall_help`, `pending_switch` "abandon booking?" logic) exist almost entirely to make a *script* behave like an agent. In tool-agent mode, **the LLM does that work natively** from one system prompt.
- Therefore "follow the course" and "make it simple" are the **same task**: promote the tool agent, and the complicated machinery becomes unnecessary.

---

## 5. The plan (ordered, simple, safe)

Each phase is independently shippable and keeps your tests green. Do them in order.

### Phase 0 — Set the policy (no code)
Keep one safety property you already have and the course respects: **the demo must never break with no API key.** So the target is:
- **Key present →** tool-calling agent (the course's agent, your default).
- **No key →** FSM as a silent offline fallback.

This means you *promote* the tool agent without *deleting* your safety net on day one.

### Phase 1 — Flip the default (≈1 line + test update)
- `config.py`: change `booking_agent_mode` default from `"fsm"` → `"tool_agent"`.
- `agent/__init__.py:handle()` already falls back to the FSM when `tool_mode_available()` is `False`, so no routing change is needed.
- Update the test `test_router_defaults_to_fsm` → it should now assert the tool agent is chosen *when a key is available*, and the FSM only when not. (This test currently encodes the old default; flipping it is part of the change, not a regression.)

### Phase 2 — Close the two grounding gaps so the tool agent loses nothing the FSM did
The FSM can answer FAQs and recommend events from real data. Give the tool agent the same powers as **tools** (so its answers stay grounded — directly addresses the Week 6 *hallucination* failure mode):
- Add `answer_faq` → wraps your existing `rag.py` knowledge base.
- (Optional) Add `recommend_events` → wraps `interests.py` / `graph.recommend_events`.
- Register both in `tool_specs._ALLOWED` and `TOOL_SCHEMAS`. Payment stays **out** of the tool list — do not change that.

### Phase 3 — Upgrade evaluation to measure *the agent* (Week 6's real ask)
- Add a second eval set of **task scenarios**, not sentences. Each case = a goal + the expected **trajectory** (tools called, in order) + the expected **outcome** (reached `AWAITING_CONFIRMATION`, correct total, **never** charged without an explicit confirm).
- Reuse the `FakeModel` pattern already in `tests/test_agent/test_tool_agent.py` for an offline, deterministic version; extend `scripts/eval_agent.py` to score task success on the live model.
- This turns "my NLU is 80% accurate" into "my agent completes the booking task X% of the time and never violates the payment gate" — which is what the course grades.

### Phase 4 — Simplify / demote the FSM
Once Phases 1–3 are green:
- Re-document `policy.py` as the **offline fallback**, not "the MVP." It's no longer *the agent* — it's the no-key safety net.
- Delete or fold in the helpers that only existed to dress up the script: `compose.py`, `_stall_help`, the `pending_switch` flow, and any `answer.py`/`interests.py` paths now covered by the new tools. (Keep `rag.py` and `interests.py` *logic* — they back the new tools — just drop the FSM-only plumbing.)
- Update `CLAUDE.md`, `README.md`, and Constitution Principle VIII to say the tool-calling agent is the MVP and the FSM is the fallback.

> If you'd rather **fully** remove the FSM (no fallback), replace the offline path with a tiny scripted fake-model loop so tests and the keyless demo still run. **Recommended: keep the FSM as the fallback** — it's a genuine reliability asset and costs you nothing once it's no longer the headline.

### Phase 5 — (Optional) Real Week 5 depth
Only if you want multi-agent / memory / planning credit beyond a mention:
- `memory.py` → back it with a small vector store (the course's *Long-Term Memory with Vector Store*).
- `graph.py` → a real planner that decomposes the goal, or a real LangGraph `StateGraph` with role nodes (Catalog / Pricing / Hold). Otherwise, present these honestly as "designed-for, stubbed."

---

## 6. Keep these no matter what (do not "simplify" them away)

These are both course requirements (Week 6) and your project's Constitution non-negotiables:

1. **Human-in-the-loop payment gate** — booking/payment only after an explicit user "confirm", executed in code. ✅ already correct in `tool_agent.py`.
2. **Payment is never a model tool** — the LLM physically cannot trigger a charge. ✅ already correct in `tool_specs.py`.
3. **Atomic seat holds** — all-or-nothing, 10-min TTL. ✅ in `tools/holds.py`.
4. **Loop prevention** — `MAX_STEPS` cap. ✅.
5. **Observability** — every tool call & transition logged. ✅.

---

## 7. One-line summary for your presentation

> *"We built the course's agent — an LLM Reason–Act–Observe tool-calling loop with a hard human-in-the-loop payment gate — and kept a deterministic state machine as an offline fallback so the demo never breaks without a model."*

That sentence is true the moment Phase 1 lands, and it's exactly the story the curriculum is looking for.

---

### Appendix — files referenced

| Concern | File |
|---|---|
| Mode router | `src/booking_agent/agent/__init__.py` |
| FSM (default today → fallback after) | `src/booking_agent/agent/policy.py` |
| Tool-calling agent (→ default) | `src/booking_agent/agent/tool_agent.py` |
| Tool schemas + dispatcher | `src/booking_agent/agent/tool_specs.py` |
| Guardrails / HITL gate | `src/booking_agent/agent/guardrails.py` |
| Observability | `src/booking_agent/agent/observability.py` |
| Long-term memory (stub) | `src/booking_agent/agent/memory.py` |
| Planner / multi-agent (stub) | `src/booking_agent/agent/graph.py` |
| Eval set (NLU today → add task-level) | `src/booking_agent/agent/eval_dataset.py`, `scripts/eval_agent.py` |
| Default mode flag | `src/booking_agent/config.py` (`booking_agent_mode`) |
| Tool-agent tests (the pattern to reuse) | `tests/test_agent/test_tool_agent.py` |
