from __future__ import annotations

from enum import Enum


class Category(str, Enum):
    """Ticket categories, priced per event."""

    VIP = "vip"
    GOLD = "gold"
    SILVER = "silver"
    STANDING = "standing"


class SeatStatus(str, Enum):
    AVAILABLE = "available"
    HELD = "held"
    SOLD = "sold"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    SOLD_OUT = "sold_out"
    CANCELLED = "cancelled"


class BookingStatus(str, Enum):
    HELD = "held"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class HoldStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    CONVERTED = "converted"  # hold became a paid booking


class PaymentStatus(str, Enum):
    INITIATED = "initiated"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class MemberTier(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class Sentiment(str, Enum):
    """Per-turn classification used by the personalisation/sentiment slice (F006)."""

    ENGAGED = "engaged"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"


# --- Membership economics (Requirements.md §10) -----------------------------
# Discounts are integer basis points (1500 = 15%) so all money math stays exact.

NON_MEMBER_CAP = 4
NON_MEMBER_DISCOUNT_BPS = 0

TIER_DISCOUNT_BPS: dict[MemberTier, int] = {
    MemberTier.BRONZE: 500,    # 5%
    MemberTier.SILVER: 1000,   # 10%
    MemberTier.GOLD: 1200,     # 12%
    MemberTier.PLATINUM: 1500, # 15%
}

TIER_CAP: dict[MemberTier, int] = {
    MemberTier.BRONZE: 4,
    MemberTier.SILVER: 6,
    MemberTier.GOLD: 6,
    MemberTier.PLATINUM: 8,
}


def discount_bps_for(tier: MemberTier | None) -> int:
    """Discount in basis points for a tier; non-member (None) -> 0."""

    return TIER_DISCOUNT_BPS.get(tier, NON_MEMBER_DISCOUNT_BPS) if tier else NON_MEMBER_DISCOUNT_BPS


def cap_for(tier: MemberTier | None) -> int:
    """Max tickets per booking for a tier; non-member (None) -> 4."""

    return TIER_CAP.get(tier, NON_MEMBER_CAP) if tier else NON_MEMBER_CAP
