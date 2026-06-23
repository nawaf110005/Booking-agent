"""Session store: stable ids + persistence so the chat never 'starts over'."""

from __future__ import annotations

from booking_agent.agent.state import ConversationState
from booking_agent.agent.store import SessionStore


def test_get_or_create_honours_client_id() -> None:
    # The real bug: an unknown id (e.g. after a restart) used to mint a NEW random
    # session every turn. It must instead create-under-that-id and then reuse it.
    store = SessionStore()
    s1 = store.get_or_create("abc")
    assert s1.session_id == "abc"
    s1.event_id = 1
    s2 = store.get_or_create("abc")          # same id next turn
    assert s2 is s1                           # reused, not a fresh session
    assert s2.event_id == 1                    # state accumulated, didn't start over


def test_no_id_creates_fresh_session() -> None:
    store = SessionStore()
    a = store.get_or_create(None)
    b = store.get_or_create(None)
    assert a.session_id != b.session_id


def test_sessions_survive_a_restart(tmp_path, monkeypatch) -> None:
    # Persisted to disk → a brand-new store instance (simulating a backend restart)
    # resumes the in-progress booking instead of starting over.
    from booking_agent.config import settings

    monkeypatch.setattr(settings, "booking_agent_persist_sessions", True, raising=False)

    store1 = SessionStore(persist_dir=tmp_path)
    st = store1.get_or_create("sess-1")
    st.event_id = 7
    st.email = "nawaf@example.com"
    st.category = "gold"
    store1.save(st)

    store2 = SessionStore(persist_dir=tmp_path)   # fresh process, empty memory
    resumed = store2.get_or_create("sess-1")
    assert resumed.event_id == 7
    assert resumed.email == "nawaf@example.com"
    assert resumed.category == "gold"


def test_persistence_off_writes_nothing(tmp_path, monkeypatch) -> None:
    from booking_agent.config import settings

    monkeypatch.setattr(settings, "booking_agent_persist_sessions", False, raising=False)
    store = SessionStore(persist_dir=tmp_path)
    store.save(ConversationState(session_id="x"))
    assert not list(tmp_path.iterdir())           # nothing written when disabled
