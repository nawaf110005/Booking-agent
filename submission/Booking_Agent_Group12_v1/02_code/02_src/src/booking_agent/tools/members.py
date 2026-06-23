"""Membership tools: email lookup and ticket-cap resolution."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking_agent.db.enums import NON_MEMBER_CAP, MemberTier, cap_for
from booking_agent.db.models import Member
from booking_agent.tools.schemas import MemberOut


def lookup_member_by_email(session: Session, email: str) -> MemberOut:
    """Resolve a buyer's membership by email.

    Returns a non-member result (discount 0, cap 4) for unknown emails — never
    raises — so the agent can always proceed to a quote.
    """

    normalized = (email or "").strip().lower()
    member = session.execute(
        select(Member).where(func.lower(Member.email) == normalized)
    ).scalar_one_or_none()

    if member is None:
        return MemberOut(
            email=normalized,
            name=None,
            tier=None,
            discount_bps=0,
            ticket_cap=NON_MEMBER_CAP,
            is_member=False,
        )

    return MemberOut(
        email=member.email,
        name=member.name,
        tier=member.tier,
        discount_bps=member.discount_bps,
        ticket_cap=member.ticket_cap,
        is_member=True,
    )


def get_ticket_cap(tier: MemberTier | None) -> int:
    """Max tickets per booking for a tier; non-member (None) -> 4."""

    return cap_for(tier)
