"""LLM-as-judge scorer for free-text replies (Week 2: *Optimizing LLM-as-a-Judge*).

The slot eval (`eval_dataset.py`) grades structured extraction; this grades the
*quality* of a natural-language reply (helpful? on-topic? grounded?) on a 1–5
scale. `complete` is injectable (a `(system, user) -> str` callable like
`llm.chat_complete`), so it's offline-testable with a stubbed judge.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

JUDGE_SYSTEM = (
    "You are a strict evaluator of a ticket-booking assistant. Score the assistant "
    "REPLY for the user QUESTION against the CRITERIA from 1 (poor) to 5 (excellent). "
    "Penalise anything off-topic, unhelpful, or not grounded in real catalog/policy. "
    'Return ONLY JSON: {"score": <int 1-5>, "reason": "<one short sentence>"}.'
)


def judge_reply(question: str, reply: str, criteria: str,
                complete: Callable[[str, str], str]) -> dict:
    """Return {'score': int 0-5, 'reason': str}. score 0 means the judge failed."""
    user = f"QUESTION: {question}\nREPLY: {reply}\nCRITERIA: {criteria}"
    try:
        raw = complete(JUDGE_SYSTEM, user)
    except Exception as exc:
        return {"score": 0, "reason": f"judge error: {type(exc).__name__}"}
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return {"score": 0, "reason": "judge returned no JSON"}
    try:
        data = json.loads(match.group(0))
        score = int(data.get("score", 0))
        return {"score": max(0, min(5, score)), "reason": str(data.get("reason", ""))}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"score": 0, "reason": "unparseable judge output"}
