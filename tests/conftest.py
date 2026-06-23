from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from booking_agent.db import models  # noqa: F401  (register models on Base)
from booking_agent.db.base import Base
from booking_agent.db.seed import seed_demo


@pytest.fixture(autouse=True)
def _force_heuristic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests offline & deterministic: the agent uses the rule-based
    extractor even when a real LLM key is configured in .env."""
    from booking_agent.config import settings

    monkeypatch.setattr("booking_agent.agent.orchestrator.llm_available", lambda: False, raising=False)
    monkeypatch.setattr("booking_agent.agent.answer.llm_available", lambda: False, raising=False)
    monkeypatch.setattr("booking_agent.agent.compose.llm_available", lambda: False, raising=False)
    monkeypatch.setattr(settings, "booking_agent_mode", "multi_agent", raising=False)
    monkeypatch.setattr(settings, "booking_agent_persist_sessions", False, raising=False)


@pytest.fixture
def engine() -> Iterator[Engine]:
    # StaticPool keeps a single shared in-memory connection so the schema and
    # data persist across sessions within one test.
    eng = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def seeded(session: Session) -> Session:
    seed_demo(session)
    session.commit()
    return session


@pytest.fixture
def coldplay_riyadh_id(seeded: Session) -> int:
    from booking_agent.tools.events import search_events

    events = search_events(seeded, "Coldplay", city="Riyadh")
    assert events, "seed should contain a Coldplay Riyadh event"
    return events[0].id
