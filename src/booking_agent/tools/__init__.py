"""Typed Python tools the agent calls (Constitution III).

Every booking capability is an in-repo function here — no external ticketing
SaaS. The agent reasons over these signatures and docstrings.
"""

from booking_agent.tools.errors import (
    CapExceededError,
    NotFoundError,
    SeatUnavailableError,
    ToolError,
    ValidationToolError,
)
from booking_agent.tools.events import get_event_details, search_events
from booking_agent.tools.holds import (
    check_seat_availability,
    place_seat_hold,
    release_expired_holds,
    release_seat_hold,
)
from booking_agent.tools.members import get_ticket_cap, lookup_member_by_email
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing
from booking_agent.tools.seatmap import render_seat_map

__all__ = [
    "CapExceededError",
    "NotFoundError",
    "SeatUnavailableError",
    "ToolError",
    "ValidationToolError",
    "check_seat_availability",
    "compute_quote",
    "get_categories_with_pricing",
    "get_event_details",
    "get_ticket_cap",
    "lookup_member_by_email",
    "place_seat_hold",
    "release_expired_holds",
    "release_seat_hold",
    "render_seat_map",
    "search_events",
]
