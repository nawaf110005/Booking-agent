from __future__ import annotations


class ToolError(Exception):
    """Base for all tool-layer errors. The agent catches this to recover gracefully."""


class NotFoundError(ToolError):
    """A referenced record (event, seat, category) does not exist."""


class SeatUnavailableError(ToolError):
    """One or more requested seats are not available — the hold is all-or-nothing."""

    def __init__(self, message: str, seat_id: str | None = None) -> None:
        super().__init__(message)
        self.seat_id = seat_id


class CapExceededError(ToolError):
    """Requested quantity exceeds the buyer's per-booking ticket cap."""

    def __init__(self, message: str, cap: int | None = None) -> None:
        super().__init__(message)
        self.cap = cap


class ValidationToolError(ToolError):
    """Invalid tool input (e.g. empty seat list, non-positive quantity)."""
