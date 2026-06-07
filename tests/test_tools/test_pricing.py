from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from booking_agent.db.enums import Category, MemberTier
from booking_agent.tools.errors import CapExceededError, NotFoundError, ValidationToolError
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing


def test_platinum_gold_four_matches_handcomputed(coldplay_riyadh_id: int, seeded: Session) -> None:
    """The headline example from the proposal: Gold 800 SAR, Platinum 15%, qty 4."""

    q = compute_quote(seeded, coldplay_riyadh_id, "gold", 4, MemberTier.PLATINUM)
    assert q.unit_price == 80_000        # 800.00 SAR
    assert q.unit_discount == 12_000     # 120.00
    assert q.net_unit_price == 68_000    # 680.00
    assert q.subtotal == 320_000         # 3,200.00
    assert q.discount_total == 48_000    # 480.00
    assert q.net_subtotal == 272_000     # 2,720.00
    assert q.vat == 40_800               # 408.00
    assert q.total == 312_800            # 3,128.00


def test_non_member_silver_two_no_discount(coldplay_riyadh_id: int, seeded: Session) -> None:
    q = compute_quote(seeded, coldplay_riyadh_id, "silver", 2, None)
    assert q.unit_price == 40_000
    assert q.discount_total == 0
    assert q.net_subtotal == 80_000
    assert q.vat == 12_000               # 15% of 80,000
    assert q.total == 92_000


@pytest.mark.parametrize(
    ("tier", "bps"),
    [
        (None, 0),
        (MemberTier.BRONZE, 500),
        (MemberTier.SILVER, 1000),
        (MemberTier.GOLD, 1200),
        (MemberTier.PLATINUM, 1500),
    ],
)
def test_discount_is_exact_per_tier(
    tier: MemberTier | None, bps: int, coldplay_riyadh_id: int, seeded: Session
) -> None:
    q = compute_quote(seeded, coldplay_riyadh_id, "vip", 1, tier)
    expected_discount = (q.unit_price * bps + 5_000) // 10_000
    assert q.unit_discount == expected_discount
    assert q.net_subtotal == q.subtotal - q.discount_total
    assert q.total == q.net_subtotal + q.vat


def test_vat_is_fifteen_percent_of_net(coldplay_riyadh_id: int, seeded: Session) -> None:
    q = compute_quote(seeded, coldplay_riyadh_id, "gold", 3, MemberTier.GOLD)
    assert q.vat == (q.net_subtotal * 1500 + 5_000) // 10_000


def test_cap_exceeded_non_member(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(CapExceededError) as exc:
        compute_quote(seeded, coldplay_riyadh_id, "gold", 5, None)  # cap 4
    assert exc.value.cap == 4


def test_cap_exceeded_platinum(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(CapExceededError):
        compute_quote(seeded, coldplay_riyadh_id, "gold", 9, MemberTier.PLATINUM)  # cap 8


def test_zero_quantity_rejected(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(ValidationToolError):
        compute_quote(seeded, coldplay_riyadh_id, "gold", 0, None)


def test_unknown_category(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        compute_quote(seeded, coldplay_riyadh_id, "platinum_lounge", 1, None)


def test_unknown_event(seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        compute_quote(seeded, 99999, "gold", 1, None)


def test_categories_listing_ordered_desc(coldplay_riyadh_id: int, seeded: Session) -> None:
    cats = get_categories_with_pricing(seeded, coldplay_riyadh_id, MemberTier.PLATINUM)
    assert [c.category for c in cats] == [
        Category.VIP,
        Category.GOLD,
        Category.SILVER,
        Category.STANDING,
    ]
    gold = next(c for c in cats if c.category == Category.GOLD)
    assert gold.base_price == 80_000
    assert gold.discounted_price == 68_000   # 15% off
    assert gold.available > 0
