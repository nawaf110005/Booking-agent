"""Cover the LLM branch of grounded Q&A (`agent/answer.py`).

The booking-flow suite forces the rule-based fallback, so the model-backed answer
path was untested. Here we enable it with a stub and verify (a) the model's reply
is used and (b) a provider failure degrades to the rule-based answer.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.agent import answer as answer_mod
from booking_agent.agent.answer import answer_question


def test_uses_llm_reply_when_available(seeded: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)
    monkeypatch.setattr(answer_mod, "chat_complete",
                        lambda system, user, **kw: "Bronze 5%, Gold 12% — share your email and I'll apply it.")
    out = answer_question(seeded, "is there a discount?")
    assert out == "Bronze 5%, Gold 12% — share your email and I'll apply it."


def test_falls_back_to_rules_on_provider_error(seeded: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answer_mod, "llm_available", lambda: True)

    def _boom(system: str, user: str, **kw) -> str:
        raise RuntimeError("provider down")

    monkeypatch.setattr(answer_mod, "chat_complete", _boom)
    out = answer_question(seeded, "is there a discount?")
    assert "%" in out or "member" in out.lower()  # deterministic FAQ fallback
