"""Typed responses (FR-010), LLM-as-judge (Week 2), graph/planner (FR-014)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.graph import build_graph, plan_booking
from booking_agent.agent.judge import judge_reply
from booking_agent.agent.policy import respond
from booking_agent.agent.responses import AgentResponse, infer_response_type
from booking_agent.agent.state import ConversationState


# --- typed responses (FR-010) --------------------------------------------- #

def test_infer_response_type() -> None:
    assert infer_response_type({"payment": {"x": 1}}) == "payment"
    assert infer_response_type({"confirmation": {"x": 1}}) == "confirmation"
    assert infer_response_type({"quote": {}, "seatmap_url": "/x"}) == "seatmap"
    assert infer_response_type({"events": [1]}) == "event_cards"
    assert infer_response_type({}) == "message"


def test_respond_payload_is_typed(seeded: Session) -> None:
    st = ConversationState(session_id="r1")
    r = respond(seeded, st, "Coldplay in Riyadh")
    assert r["response_type"] == "message"
    model = AgentResponse(**r)          # validates without raising
    assert model.step == r["step"] == S.NEED_EMAIL


def test_event_cards_get_typed(seeded: Session) -> None:
    st = ConversationState(session_id="r2")
    r = respond(seeded, st, "show me concerts")
    assert r["response_type"] == "event_cards"


# --- LLM-as-judge (Week 2) ------------------------------------------------ #

def test_judge_parses_and_clamps() -> None:
    out = judge_reply("is there a discount?", "Members get 5–15% off.", "helpful, grounded",
                      lambda system, user: '{"score": 4, "reason": "helpful and grounded"}')
    assert out["score"] == 4 and "helpful" in out["reason"]
    assert judge_reply("q", "a", "c", lambda s, u: '{"score": 9}')["score"] == 5


def test_judge_handles_bad_output() -> None:
    assert judge_reply("q", "a", "c", lambda s, u: "not json")["score"] == 0

    def boom(system, user):
        raise RuntimeError("down")

    assert judge_reply("q", "a", "c", boom)["score"] == 0


# --- graph adapter + planner (FR-014; Week 5) ----------------------------- #

def test_plan_booking_decomposition() -> None:
    plan = plan_booking("book coldplay")
    assert plan[0] == "search_catalog"
    assert "confirm_hitl" in plan
    assert plan[-1] == "fulfil_ticket"


def test_graph_invoke_routes_a_turn(seeded: Session) -> None:
    g = build_graph()
    st = ConversationState(session_id="g1")
    r = g.invoke(seeded, st, "Coldplay in Riyadh")
    assert r["step"] == S.NEED_EMAIL


# --- agent memory + multi-agent (Week 5) ---------------------------------- #

def test_long_term_memory_record_and_recall() -> None:
    from booking_agent.agent.memory import MEMORY

    MEMORY.record("fan@example.com", "Coldplay — 2× gold")
    assert "Coldplay — 2× gold" in MEMORY.recall("fan@example.com")
    assert MEMORY.recall("stranger@example.com") == []


def test_recommender_and_router(seeded: Session) -> None:
    from booking_agent.agent.graph import MultiAgentGraph, recommend_events, route_intent

    recs = recommend_events(seeded, ["concert"])
    assert recs and all("Derby" not in e.title for e in recs)
    assert route_intent("recommend") == "recommender"
    assert route_intent("book") == "booking"
    out = MultiAgentGraph().invoke(seeded, ConversationState(session_id="ma"), "suggest", intent="recommend")
    assert out["agent"] == "recommender" and out["recommendations"]


def test_booking_is_remembered_after_confirm(seeded: Session) -> None:
    from booking_agent.agent.memory import MEMORY

    st = ConversationState(session_id="mem1")
    for msg in ("Coldplay in Riyadh", "fanmem@example.com", "gold", "4", "G3, G4, G5, G6", "confirm"):
        respond(seeded, st, msg)
    assert any("Coldplay" in s for s in MEMORY.recall("fanmem@example.com"))
