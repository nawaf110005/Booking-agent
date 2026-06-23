from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from booking_agent.api.app import app
from booking_agent.api.deps import get_db


@pytest.fixture
def client(seeded: Session) -> Iterator[TestClient]:
    # Drive the API against the in-memory seeded session instead of booking.db.
    app.dependency_overrides[get_db] = lambda: seeded
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_healthz(client: TestClient) -> None:
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    assert r.json()["currency"] == "SAR"
    assert r.json()["vat_rate"] == 0.15


def test_list_events(client: TestClient) -> None:
    r = client.get("/v1/events", params={"query": "Coldplay"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_event_not_found(client: TestClient) -> None:
    r = client.get("/v1/events/99999")
    assert r.status_code == 404
    assert r.json()["error"] == "NotFoundError"


def test_quote_ok(client: TestClient, coldplay_riyadh_id: int) -> None:
    r = client.post(
        "/v1/quote",
        json={"event_id": coldplay_riyadh_id, "category": "gold", "quantity": 4, "email": "nawaf@example.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 312_800       # 3,128.00 SAR
    assert body["discount_total"] == 48_000


def test_quote_cap_exceeded(client: TestClient, coldplay_riyadh_id: int) -> None:
    r = client.post(
        "/v1/quote",
        json={"event_id": coldplay_riyadh_id, "category": "gold", "quantity": 5},  # non-member cap 4
    )
    assert r.status_code == 409
    assert r.json()["error"] == "CapExceededError"


def test_categories(client: TestClient, coldplay_riyadh_id: int) -> None:
    r = client.get(f"/v1/events/{coldplay_riyadh_id}/categories", params={"email": "nawaf@example.com"})
    assert r.status_code == 200
    cats = r.json()
    gold = next(c for c in cats if c["category"] == "gold")
    assert gold["discounted_price"] == 68_000


def test_seatmap_png(client: TestClient, coldplay_riyadh_id: int) -> None:
    r = client.get(f"/v1/events/{coldplay_riyadh_id}/seatmap.png", params={"category": "gold"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 500


def test_hold_then_release(client: TestClient, coldplay_riyadh_id: int) -> None:
    r = client.post(
        "/v1/holds",
        json={"event_id": coldplay_riyadh_id, "seat_ids": ["G9", "G10"], "email": "x@a.com"},
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert len(r.json()["seat_ids"]) == 2

    r2 = client.delete(f"/v1/holds/{token}")
    assert r2.status_code == 200
    assert r2.json()["released"] == 2


def test_hold_conflict_is_409(client: TestClient, coldplay_riyadh_id: int) -> None:
    client.post(
        "/v1/holds",
        json={"event_id": coldplay_riyadh_id, "seat_ids": ["H5"], "email": "first@a.com"},
    )
    r = client.post(
        "/v1/holds",
        json={"event_id": coldplay_riyadh_id, "seat_ids": ["H5"], "email": "second@a.com"},
    )
    assert r.status_code == 409
    assert r.json()["error"] == "SeatUnavailableError"
