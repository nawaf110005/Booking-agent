from __future__ import annotations

import pytest
from freezegun import freeze_time
from sqlalchemy.orm import Session

from booking_agent.db.enums import SeatStatus
from booking_agent.tools.errors import NotFoundError, SeatUnavailableError, ValidationToolError
from booking_agent.tools.holds import (
    check_seat_availability,
    place_seat_hold,
    release_expired_holds,
    release_seat_hold,
)


def _status(session: Session, event_id: int, seat_id: str) -> SeatStatus:
    return check_seat_availability(session, event_id, [seat_id])[0].status


def test_hold_all_available_seats(coldplay_riyadh_id: int, seeded: Session) -> None:
    result = place_seat_hold(seeded, coldplay_riyadh_id, ["G3", "G4"], "buyer@a.com")
    seeded.commit()
    assert set(result.seat_ids) == {"G3", "G4"}
    assert _status(seeded, coldplay_riyadh_id, "G3") == SeatStatus.HELD
    assert _status(seeded, coldplay_riyadh_id, "G4") == SeatStatus.HELD


def test_hold_is_all_or_nothing(coldplay_riyadh_id: int, seeded: Session) -> None:
    place_seat_hold(seeded, coldplay_riyadh_id, ["G5"], "first@a.com")
    seeded.commit()

    with pytest.raises(SeatUnavailableError):
        place_seat_hold(seeded, coldplay_riyadh_id, ["G5", "G6"], "second@a.com")
    seeded.rollback()

    # G6 must remain available — the failed call held nothing.
    assert _status(seeded, coldplay_riyadh_id, "G6") == SeatStatus.AVAILABLE


def test_sold_seat_cannot_be_held(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(SeatUnavailableError):
        place_seat_hold(seeded, coldplay_riyadh_id, ["G1"], "buyer@a.com")  # G1 is SOLD


def test_rehold_same_buyer_is_idempotent(coldplay_riyadh_id: int, seeded: Session) -> None:
    first = place_seat_hold(seeded, coldplay_riyadh_id, ["G7", "G8"], "buyer@a.com")
    seeded.commit()
    again = place_seat_hold(seeded, coldplay_riyadh_id, ["G7", "G8"], "buyer@a.com")
    assert again.token == first.token


def test_release_frees_seats(coldplay_riyadh_id: int, seeded: Session) -> None:
    held = place_seat_hold(seeded, coldplay_riyadh_id, ["H1", "H2"], "buyer@a.com")
    seeded.commit()
    released = release_seat_hold(seeded, held.token)
    seeded.commit()
    assert released == 2
    assert _status(seeded, coldplay_riyadh_id, "H1") == SeatStatus.AVAILABLE


def test_expired_holds_are_swept(coldplay_riyadh_id: int, seeded: Session) -> None:
    with freeze_time("2026-06-07 12:00:00"):
        place_seat_hold(seeded, coldplay_riyadh_id, ["H3", "H4"], "buyer@a.com")
        seeded.commit()
        assert _status(seeded, coldplay_riyadh_id, "H3") == SeatStatus.HELD

    with freeze_time("2026-06-07 12:11:00"):  # 11 minutes later > 10-min TTL
        swept = release_expired_holds(seeded)
        seeded.commit()
        assert swept >= 2
        assert _status(seeded, coldplay_riyadh_id, "H3") == SeatStatus.AVAILABLE


def test_expired_seat_can_be_re_held_by_someone_else(
    coldplay_riyadh_id: int, seeded: Session
) -> None:
    with freeze_time("2026-06-07 12:00:00"):
        place_seat_hold(seeded, coldplay_riyadh_id, ["S1"], "first@a.com")
        seeded.commit()
    with freeze_time("2026-06-07 12:20:00"):
        result = place_seat_hold(seeded, coldplay_riyadh_id, ["S1"], "second@a.com")
        seeded.commit()
        assert result.email == "second@a.com"


def test_empty_seat_list_rejected(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(ValidationToolError):
        place_seat_hold(seeded, coldplay_riyadh_id, [], "buyer@a.com")


def test_unknown_seat_rejected(coldplay_riyadh_id: int, seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        place_seat_hold(seeded, coldplay_riyadh_id, ["ZZ999"], "buyer@a.com")
