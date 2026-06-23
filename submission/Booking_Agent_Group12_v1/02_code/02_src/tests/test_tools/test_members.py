from __future__ import annotations

from sqlalchemy.orm import Session

from booking_agent.db.enums import MemberTier
from booking_agent.tools.members import get_ticket_cap, lookup_member_by_email


def test_known_member_resolves_tier(seeded: Session) -> None:
    member = lookup_member_by_email(seeded, "nawaf@example.com")
    assert member.is_member is True
    assert member.tier == MemberTier.PLATINUM
    assert member.discount_bps == 1500
    assert member.ticket_cap == 8


def test_lookup_is_case_insensitive(seeded: Session) -> None:
    member = lookup_member_by_email(seeded, "  NAWAF@Example.COM ")
    assert member.is_member is True
    assert member.tier == MemberTier.PLATINUM


def test_unknown_email_is_non_member(seeded: Session) -> None:
    member = lookup_member_by_email(seeded, "stranger@nowhere.com")
    assert member.is_member is False
    assert member.tier is None
    assert member.discount_bps == 0
    assert member.ticket_cap == 4


def test_ticket_cap_by_tier() -> None:
    assert get_ticket_cap(MemberTier.PLATINUM) == 8
    assert get_ticket_cap(MemberTier.GOLD) == 6
    assert get_ticket_cap(MemberTier.SILVER) == 6
    assert get_ticket_cap(MemberTier.BRONZE) == 4
    assert get_ticket_cap(None) == 4
