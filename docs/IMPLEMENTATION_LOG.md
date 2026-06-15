# Implementation Log — closing the course gaps

Living worklog for hardening Booking-Agent against the bootcamp's agentic
requirements. Plan and rationale: see [`COURSE_GAP_ANALYSIS.md`](COURSE_GAP_ANALYSIS.md).
Track chosen: **incremental reliability/testing first**; the tool-calling/ReAct
refactor (analysis Tier 2) stays deferred until decided.

> Note on pushing: increments are committed here as they land. If a commit hasn't
> reached GitHub yet, run `git push origin main` from the machine that holds the repo
> credentials.

## Status

| # | Increment | Course tie-in | State |
|---|---|---|---|
| 1 | Wire nano-gpt/Llama + first LLM-path tests + gap analysis | W3/W6 | ✅ done |
| 2 | Shared evaluation dataset + automated eval runner | W6 Build/Evaluate an eval set | ✅ done |
| 3 | Guardrails module + tests (HITL, cap, on-topic) | W6 Guardrails & Safety | ⏳ next |
| 4 | Observability: tool-call + state-transition logging | W4 debug / W6 failure diagnosis; FR-011/VII | ⏳ planned |
| 5 | Test the `answer.py` LLM branch | W6 eval | ⏳ planned |
| 6 | Dynamic (model-generated) booking replies | W4 | ⏳ planned |

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
