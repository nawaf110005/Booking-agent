"""Tests for opt-in dynamic reply phrasing (`agent/compose.py`).

Default-off means the FSM's wording (and the rest of the suite) is unaffected;
when enabled the prose is rephrased but a provider failure never breaks a turn.
"""

from __future__ import annotations

import pytest

from booking_agent.agent import compose as compose_mod
from booking_agent.agent.compose import compose_reply


def test_passthrough_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if a model is "available", the default (flag off) is byte-identical text.
    monkeypatch.setattr(compose_mod, "llm_available", lambda: True)
    monkeypatch.setattr(compose_mod.settings, "booking_agent_dynamic_replies", False, raising=False)
    text = "Pick 2 Gold seats like G3, G4."
    assert compose_reply(text) == text


def test_rephrases_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compose_mod, "llm_available", lambda: True)
    monkeypatch.setattr(compose_mod.settings, "booking_agent_dynamic_replies", True, raising=False)
    monkeypatch.setattr(compose_mod, "chat_complete",
                        lambda s, u, max_tokens=200: "Sure — grab 2 Gold seats, e.g. G3, G4!")
    assert compose_reply("Pick 2 Gold seats like G3, G4.") == "Sure — grab 2 Gold seats, e.g. G3, G4!"


def test_falls_back_to_original_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compose_mod, "llm_available", lambda: True)
    monkeypatch.setattr(compose_mod.settings, "booking_agent_dynamic_replies", True, raising=False)

    def _boom(system: str, user: str, max_tokens: int = 200) -> str:
        raise RuntimeError("provider down")

    monkeypatch.setattr(compose_mod, "chat_complete", _boom)
    assert compose_reply("hello") == "hello"
