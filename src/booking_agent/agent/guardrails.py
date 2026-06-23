"""Centralized safety guardrails.

Pure, dependency-light predicates that the agent enforces. Keeping them in one
module makes the safety rules (a) unit-testable in isolation and (b) auditable in
one place — "can the agent do the dangerous thing?". The headline is the
human-in-the-loop payment gate (Constitution Principle I).
"""

from __future__ import annotations

from booking_agent.agent import state as S


def can_issue_payment(step: str) -> bool:
    """A payment URL/booking may be created ONLY from the confirmation gate."""
    return step == S.AWAITING_CONFIRMATION


def exceeds_cap(quantity: int, cap: int) -> bool:
    """True if the requested quantity is above the member tier's ticket cap."""
    return quantity > cap


def clamp_to_cap(quantity: int, cap: int) -> int:
    """The largest bookable quantity at or below the cap."""
    return min(quantity, cap)


def is_valid_quantity(quantity: int) -> bool:
    """Quantities must be positive integers."""
    return isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0
