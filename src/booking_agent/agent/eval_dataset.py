"""Shared evaluation set for the slot extractor.

Single source of truth used by BOTH:
  - the offline regression tests (`tests/test_agent/test_llm_eval.py`, stubbed model), and
  - the live grader (`scripts/eval_agent.py`, real nano-gpt/Llama model).

Each case is a user message plus the slots a correct extraction MUST contain.
Only the listed fields are graded; the extractor may fill others. Keep this list
growing — it is the project's yardstick for "did the model get better or worse?".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# message -> required slots. Bilingual (Arabic/English) on purpose.
EVAL_SET: list[dict[str, Any]] = [
    {"message": "I want 4 Gold tickets to Coldplay in Riyadh, nawaf@example.com",
     "expect": {"event_query": "coldplay", "city": "Riyadh", "quantity": 4,
                "category": "gold", "email": "nawaf@example.com"}},
    {"message": "book the Riyadh derby",
     "expect": {"event_query": "derby"}},
    {"message": "my email is dana@example.com",
     "expect": {"email": "dana@example.com"}},
    {"message": "vip please",
     "expect": {"category": "vip"}},
    {"message": "just 3",
     "expect": {"quantity": 3}},
    {"message": "seats G3 and G4",
     "expect": {"seat_ids": ["G3", "G4"]}},
    {"message": "what's on this weekend?",
     "expect": {"intent": "browse", "when": "weekend"}},
    {"message": "anything in Jeddah today?",
     "expect": {"intent": "browse", "city": "Jeddah", "when": "today"}},
    {"message": "is there a member discount?",
     "expect": {"intent": "ask"}},
    {"message": "how much is VAT?",
     "expect": {"intent": "ask"}},
    {"message": "yes, go ahead and confirm",
     "expect": {"intent": "confirm"}},
    {"message": "no, cancel that",
     "expect": {"intent": "cancel"}},
]


def slots_match(params: Any, expect: dict[str, Any]) -> bool:
    """True iff every expected field is present and equal (case-insensitive str)."""
    if params is None:
        return False
    got = params.model_dump()
    for key, want in expect.items():
        have = got.get(key)
        if isinstance(want, str) and isinstance(have, str):
            if have.lower() != want.lower():
                return False
        elif have != want:
            return False
    return True


def grade(extract_fn: Callable[[str], Any]) -> dict[str, Any]:
    """Run `extract_fn` over the whole set; return accuracy + per-case results."""
    results = []
    for case in EVAL_SET:
        params = extract_fn(case["message"])
        ok = slots_match(params, case["expect"])
        results.append({"message": case["message"], "ok": ok,
                        "expect": case["expect"], "got": params})
    correct = sum(1 for r in results if r["ok"])
    total = len(EVAL_SET)
    return {"correct": correct, "total": total,
            "accuracy": correct / total if total else 0.0, "results": results}
