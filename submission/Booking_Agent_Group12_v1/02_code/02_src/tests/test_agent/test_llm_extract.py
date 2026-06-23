"""Unit tests for the LLM slot extractor (`agent/llm.py`).

The repo-wide autouse fixture `_force_heuristic` (see conftest) disables the LLM
in `policy`/`answer` so the booking-flow tests stay offline. That left the entire
LLM path — `llm_extract`, JSON parsing, schema coercion, error handling —
**untested**. These tests cover it directly with a stubbed provider (no network),
so the nano-gpt/Llama integration has real regression coverage.
"""

from __future__ import annotations

import pytest

from booking_agent.agent import llm as llm_mod
from booking_agent.agent.llm import llm_extract


@pytest.fixture
def enable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the llm module believe a provider is configured (no real key/network)."""
    monkeypatch.setattr(llm_mod, "llm_available", lambda: True, raising=False)


def _stub_chat(payload: str):
    def _chat(system: str, user: str, max_tokens: int = 400) -> str:
        return payload
    return _chat


def test_parses_full_slots_and_uppercases_seats(enable_llm, monkeypatch) -> None:
    monkeypatch.setattr(
        llm_mod,
        "chat_complete",
        _stub_chat(
            '{"intent":"book","event_query":"coldplay","city":"Riyadh",'
            '"quantity":4,"category":"gold","seat_ids":["g3","g4","g5","g6"],'
            '"email":"nawaf@example.com"}'
        ),
    )
    p = llm_extract("4 gold for coldplay riyadh nawaf@example.com")
    assert p is not None
    assert (p.event_query, p.city, p.quantity, p.category) == ("coldplay", "Riyadh", 4, "gold")
    assert p.seat_ids == ["G3", "G4", "G5", "G6"]  # coerced to upper-case
    assert p.email == "nawaf@example.com"


def test_extracts_json_embedded_in_prose(enable_llm, monkeypatch) -> None:
    # Real models (esp. open-weights Llama) often wrap JSON in chatter.
    monkeypatch.setattr(
        llm_mod,
        "chat_complete",
        _stub_chat('Sure!\n{"intent":"browse","when":"weekend"}\nHope that helps.'),
    )
    p = llm_extract("what's on this weekend")
    assert p is not None
    assert p.intent == "browse"
    assert p.when == "weekend"


def test_ignores_unknown_keys_and_nulls(enable_llm, monkeypatch) -> None:
    monkeypatch.setattr(
        llm_mod,
        "chat_complete",
        _stub_chat('{"intent":"email","email":"x@y.com","nonsense":123,"category":null}'),
    )
    p = llm_extract("x@y.com")
    assert p is not None
    assert p.email == "x@y.com"
    assert p.category is None


def test_malformed_json_returns_none_and_records_error(enable_llm, monkeypatch) -> None:
    monkeypatch.setattr(llm_mod, "chat_complete", _stub_chat("no json here, sorry"))
    assert llm_extract("hello") is None
    assert llm_mod.LAST_ERROR  # a diagnostic string was recorded


def test_provider_exception_falls_back_to_none(enable_llm, monkeypatch) -> None:
    def _boom(system: str, user: str, max_tokens: int = 400) -> str:
        raise RuntimeError("nano-gpt 503")

    monkeypatch.setattr(llm_mod, "chat_complete", _boom)
    assert llm_extract("anything") is None
    assert "RuntimeError" in (llm_mod.LAST_ERROR or "")


def test_returns_none_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(llm_mod, "llm_available", lambda: False, raising=False)
    assert llm_extract("4 gold coldplay") is None


# --- Transient-error retry (503 overloaded / 429 rate-limited) --------------

def test_chat_complete_retries_transient_then_succeeds(monkeypatch) -> None:
    """A transient 503 is retried; the second attempt's result is returned."""
    import booking_agent.agent.llm as L

    calls = {"n": 0}

    def flaky(system: str, user: str, max_tokens: int = 600) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Error code: 503 - model is overloaded, please try again")
        return "ok"

    monkeypatch.setattr(L, "_chat_complete_once", flaky)
    monkeypatch.setattr(L.time, "sleep", lambda *_: None)  # no real backoff wait
    assert L.chat_complete("s", "u") == "ok"
    assert calls["n"] == 2


def test_chat_complete_does_not_retry_non_transient(monkeypatch) -> None:
    import booking_agent.agent.llm as L

    calls = {"n": 0}

    def boom(system: str, user: str, max_tokens: int = 600) -> str:
        calls["n"] += 1
        raise RuntimeError("Error code: 401 - invalid api key")

    monkeypatch.setattr(L, "_chat_complete_once", boom)
    monkeypatch.setattr(L.time, "sleep", lambda *_: None)
    import pytest
    with pytest.raises(RuntimeError):
        L.chat_complete("s", "u")
    assert calls["n"] == 1  # 401 is not transient → no retry


def test_is_transient_classification() -> None:
    from booking_agent.agent.llm import _is_transient

    assert _is_transient(RuntimeError("Error code: 503 - high demand"))
    assert _is_transient(RuntimeError("429 - you exceeded your current quota"))
    assert not _is_transient(RuntimeError("403 - permission denied"))
    assert not _is_transient(RuntimeError("invalid request"))
