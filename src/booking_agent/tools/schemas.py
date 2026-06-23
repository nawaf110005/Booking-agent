from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from booking_agent.db.enums import BookingStatus, Category, MemberTier, SeatStatus
from booking_agent.tools.money import sar_str


class _DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# -- Events ------------------------------------------------------------------


class EventOut(_DTO):
    id: int
    title: str
    starts_at: datetime
    venue: str
    city: str
    image_url: str | None = None
    detail_url: str | None = None
    status: str
    description: str | None = None


# -- Members -----------------------------------------------------------------


class MemberOut(_DTO):
    email: str
    name: str | None = None
    tier: MemberTier | None = None
    discount_bps: int = 0
    ticket_cap: int = 4
    is_member: bool = False

    @property
    def discount_label(self) -> str:
        return f"{self.discount_bps / 100:.0f}%"


# -- Pricing -----------------------------------------------------------------


class CategoryPrice(_DTO):
    category: Category
    base_price: int          # halalas
    discounted_price: int    # halalas (== base_price when no discount)
    available: int
    total: int
    currency: str = "SAR"

    @property
    def base_sar(self) -> str:
        return sar_str(self.base_price, self.currency)

    @property
    def discounted_sar(self) -> str:
        return sar_str(self.discounted_price, self.currency)


class Quote(_DTO):
    """Itemised, exact quote. All money fields are integer halalas."""

    event_id: int
    event_title: str
    category: Category
    quantity: int
    tier: MemberTier | None = None
    unit_price: int
    unit_discount: int
    net_unit_price: int
    subtotal: int
    discount_total: int
    net_subtotal: int
    vat: int
    total: int
    currency: str = "SAR"

    def summary_lines(self) -> list[str]:
        """Human-readable lines for the confirmation card / CLI."""

        lines = [
            f"{self.quantity}× {self.category.value.title()} @ {sar_str(self.unit_price, self.currency)}"
        ]
        if self.discount_total:
            lines.append(f"Member discount: -{sar_str(self.discount_total, self.currency)}")
        lines.append(f"Subtotal: {sar_str(self.net_subtotal, self.currency)}")
        lines.append(f"VAT 15%: {sar_str(self.vat, self.currency)}")
        lines.append(f"Total: {sar_str(self.total, self.currency)}")
        return lines


# -- Seats / holds -----------------------------------------------------------


class SeatInfo(_DTO):
    seat_id: str
    category: Category
    status: SeatStatus
    base_price: int


class HoldResult(_DTO):
    token: str
    event_id: int
    seat_ids: list[str]
    email: str
    expires_at: datetime
    ttl_minutes: int


# -- Bookings ----------------------------------------------------------------


class BookingOut(_DTO):
    id: int
    buyer_email: str
    event_id: int
    category: Category
    quantity: int
    status: BookingStatus
    subtotal: int
    discount_total: int
    vat: int
    total: int
    currency: str
    seat_ids: list[str] = Field(default_factory=list)
