"""Provider wiring: key resolution + OpenAI-compatible base URLs."""

from __future__ import annotations

from booking_agent.agent.llm import GEMINI_BASE_URL, NANOGPT_BASE_URL, openai_base_url
from booking_agent.config import Settings


def test_google_provider_resolves_google_key() -> None:
    s = Settings(booking_agent_provider="google", google_api_key="AIza-test")
    assert s.active_llm_key == "AIza-test"
    assert s.llm_configured is True


def test_provider_base_urls() -> None:
    assert openai_base_url("google") == GEMINI_BASE_URL
    assert openai_base_url("gemini") == GEMINI_BASE_URL
    assert openai_base_url("nanogpt") == NANOGPT_BASE_URL
    assert openai_base_url("openai") is None
    assert "generativelanguage.googleapis.com" in GEMINI_BASE_URL
