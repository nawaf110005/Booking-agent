"""End-to-end booking flow through the multi-agent orchestrator (offline brain).

These exercise the orchestrator + specialist team the same way a user would, with
no API key: the deterministic offline brain drives the specialists, so the whole
booking — search → member → quote → seats → atomic hold → HITL confirm → pay →
ticket — runs offline and deterministically.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.agent import state as S
from booking_agent.agent.orchestrator import respond
from booking_agent.agent.state import ConversationState
from booking_agent.tools.payments import pay_booking


def _state() -> ConversationState:
    return ConversationState(session_id="test")


def test_full_chat_booking_to_ticket(seeded: Session) -> None:
    st = _state()

    r = respond(seeded, st, "Coldplay in Riyadh")
    assert st.event_id is not None
    assert r["step"] == S.NEED_EMAIL

    r = respond(seeded, st, "nawaf@example.com")
    assert st.email == "nawaf@example.com"
    assert r["step"] == S.CATEGORY_SELECTION
    assert r["member"]["is_member"] is True
    assert r["categories"]

    r = respond(seeded, st, "gold")
    assert r["step"] == S.NEED_QUANTITY

    r = respond(seeded, st, "4")
    assert st.quantity == 4
    assert r["step"] == S.SEAT_SELECTION
    assert r["seatmap_url"] is not None
    assert r["quote"]["total_sar"]

    r = respond(seeded, st, "G3, G4, G5, G6")
    assert r["step"] == S.AWAITING_CONFIRMATION
    assert r["confirmation"]["seats"] == ["G3", "G4", "G5", "G6"]
    assert r["confirmation"]["total_sar"] == "3,128.00 SAR"
    assert st.hold_token is not None

    r = respond(seeded, st, "confirm")
    assert r["step"] == S.PAYMENT
    assert r["payment"]["booking_id"] == st.booking_id

    ticket = pay_booking(seeded, st.booking_id)
    assert ticket["seats"] == ["G3", "G4", "G5", "G6"]
    assert ticket["qr_url"].endswith("/qr.png")


def test_one_shot_message_advances_to_seats(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "4 gold tickets for Coldplay in Riyadh, nawaf@example.com")
    # event + email + category + quantity all handled in one turn -> seat map.
    assert st.event_id is not None
    assert st.email == "nawaf@example.com"
    assert st.category == "gold"
    assert st.quantity == 4
    assert r["step"] == S.SEAT_SELECTION


def test_cap_enforced_for_guest(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "guest@example.com")  # non-member, cap 4
    respond(seeded, st, "gold")
    r = respond(seeded, st, "6")
    assert r["step"] == S.NEED_QUANTITY
    assert "up to" in r["reply"].lower()
    assert st.quantity is None


def test_event_disambiguation_then_city(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "Coldplay")  # two cities
    assert r["step"] == S.EVENT_SELECTION
    assert r["events"] is not None and len(r["events"]) == 2
    r = respond(seeded, st, "Riyadh")    # disambiguate by city
    assert st.event_id is not None
    assert r["step"] == S.NEED_EMAIL


def test_cancel_releases_hold(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    respond(seeded, st, "gold")
    respond(seeded, st, "2")
    respond(seeded, st, "G7, G8")
    assert st.hold_token is not None
    r = respond(seeded, st, "cancel")
    assert st.hold_token is None
    assert r["step"] == S.SEAT_SELECTION


def test_whats_on_this_weekend_filters(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "What's on this weekend?")
    assert r["step"] == S.EVENT_SELECTION
    assert r["events"] is not None
    titles = [e["title"] for e in r["events"]]
    # Only the seeded weekend event — NOT the whole catalog.
    assert "Riyadh Comedy Night" in titles
    assert "Coldplay — Music of the Spheres" not in titles
    assert st.event_id is None  # discovery shows cards, doesn't auto-select


def test_faq_question_answered_without_derailing(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "is there a discount?")
    assert "%" in r["reply"] or "member" in r["reply"].lower()
    assert st.event_id is None  # asking a question doesn't start a booking


def test_meta_question_about_project(seeded: Session) -> None:
    st = _state()
    r = respond(seeded, st, "who built you?")
    assert "nawaf" in r["reply"].lower() or "booking-agent" in r["reply"].lower()


def test_question_midflow_keeps_state(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    r = respond(seeded, st, "is there a discount?")  # ask mid-flow
    assert st.email == "nawaf@example.com"  # not derailed
    assert st.event_id is not None
    assert "%" in r["reply"] or "member" in r["reply"].lower()


def test_question_and_completion_at_payment_step(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    respond(seeded, st, "gold")
    respond(seeded, st, "4")
    respond(seeded, st, "G3, G4, G5, G6")
    assert respond(seeded, st, "confirm")["step"] == S.PAYMENT
    booking_id = st.booking_id

    # A question at the payment step is answered — not the canned "pay now".
    r = respond(seeded, st, "can you tell me about this event?")
    assert "pay now" not in r["reply"].lower()
    assert "coldplay" in r["reply"].lower()

    # Once paid (separate endpoint), the agent stops asking to pay.
    pay_booking(seeded, booking_id)
    r = respond(seeded, st, "ok")
    assert st.step == S.CONFIRMED
    assert "pay now" not in r["reply"].lower()

    # The user can then start a fresh booking.
    respond(seeded, st, "book the Riyadh derby")
    assert st.booking_id is None
    assert st.event_id is not None


def test_can_switch_event_before_hold(seeded: Session) -> None:
    # "nvm, I want the derby" mid-flow switches events instead of being ignored.
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    coldplay_id = st.event_id
    assert st.step == S.NEED_EMAIL
    r = respond(seeded, st, "actually I want the Riyadh derby")
    assert st.event_id is not None and st.event_id != coldplay_id
    assert "derby" in r["reply"].lower()
    assert st.step == S.NEED_EMAIL          # now asking email for the derby


def test_switching_event_resets_downstream_slots(seeded: Session) -> None:
    st = _state()
    respond(seeded, st, "Coldplay in Riyadh")
    respond(seeded, st, "nawaf@example.com")
    respond(seeded, st, "gold")             # category set on Coldplay
    assert st.category == "gold"
    respond(seeded, st, "actually the Riyadh derby")
    assert st.category is None               # category cleared on switch
    assert st.email == "nawaf@example.com"   # identity kept


def test_can_start_a_new_event_right_after_payment(seeded: Session) -> None:
    from booking_agent.tools.events import get_event_details

    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "2", "G3, G4", "confirm"]:
        respond(seeded, st, m)
    pay_booking(seeded, st.booking_id)
    r = respond(seeded, st, "i need the derby event")    # new event in the same breath
    assert st.booking_id is None                          # old booking cleared
    assert st.event_id is not None
    assert "Derby" in get_event_details(seeded, st.event_id).title  # switched to the derby
    assert st.email == "nawaf@example.com"                # remembered the buyer
    assert "paid and your ticket is issued" not in r["reply"]  # didn't just announce completion


def test_can_switch_to_a_genre_mid_flow(seeded: Session) -> None:
    # "changed my mind, I want musical events" drops the current (sports) event and
    # browses the music genre instead of staying stuck on the derby.
    st = _state()
    respond(seeded, st, "Riyadh derby")
    assert st.event_id is not None
    r = respond(seeded, st, "i changed my mind i need musical events")
    assert st.event_id is None                                   # dropped the derby
    titles = [e["title"] for e in (r["events"] or [])]
    assert any("Coldplay" in t or "Soundstorm" in t for t in titles)
    assert not any("Derby" in t for t in titles)                 # not the sports event


def test_can_change_quantity_before_hold(seeded: Session) -> None:
    # #1 slot correction: a new quantity before seats are held updates and re-quotes.
    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "4"]:
        respond(seeded, st, m)
    assert st.quantity == 4 and st.step == S.SEAT_SELECTION
    r = respond(seeded, st, "2 tickets")
    assert st.quantity == 2
    assert r["quote"]["quantity"] == 2          # re-quoted for the new quantity


def test_can_change_category_before_hold(seeded: Session) -> None:
    # #1 slot correction: switching category before holding seats is honoured.
    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "vip", "2"]:
        respond(seeded, st, m)
    assert st.category == "vip"
    r = respond(seeded, st, "actually gold")
    assert st.category == "gold"
    assert r["quote"]["category"] == "gold"


def test_taken_seats_give_a_clear_error(seeded: Session) -> None:
    # #6: G1/G2 are seeded SOLD for the Coldplay Riyadh show → clear, helpful error.
    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "2"]:
        respond(seeded, st, m)
    r = respond(seeded, st, "G1, G2")
    assert st.hold_token is None
    assert r["step"] == S.SEAT_SELECTION
    assert "sorry" in r["reply"].lower()
    assert "other seat" in r["reply"].lower()


def test_confirmation_reply_has_grounded_summary(seeded: Session) -> None:
    # #2: the confirmation prose is a deterministic, grounded one-liner (no LLM).
    st = _state()
    r = None
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "2", "G3, G4"]:
        r = respond(seeded, st, m)
    assert r["step"] == S.AWAITING_CONFIRMATION
    assert "2×" in r["reply"] and "Gold" in r["reply"]
    assert "G3, G4" in r["reply"] and "Coldplay" in r["reply"]


def _book_to_confirm(db) -> ConversationState:
    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "2", "G3, G4"]:
        respond(db, st, m)
    assert st.step == S.AWAITING_CONFIRMATION
    return st


def test_confirm_with_no_active_booking_is_graceful(seeded: Session) -> None:
    # "confirm" in a fresh/stale session plainly says there's nothing to confirm yet.
    st = _state()
    r = respond(seeded, st, "confirm")
    assert "active booking" in r["reply"].lower()
    assert "moyasar" not in r["reply"].lower()


def test_change_request_at_gate_gives_accurate_guidance(seeded: Session) -> None:
    # #5: "can i change it?" at the gate → accurate cancel-to-edit guidance, hold intact.
    st = _book_to_confirm(seeded)
    r = respond(seeded, st, "can i change it?")
    assert st.step == S.AWAITING_CONFIRMATION       # still at the gate
    assert st.hold_token is not None                # seats not released
    assert r["suggestions"] == ["confirm", "cancel"]
    assert "cancel" in r["reply"].lower()


def test_question_at_confirmation_keeps_flow(seeded: Session) -> None:
    st = _book_to_confirm(seeded)
    r = respond(seeded, st, "how does payment work?")        # a question, not an action
    assert st.step == S.AWAITING_CONFIRMATION                # still booking
    assert r["suggestions"] == ["confirm", "cancel"]         # flow-appropriate chips
    assert "moyasar" not in r["reply"].lower()


def test_unknown_event_offers_similar_genre_then_shows_on_yes(seeded: Session, monkeypatch) -> None:
    # "Justin Bieber" isn't in the catalog. Instead of dumping everything, the agent
    # infers it's a concert, OFFERS similar events, and only shows them after a yes.
    from booking_agent.agent import orchestrator as orch

    monkeypatch.setattr(orch, "infer_genre", lambda q: "concert")
    st = _state()
    r = respond(seeded, st, "tickets for justin bieber")
    assert st.pending_suggestion == "concert"          # offer is pending
    assert r["events"] is None                          # did NOT dump the catalog yet
    assert "don't have" in r["reply"].lower()
    assert "Yes, show me" in r["suggestions"]

    r2 = respond(seeded, st, "yes")                     # user accepts
    assert st.pending_suggestion is None
    titles = [e["title"] for e in r2["events"]]
    assert any("Coldplay" in t for t in titles)         # a concert is shown
    assert not any("Derby" in t for t in titles)        # sports is filtered out


def test_browse_for_unknown_act_offers_genre_not_catalog(seeded: Session, monkeypatch) -> None:
    # "dua lipa events?" routes to browse (the word "events"), but it's a named act we
    # don't carry — offer a similar genre instead of dumping the whole catalog.
    from booking_agent.agent import orchestrator as orch
    from booking_agent.agent.schemas import BookingParams

    monkeypatch.setattr(orch, "llm_available", lambda: True)
    monkeypatch.setattr(orch, "llm_extract", lambda m: BookingParams(intent="browse", event_query="dua lipa"))
    monkeypatch.setattr(orch, "infer_genre", lambda q: "concert")
    st = _state()
    r = respond(seeded, st, "dua lipa events?")
    assert st.pending_suggestion == "concert"
    assert r["events"] is None                       # offered, did NOT dump the catalog
    assert "don't have" in r["reply"].lower()


def test_unknown_event_offer_can_be_declined(seeded: Session, monkeypatch) -> None:
    from booking_agent.agent import orchestrator as orch

    monkeypatch.setattr(orch, "infer_genre", lambda q: "concert")
    st = _state()
    respond(seeded, st, "tickets for justin bieber")
    r = respond(seeded, st, "no thanks")
    assert st.pending_suggestion is None
    assert r["events"] is None
    assert "no worries" in r["reply"].lower() or "tell me" in r["reply"].lower()


def test_unknown_event_with_no_inferable_genre_falls_back_to_catalog(seeded: Session) -> None:
    # Offline (no genre inference): keep the existing acknowledge-and-show-catalog behaviour.
    st = _state()
    r = respond(seeded, st, "I need ticket for jb")
    assert st.pending_suggestion is None
    assert r["events"]                                  # catalog shown, not an empty reply
    assert "jb" in r["reply"].lower() or "couldn't find" in r["reply"].lower()


def test_card_click_selects_event_even_if_model_does_nothing(seeded: Session, monkeypatch) -> None:
    # Clicking "Select" sends "#<id>". That UI action must resolve deterministically
    # even when the LLM specialist returns no tool call (the real-world failure seen
    # where "#6" fell back to the greeting + catalog).
    from booking_agent.agent import orchestrator as orch
    from booking_agent.agent import tool_agent

    monkeypatch.setattr(orch, "llm_available", lambda: True)
    monkeypatch.setattr(orch, "llm_extract", lambda m: None)
    monkeypatch.setattr(tool_agent, "default_complete",
                        lambda messages, tools: {"content": "ok", "tool_calls": []})
    st = _state()
    r = respond(seeded, st, "#1")                    # a card click on event id 1
    assert st.event_id == 1
    assert r["step"] == S.NEED_EMAIL                 # selected and moved on, not the greeting


def test_email_my_ticket_is_honestly_declined(seeded: Session) -> None:
    # Email/SMS delivery isn't a feature → say so clearly + point to the QR, never dodge.
    st = _state()
    for m in ["Coldplay in Riyadh", "nawaf@example.com", "gold", "2", "G3, G4", "confirm"]:
        respond(seeded, st, m)
    pay_booking(seeded, st.booking_id)
    respond(seeded, st, "ok")                       # -> CONFIRMED
    r = respond(seeded, st, "can you send it to my email")
    reply = r["reply"].lower()
    assert ("doesn't email" in reply or "does not email" in reply or "download" in reply)
    assert "qr" in reply
    assert st.booking_id is not None                # didn't blow away their booking


def test_typo_event_question_resolves_not_faq(seeded: Session) -> None:
    """A misspelled event question must find the event, never an unrelated FAQ."""
    st = _state()
    r = respond(seeded, st, "dose cold play will be here in saudi")
    assert "payment" not in r["reply"].lower()
    # resolves Coldplay → either disambiguation cards or a single match moving forward
    assert r["events"] or st.event_id is not None
