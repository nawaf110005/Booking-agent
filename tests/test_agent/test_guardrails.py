"""Unit tests for the safety guardrails (Week 6: Guardrails & Safety)."""

from __future__ import annotations

from booking_agent.agent import guardrails as g
from booking_agent.agent import state as S


def test_payment_allowed_only_at_confirmation_gate() -> None:
    assert g.can_issue_payment(S.AWAITING_CONFIRMATION) is True
    for step in (S.GREETING, S.EVENT_SELECTION, S.NEED_EMAIL, S.CATEGORY_SELECTION,
                 S.NEED_QUANTITY, S.SEAT_SELECTION, S.PAYMENT, S.CONFIRMED):
        assert g.can_issue_payment(step) is False


def test_cap_predicates() -> None:
    assert g.exceeds_cap(6, 4) is True
    assert g.exceeds_cap(4, 4) is False
    assert g.clamp_to_cap(9, 8) == 8
    assert g.clamp_to_cap(2, 8) == 2


def test_valid_quantity() -> None:
    assert g.is_valid_quantity(1)
    assert g.is_valid_quantity(8)
    assert not g.is_valid_quantity(0)
    assert not g.is_valid_quantity(-3)
    assert not g.is_valid_quantity(True)  # bools are not quantities
