"""A small, offline **evaluation set** for the slot extractor.

This is the pattern from Week 6 of the bootcamp (Agent Evaluation → "Build an
Evaluation Set" / "Evaluate the Agent System"): a labelled dataset of inputs +
expected outputs, a scorer, and an accuracy threshold — run in CI.

It is deliberately model-agnostic. Here the provider is stubbed so the harness is
deterministic and needs no network/key. To grade the **real** nano-gpt/Llama
model, delete the stub and point `chat_complete` at the live provider; the
dataset and scorer are unchanged. That is the whole point of an eval harness:
swap the model, keep the yardstick.
"""

from __future__ import annotations

import json

import pytest

from booking_agent.agent import llm as llm_mod
from booking_agent.agent.llm import llm_extract

# Labelled cases: user message -> the slots a correct extraction should contain.
# (Only the listed fields are graded; others may be present.)
EVAL_SET: list[dict] = [
    {
        "message": "I want 4 Gold tickets to Coldplay in Riyadh, nawaf@example.com",
        "expect": {"event_query": "coldplay", "city": "Riyadh", "quantity": 4,
                   "category": "gold", "email": "nawaf@example.com"},
    },
    {
        "message": "تذكرتين فضي لكولدبلاي",  # Arabic: two silver for Coldplay
        "expect": {"event_query": "coldplay", "quantity": 2, "category": "silver"},
    },
    {
        "message": "what's on this weekend?",
        "expect": {"intent": "browse", "when": "weekend"},
    },
    {
        "message": "is there a member discount?",
        "expect": {"intent": "ask"},
    },
    {
        "message": "yes, go ahead and confirm",
        "expect": {"intent": "confirm"},
    },
    {
        "message": "seats G3 and G4 please",
        "expect": {"seat_ids": ["G3", "G4"]},
    },
]


def _stub_from(responses: dict[str, str]):
    """A fake model: returns the canned JSON for a message, else an empty object."""
    def _chat(system: str, user: str, max_tokens: int = 400) -> str:
        return responses.get(user, "{}")
    return _chat


def _slots_match(params, expect: dict) -> bool:
    """True iff every expected field matches (case-insensitive for strings)."""
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


@pytest.fixture
def enable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod, "llm_available", lambda: True, raising=False)


def test_eval_set_accuracy_meets_threshold(enable_llm, monkeypatch) -> None:
    # A correct model (stub echoes the gold labels) should score 100%.
    responses = {c["message"]: json.dumps(c["expect"]) for c in EVAL_SET}
    monkeypatch.setattr(llm_mod, "chat_complete", _stub_from(responses))

    correct = sum(_slots_match(llm_extract(c["message"]), c["expect"]) for c in EVAL_SET)
    accuracy = correct / len(EVAL_SET)
    assert accuracy >= 0.95, f"slot-extraction accuracy {accuracy:.0%} below threshold"


def test_harness_actually_detects_a_regression(enable_llm, monkeypatch) -> None:
    # Prove the scorer discriminates: make the model hallucinate on ONE case
    # (wrong category) and assert the measured accuracy drops by exactly one.
    responses = {c["message"]: json.dumps(c["expect"]) for c in EVAL_SET}
    bad = EVAL_SET[0]
    hallucinated = {**bad["expect"], "category": "vip"}  # gold -> vip
    responses[bad["message"]] = json.dumps(hallucinated)
    monkeypatch.setattr(llm_mod, "chat_complete", _stub_from(responses))

    correct = sum(_slots_match(llm_extract(c["message"]), c["expect"]) for c in EVAL_SET)
    assert correct == len(EVAL_SET) - 1
