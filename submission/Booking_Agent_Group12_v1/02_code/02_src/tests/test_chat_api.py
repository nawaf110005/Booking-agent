from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from booking_agent.api.app import app
from booking_agent.api.deps import get_db


@pytest.fixture
def client(seeded: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: seeded
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_chat_books_a_ticket_end_to_end(client: TestClient) -> None:
    sid = client.post("/v1/sessions").json()["session_id"]

    def chat(msg: str) -> dict:
        return client.post("/v1/chat", json={"session_id": sid, "message": msg}).json()

    chat("Coldplay in Riyadh")
    assert chat("nawaf@example.com")["step"] == "category_selection"
    chat("gold")
    assert chat("4")["step"] == "seat_selection"
    r = chat("G7, G8, G9, G10")
    assert r["confirmation"]["seats"] == ["G7", "G8", "G9", "G10"]
    r = chat("confirm")
    booking_id = r["payment"]["booking_id"]
    assert booking_id

    pay = client.post(f"/v1/pay/{booking_id}").json()
    assert pay["ticket"]["booking_id"] == booking_id
    assert pay["ticket"]["seats"] == ["G7", "G8", "G9", "G10"]

    qr = client.get(f"/v1/tickets/{booking_id}/qr.png")
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"


def test_pay_is_idempotent(client: TestClient) -> None:
    sid = client.post("/v1/sessions").json()["session_id"]

    def chat(msg: str) -> dict:
        return client.post("/v1/chat", json={"session_id": sid, "message": msg}).json()

    chat("Coldplay in Riyadh")
    chat("nawaf@example.com")
    chat("vip")
    chat("2")
    chat("A2, B2")
    booking_id = chat("confirm")["payment"]["booking_id"]

    first = client.post(f"/v1/pay/{booking_id}").json()["ticket"]
    second = client.post(f"/v1/pay/{booking_id}").json()["ticket"]
    assert first["booking_id"] == second["booking_id"] == booking_id


def test_website_is_served(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "booking agent" in r.text.lower()
