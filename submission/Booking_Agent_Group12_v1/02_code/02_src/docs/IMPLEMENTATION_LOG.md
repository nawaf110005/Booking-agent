# Implementation Log — closing the course gaps

Living worklog for hardening Booking-Agent against the bootcamp's agentic
requirements. Plan and rationale: see [`COURSE_GAP_ANALYSIS.md`](COURSE_GAP_ANALYSIS.md).
Track chosen: **incremental reliability/testing first**; the tool-calling/ReAct
refactor (analysis Tier 2) stays deferred until decided.

> Pushing: commit 1 is committed locally (`25430dd`). The build environment is a
> create-only mount (it can't delete files), so it can't push or make further commits
> and left stale git `*.lock` files behind. Finish from the machine that holds the repo:
>
> ```bash
> rm -f .git/HEAD.lock .git/index.lock .git/refs/heads/main.lock .git/objects/maintenance.lock
> rm -f _probe_del.txt .git/_probe.txt && find .git/objects -name 'tmp_obj_*' -delete
> git add -A && git commit -m "Agent hardening: eval harness, guardrails, observability, dynamic replies, smoke + docs"
> git push origin main      # ships commit 1 + this one (.env stays local — gitignored)
> ```

## Status

| # | Increment | Course tie-in | State |
|---|---|---|---|
| 1 | Wire nano-gpt/Llama + first LLM-path tests + gap analysis | W3/W6 | ✅ committed (25430dd) |
| 2 | Shared evaluation dataset + automated eval runner | W6 Build/Evaluate an eval set | ✅ built + tested · pending commit |
| 3 | Guardrails module + tests (HITL gate, cap) | W6 Guardrails & Safety | ✅ built + tested · pending commit |
| 4 | Observability: tool-call + state-transition logging | W4 debug / W6 failure diagnosis; FR-011/VII | ✅ built + tested · pending commit |
| 5 | Test the `answer.py` LLM branch | W6 eval | ✅ built + tested · pending commit |
| 6 | Dynamic (model-generated) booking replies (opt-in) | W4 | ✅ built + tested · pending commit |
| 7 | Presentation notes + agent-loop smoke script | — | ✅ done · pending commit |
| 8 | **Tool-calling agent mode** (ReAct loop + tool dispatcher + autonomy guardrails + loop prevention) | W4 Tool Use / W5 Loop Prevention | ✅ built + tested · pending commit |
| 9 | **Conversational + personalised layer** — chat/ask at any step, greet by name, warmer prompts, dynamic replies on by default | W4 / personalisation | ✅ built + tested · pending commit |
| 10 | **Robustness** — LLM timeout (no hanging) + clear handling of off-topic/irrelevant messages (no canned-greeting brush-off) | W6 failure modes | ✅ built + tested · pending commit |
| 11 | **Personalised discovery** — infer/ask interest, use profile prefs (don't dump the catalog) + long-term booking memory | spec 006 / W5 | ✅ built + tested · pending commit |
| 12 | **Per-turn sentiment** + interaction log; adapt on frustration | FR-012 / W6 | ✅ built + tested · pending commit |
| 13 | **RAG** over a venue/FAQ knowledge base, grounded into the answerer | spec 007 / W2–3 | ✅ built + tested · pending commit |
| 14 | **Typed `AgentResponse`** (response_type discriminator) at the API boundary | FR-010 | ✅ built + tested · pending commit |
| 15 | **LLM-as-judge** scorer for free-text replies | W2 | ✅ built + tested · pending commit |
| 16 | **Orchestration** — LangGraph-style adapter + planner + multi-agent router (recommender + booking) | FR-014 / W5 | ✅ built + tested · pending commit |

**Suite: 143 passing.** Every named course gap is now implemented and tested
(see the gap-closure table below). Remaining work is production-hardening of the
in-memory stores (Redis/vector DB) and grading tool-agent mode on the live model.

## Gap closure (vs. COURSE_GAP_ANALYSIS.md)

| Course gap | Module | Status |
|---|---|---|
| Tool-calling / ReAct agent (W4) | `tool_agent.py`, `tool_specs.py` | ✅ |
| Agent evaluation set + automated grader (W6) | `eval_dataset.py`, `scripts/eval_agent.py` | ✅ |
| LLM-as-judge (W2) | `judge.py` | ✅ |
| Guardrails & safety, autonomy limits (W6/W4) | `guardrails.py` | ✅ |
| Observability / tool-call logging (FR-011, W4) | `observability.py` | ✅ |
| Per-turn sentiment + interaction log (FR-012) | `sentiment.py` | ✅ |
| RAG venue/FAQ (spec 007, W2–3) | `rag.py` | ✅ |
| Personalisation + preference learning (spec 006) | `interests.py`, `profiles.py`, `memory.py` | ✅ |
| Typed AgentResponse (FR-010) | `responses.py` | ✅ |
| Loop prevention (W5) | `tool_agent.py` (step cap) | ✅ |
| Planning / task decomposition (W5) | `graph.py` (`plan_booking`) | ✅ |
| Multi-agent orchestration + LangGraph stub (FR-014, W5) | `graph.py` (`MultiAgentGraph`, `AgentGraph`) | ✅ (demo-grade) |
| Dynamic, conversational, personalised UX | `compose.py`, `answer.py`, `policy.py` | ✅ | Runtime smokes: `scripts/agent_smoke.py` (FSM) and the
tool-agent loop both book a ticket and print the observable-reasoning trace with PII
redacted. Tool-agent mode is opt-in via `BOOKING_AGENT_MODE=tool_agent`; FSM stays the
default so the MVP can't regress (Constitution VIII).

## Changelog

### 2026-06-15

- **Increment 1.** Wired the agent to nano-gpt/Llama (`.env`, `.env.example`,
  `scripts/nanogpt_check.py`). Added the first LLM-path tests — `test_llm_extract.py`,
  `test_llm_eval.py`, `test_llm_policy.py` (incl. the HITL-bypass guardrail test).
  Suite: 95 passing. Authored `COURSE_GAP_ANALYSIS.md`.
- **Increment 2.** Extracted a shared, expanded evaluation dataset
  (`agent/eval_dataset.py`) and added an automated eval runner
  (`scripts/eval_agent.py`) that grades the live model and prints accuracy — the W6
  "Automated Evaluation Workflow" pattern. Tests updated to reuse the dataset.
- **Increment 3.** `agent/guardrails.py` — pure, testable safety predicates (payment
  only at the confirmation gate, tier-cap), wired into `policy.py`; `test_guardrails.py`.
- **Increment 4.** `agent/observability.py` — structured, PII-redacted log of every
  tool call + state transition (Constitution VII / FR-011); instrumented `policy.py`;
  `test_observability.py`.
- **Increment 5.** `test_answer_llm.py` — covers the grounded-Q&A LLM branch + its
  fallback (previously untested).
- **Increment 6.** `agent/compose.py` — opt-in dynamic reply phrasing
  (`BOOKING_AGENT_DYNAMIC_REPLIES`, default off); wired into `_reply`; `test_compose.py`.
- **Increment 7.** `scripts/agent_smoke.py` (end-to-end agent-loop smoke + trace) and
  `docs/PRESENTATION_NOTES.md` (pain-point → fix narrative for the capstone).
- **Increment 8.** Tool-calling agent mode — `agent/tool_specs.py` (function schemas +
  dispatcher over the real F001 tools) and `agent/tool_agent.py` (Reason–Act–Observe
  loop, step cap for loop prevention, deterministic HITL confirm). Routed via
  `agent.handle` + `BOOKING_AGENT_MODE` (default `fsm`); API uses the router.
  `test_tool_agent.py`: happy path, autonomy guardrail (model can't book/pay), loop
  prevention, observability, routing.
- **Increment 9.** Conversational + personalised experience. The agent now answers
  questions / small talk **at any step** and keeps the booking going (no more "can't ask
  anything mid-flow"), greets the user by name (derived from email), and feeds the model
  a personalisation context (name, tier, step, what's-needed) via a warmer prompt — in
  both the FSM and tool-agent modes. Dynamic replies (`compose.py`) are **on by default**
  so the wording reads naturally; tests pin it off for determinism. `test_conversation.py`
  covers name personalisation, mid-step questions, and the gated routing.
- **Increment 10.** Robustness from real use. (a) Every LLM call now has a hard timeout
  (`LLM_TIMEOUT_SECONDS`, default 20s) so a slow/unreachable provider fails fast instead
  of hanging; the FSM degrades to heuristics and the tool-agent returns a clear message
  rather than crashing/500-ing. (b) Off-topic / irrelevant messages ("write me code") now
  get a clear, in-character reply that declines and redirects — no more falling through to
  the canned greeting that ignored the user. Tests in `test_conversation.py` /
  `test_tool_agent.py`.
- **Increment 11 (gap sweep).** Closed every remaining named course gap:
  personalised discovery (`interests.py`, `profiles.py`) + long-term memory (`memory.py`);
  per-turn sentiment (`sentiment.py`); RAG venue/FAQ (`rag.py`); typed `AgentResponse`
  (`responses.py`); LLM-as-judge (`judge.py`); and orchestration — planner + LangGraph
  adapter + multi-agent router (`graph.py`). See the gap-closure table above.
- **Result.** 83 → **143 tests**, all green, and **all named course gaps implemented**.
  The agent now: chats and personalises, learns interests (no catalog dumps), remembers
  past bookings, tracks sentiment, grounds answers in a knowledge base, fails fast on a
  slow model, exposes typed responses, can be graded by an LLM judge, and — in
  tool-agent mode — lets the model drive tools in a ReAct loop behind a code-enforced
  payment gate. Remaining is production-hardening (Redis/vector DB instead of in-memory
  stores) and tuning tool-agent mode against the live model.
