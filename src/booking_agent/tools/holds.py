"""Atomic, time-bounded seat holds (Constitution II).

`place_seat_hold` is all-or-nothing: either every requested seat is held or the
call raises and nothing changes. Holds carry a 10-minute TTL; expired holds are
swept lazily on read/hold and explicitly by `release_expired_holds`.

Concurrency: on SQLite (single writer) the surrounding transaction serialises
holds. On PostgreSQL, wrap the seat reads in `SELECT ... FOR UPDATE`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking_agent.config import settings
from booking_agent.db.base import ensure_aware, utcnow
from booking_agent.db.enums import HoldStatus, SeatStatus
from booking_agent.db.models import AuditLog, Hold, Seat
from booking_agent.tools.errors import NotFoundError, SeatUnavailableError, ValidationToolError
from booking_agent.tools.schemas import HoldResult, SeatInfo


def _audit(session: Session, event_id: int, seat_id: str, action: str, detail: str) -> None:
    session.add(
        AuditLog(
            entity_type="seat",
            entity_id=f"{event_id}:{seat_id}",
            action=action,
            detail=detail,
        )
    )


def _expire_event_holds(session: Session, event_id: int, now: datetime) -> int:
    """Release holds for one event whose TTL has lapsed. Returns count expired."""

    expired = session.execute(
        select(Hold).where(Hold.event_id == event_id, Hold.status == HoldStatus.ACTIVE)
    ).scalars().all()
    count = 0
    for hold in expired:
        if ensure_aware(hold.expires_at) <= now:
            hold.status = HoldStatus.EXPIRED
            seat = session.execute(
                select(Seat).where(Seat.event_id == event_id, Seat.seat_id == hold.seat_id)
            ).scalar_one_or_none()
            if seat is not None and seat.status == SeatStatus.HELD:
                seat.status = SeatStatus.AVAILABLE
                _audit(session, event_id, hold.seat_id, "hold_expired", f"token={hold.token}")
            count += 1
    return count


def check_seat_availability(
    session: Session, event_id: int, seat_ids: list[str]
) -> list[SeatInfo]:
    """Report the current status of specific seats (after expiring stale holds)."""

    _expire_event_holds(session, event_id, utcnow())
    seats = session.execute(
        select(Seat).where(Seat.event_id == event_id, Seat.seat_id.in_(seat_ids))
    ).scalars().all()
    by_id = {s.seat_id: s for s in seats}
    missing = [sid for sid in seat_ids if sid not in by_id]
    if missing:
        raise NotFoundError(f"seats not found for event {event_id}: {missing}")
    return [
        SeatInfo(
            seat_id=s.seat_id,
            category=s.category,
            status=s.status,
            base_price=s.base_price,
        )
        for s in (by_id[sid] for sid in seat_ids)
    ]


def place_seat_hold(
    session: Session,
    event_id: int,
    seat_ids: list[str],
    email: str,
    ttl_minutes: int | None = None,
) -> HoldResult:
    """Atomically hold all requested seats for `ttl_minutes` (default 10).

    All-or-nothing: if any seat is unavailable, raises SeatUnavailableError and
    no seat is held. Re-holding the exact same seats as the same buyer is
    idempotent (returns the existing hold).
    """

    if not seat_ids:
        raise ValidationToolError("seat_ids must be a non-empty list")
    ttl = ttl_minutes if ttl_minutes is not None else settings.hold_ttl_minutes
    now = utcnow()

    # Free any seats whose hold has lapsed before we evaluate availability.
    _expire_event_holds(session, event_id, now)

    seats = session.execute(
        select(Seat).where(Seat.event_id == event_id, Seat.seat_id.in_(seat_ids))
    ).scalars().all()
    by_id = {s.seat_id: s for s in seats}
    missing = [sid for sid in seat_ids if sid not in by_id]
    if missing:
        raise NotFoundError(f"seats not found for event {event_id}: {missing}")

    # Idempotency fast-path: same buyer already actively holds exactly these seats.
    active = session.execute(
        select(Hold).where(
            Hold.event_id == event_id,
            Hold.seat_id.in_(seat_ids),
            Hold.status == HoldStatus.ACTIVE,
        )
    ).scalars().all()
    active_fresh = {h.seat_id: h for h in active if ensure_aware(h.expires_at) > now}
    if (
        active_fresh
        and set(active_fresh) == set(seat_ids)
        and all(h.email == email for h in active_fresh.values())
    ):
        token = next(iter(active_fresh.values())).token
        expires_at = max(ensure_aware(h.expires_at) for h in active_fresh.values())
        return HoldResult(
            token=token,
            event_id=event_id,
            seat_ids=list(seat_ids),
            email=email,
            expires_at=expires_at,
            ttl_minutes=ttl,
        )

    # Availability check — every requested seat must be free.
    for sid in seat_ids:
        seat = by_id[sid]
        if seat.status == SeatStatus.SOLD:
            raise SeatUnavailableError(f"seat {sid} is already sold", seat_id=sid)
        if seat.status == SeatStatus.HELD:
            raise SeatUnavailableError(f"seat {sid} is currently held", seat_id=sid)

    # Commit the hold atomically.
    token = uuid4().hex
    expires_at = now + timedelta(minutes=ttl)
    for sid in seat_ids:
        seat = by_id[sid]
        seat.status = SeatStatus.HELD
        session.add(
            Hold(
                token=token,
                event_id=event_id,
                seat_id=sid,
                email=email,
                expires_at=expires_at,
                status=HoldStatus.ACTIVE,
            )
        )
        _audit(session, event_id, sid, "hold", f"token={token} email={email} ttl={ttl}m")
    session.flush()

    return HoldResult(
        token=token,
        event_id=event_id,
        seat_ids=list(seat_ids),
        email=email,
        expires_at=expires_at,
        ttl_minutes=ttl,
    )


def release_seat_hold(session: Session, token: str) -> int:
    """Release every seat held under `token`. Returns the number released."""

    holds = session.execute(
        select(Hold).where(Hold.token == token, Hold.status == HoldStatus.ACTIVE)
    ).scalars().all()
    count = 0
    for hold in holds:
        hold.status = HoldStatus.RELEASED
        seat = session.execute(
            select(Seat).where(Seat.event_id == hold.event_id, Seat.seat_id == hold.seat_id)
        ).scalar_one_or_none()
        if seat is not None and seat.status == SeatStatus.HELD:
            seat.status = SeatStatus.AVAILABLE
            _audit(session, hold.event_id, hold.seat_id, "hold_released", f"token={token}")
        count += 1
    session.flush()
    return count


def release_expired_holds(session: Session, now: datetime | None = None) -> int:
    """Sweep ALL events: release holds past their TTL. Returns count released.

    Intended to be called periodically by a background worker (also the `booking-agent sweep` CLI).
    """

    now = now or utcnow()
    expired = session.execute(
        select(Hold).where(Hold.status == HoldStatus.ACTIVE)
    ).scalars().all()
    count = 0
    for hold in expired:
        if ensure_aware(hold.expires_at) <= now:
            hold.status = HoldStatus.EXPIRED
            seat = session.execute(
                select(Seat).where(
                    Seat.event_id == hold.event_id, Seat.seat_id == hold.seat_id
                )
            ).scalar_one_or_none()
            if seat is not None and seat.status == SeatStatus.HELD:
                seat.status = SeatStatus.AVAILABLE
                _audit(session, hold.event_id, hold.seat_id, "hold_expired", f"token={hold.token}")
            count += 1
    session.flush()
    return count
