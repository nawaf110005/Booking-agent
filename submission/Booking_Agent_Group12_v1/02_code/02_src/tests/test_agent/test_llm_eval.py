"""Offline regression run of the shared evaluation set (Week 6 pattern).

The dataset + scorer live in `booking_agent.agent.eval_dataset` so the SAME set
grades both this deterministic test (stubbed model) and the live model via
`scripts/eval_agent.py`. Swap the model, keep the yardstick.
"""

from __future__ import annotations

import json

import pytest

from booking_agent.agent import llm as llm_mod
from booking_agent.agent.eval_dataset import EVAL_SET, grade
from booking_agent.agent.llm import llm_extract


@pytest.fixture
def enable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod, "llm_available", lambda: True, raising=False)


def _stub_from(responses: dict[str, str]):
    def _chat(system: str, user: str, max_tokens: int = 400) -> str:
        return responses.get(user, "{}")
    return _chat


def test_dataset_is_nontrivial() -> None:
    # Guard against the set silently shrinking; it should cover many intents.
    assert len(EVAL_SET) >= 12
    intents = {c["expect"].get("intent") for c in EVAL_SET}
    assert {"browse", "ask", "confirm", "cancel"} <= intents


def test_eval_set_accuracy_meets_threshold(enable_llm, monkeypatch) -> None:
    # A correct model (stub echoes the gold labels) scores 100%.
    responses = {c["message"]: json.dumps(c["expect"]) for c in EVAL_SET}
    monkeypatch.setattr(llm_mod, "chat_complete", _stub_from(responses))

    report = grade(llm_extract)
    assert report["accuracy"] >= 0.95, report["accuracy"]


def test_harness_detects_a_regression(enable_llm, monkeypatch) -> None:
    # Prove the scorer discriminates: make the model hallucinate on ONE case.
    responses = {c["message"]: json.dumps(c["expect"]) for c in EVAL_SET}
    bad = EVAL_SET[0]
    responses[bad["message"]] = json.dumps({**bad["expect"], "category": "standing"})
    monkeypatch.setattr(llm_mod, "chat_complete", _stub_from(responses))

    report = grade(llm_extract)
    assert report["correct"] == report["total"] - 1
