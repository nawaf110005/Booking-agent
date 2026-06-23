"""Verify the Nano-GPT (Llama) wiring against the live API.

Runs on YOUR machine (the sandbox can't reach nano-gpt.com). It:
  1. lists the Llama model IDs your key can call (so you can pick an exact one),
  2. smoke-tests a one-line chat completion with the configured model,
  3. exercises the agent's own `llm_extract` on a sample message.

Usage:
    uv run python scripts/nanogpt_check.py
    # or
    python scripts/nanogpt_check.py
"""

from __future__ import annotations

import sys

from booking_agent.agent.llm import NANOGPT_BASE_URL, chat_complete, llm_extract
from booking_agent.config import settings


def main() -> int:
    provider = settings.booking_agent_provider
    key = settings.active_llm_key
    print(f"provider   = {provider}")
    print(f"model      = {settings.booking_agent_model}")
    print(f"key set    = {bool(key)} ({'…' + key[-4:] if key else 'MISSING'})")
    if not key:
        print("\nNo key resolved. Set NANOGPT_API_KEY in .env and "
              "BOOKING_AGENT_PROVIDER=nanogpt.")
        return 1

    # 1) Discover callable Llama IDs (canonical, provider-prefixed).
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=NANOGPT_BASE_URL)
        ids = sorted(m.id for m in client.models.list().data)
        llama = [i for i in ids if "llama" in i.lower()]
        print(f"\n{len(ids)} models available; {len(llama)} Llama:")
        for i in llama[:40]:
            mark = "  <- configured" if i == settings.booking_agent_model else ""
            print(f"  {i}{mark}")
        if settings.booking_agent_model not in ids:
            print(f"\n[warn] '{settings.booking_agent_model}' is not in the list — "
                  "set BOOKING_AGENT_MODEL to one of the IDs above.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[models] could not list models: {type(exc).__name__}: {exc}")

    # 2) Smoke-test a chat completion with the configured model.
    try:
        reply = chat_complete("You are a test.", "Reply with the single word: ready", max_tokens=8)
        print(f"\n[chat] OK -> {reply!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[chat] FAILED: {type(exc).__name__}: {exc}")
        print("       If this is a 404/model error, pick a model ID from the list above.")
        return 2

    # 3) Exercise the agent's slot extractor through the LLM.
    sample = "4 gold tickets for Coldplay in Riyadh, nawaf@example.com"
    params = llm_extract(sample)
    print(f"\n[extract] {sample!r}\n          -> {params}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
