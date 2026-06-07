from __future__ import annotations

from booking_agent.agent.extract import heuristic_extract


def test_extract_full_combo() -> None:
    p = heuristic_extract("I want 4 gold tickets for Coldplay in Riyadh, nawaf@example.com")
    assert p.quantity == 4
    assert p.category == "gold"
    assert p.city == "Riyadh"
    assert p.event_query == "coldplay"
    assert p.email == "nawaf@example.com"


def test_extract_seat_ids() -> None:
    p = heuristic_extract("G3, G4, G5")
    assert p.seat_ids == ["G3", "G4", "G5"]
    assert p.quantity is None  # seat tokens are not quantities


def test_extract_card_click_hash_id() -> None:
    assert heuristic_extract("#3").event_id == 3


def test_extract_bare_quantity() -> None:
    assert heuristic_extract("4").quantity == 4
    assert heuristic_extract("two").quantity == 2


def test_extract_category_word() -> None:
    assert heuristic_extract("gold").category == "gold"


def test_extract_intents() -> None:
    assert heuristic_extract("confirm").intent == "confirm"
    assert heuristic_extract("yes please").intent == "confirm"
    assert heuristic_extract("cancel").intent == "cancel"
    assert heuristic_extract("what's on this weekend?").intent == "browse"


def test_email_not_parsed_as_seats() -> None:
    p = heuristic_extract("a1@example.com")
    assert p.email == "a1@example.com"
    assert p.seat_ids == []


def test_ask_intent_for_faq() -> None:
    assert heuristic_extract("is there a discount?").intent == "ask"
    assert heuristic_extract("who built you?").intent == "ask"
    assert heuristic_extract("how does this work?").intent == "ask"


def test_ask_intent_for_type_question() -> None:
    assert heuristic_extract("what football matches this week?").intent == "ask"


def test_booking_inputs_are_not_ask() -> None:
    assert heuristic_extract("gold").intent != "ask"
    assert heuristic_extract("G3, G4").intent != "ask"
    assert heuristic_extract("what's on this weekend?").intent == "browse"
