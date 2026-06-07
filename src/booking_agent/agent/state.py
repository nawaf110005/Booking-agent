from __future__ import annotations

from dataclasses import dataclass, field

# Conversation steps (also surfaced to the UI as `step`).
GREETING = "greeting"
EVENT_SELECTION = "event_selection"
NEED_EMAIL = "need_email"
CATEGORY_SELECTION = "category_selection"
NEED_QUANTITY = "need_quantity"
SEAT_SELECTION = "seat_selection"
AWAITING_CONFIRMATION = "awaiting_confirmation"
PAYMENT = "payment"
CONFIRMED = "confirmed"


@dataclass
class ConversationState:
    """Per-session short-term memory (Constitution VII; mirrors Memory Design)."""

    session_id: str
    step: str = GREETING
    last_query: str | None = None
    event_id: int | None = None
    email: str | None = None
    tier: str | None = None
    is_member: bool = False
    ticket_cap: int = 4
    category: str | None = None
    quantity: int | None = None
    seat_ids: list[str] = field(default_factory=list)
    hold_token: str | None = None
    hold_expires: str | None = None  # ISO string
    booking_id: int | None = None
    turn: int = 0
    history: list[dict] = field(default_factory=list)  # [{role, text}]

    def record(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})
        if len(self.history) > 40:  # keep memory bounded
            self.history = self.history[-40:]
