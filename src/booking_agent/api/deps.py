from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from booking_agent.db import SessionLocal


def get_db() -> Iterator[Session]:
    """Request-scoped session: commit on success, rollback on error."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
