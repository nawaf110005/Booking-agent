"""Automated evaluation workflow (bootcamp Week 6).

Grades the **live** nano-gpt/Llama model on the shared evaluation set and prints
per-case results + overall slot-extraction accuracy. Run it after changing the
model, the system prompt, or the extractor:

    uv run python scripts/eval_agent.py
    # or
    python scripts/eval_agent.py

Requires a configured provider/key (see `.env`); with none it exits early rather
than grading the heuristic fallback.
"""

from __future__ import annotations

import sys

from booking_agent.agent.eval_dataset import grade
from booking_agent.agent.llm import llm_available, llm_extract
from booking_agent.config import settings


def main() -> int:
    if not llm_available():
        print("No LLM configured — set BOOKING_AGENT_PROVIDER + key in .env first.")
        return 1

    print(f"Grading {settings.booking_agent_provider} / {settings.booking_agent_model}\n")
    report = grade(llm_extract)

    for r in report["results"]:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"  [{mark}] {r['message']}")
        if not r["ok"]:
            print(f"         expected ⊇ {r['expect']}")
            print(f"         got        {r['got']}")

    acc = report["accuracy"]
    print(f"\nAccuracy: {report['correct']}/{report['total']} = {acc:.0%}")
    # Non-zero exit if below a CI-style threshold, so this can gate a pipeline.
    return 0 if acc >= 0.80 else 2


if __name__ == "__main__":
    sys.exit(main())
