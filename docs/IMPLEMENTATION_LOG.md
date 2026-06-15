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

**Suite: 107 passing.** End-to-end runtime smoke (`scripts/agent_smoke.py`) books a
ticket and prints the observable-reasoning trace with PII redacted.

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
- **Result.** 83 → **107 tests**, all green; the AI/agent paths went from 0 coverage to
  extractor + eval + Q&A + guardrails + observability.
