from __future__ import annotations

from pydantic import BaseModel, Field


class BookingParams(BaseModel):
    """Structured slots extracted from a user message.

    Every field is optional — the agent fills what it can each turn and asks
    for the rest. `intent` captures the verb; the slots capture the nouns.
    """

    intent: str | None = None  # book|select_event|email|category|quantity|seats|confirm|cancel|browse|greet|ask
    event_query: str | None = None
    city: str | None = None
    when: str | None = None  # weekend|today|tomorrow|week
    event_id: int | None = None
    email: str | None = None
    category: str | None = None  # vip|gold|silver|standing
    quantity: int | None = None
    seat_ids: list[str] = Field(default_factory=list)

    def merge(self, other: BookingParams) -> BookingParams:
        """Overlay non-empty fields of `other` onto a copy of self."""

        data = self.model_dump()
        for key, value in other.model_dump().items():
            if value in (None, [], ""):
                continue
            data[key] = value
        return BookingParams(**data)
