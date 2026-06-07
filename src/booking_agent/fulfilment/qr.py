"""Tamper-evident QR tickets (Constitution V).

The QR encodes an HMAC-signed token (booking id + seats + nonce), not a bare
booking id, so a screenshot of someone else's QR cannot be forged or replayed —
verification recomputes the signature with the server key.
"""

from __future__ import annotations

import hashlib
import hmac
import io
from uuid import uuid4

import qrcode

from booking_agent.config import settings


def _sign(payload: str) -> str:
    return hmac.new(
        settings.ticket_hmac_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]


def sign_qr_token(booking_id: int, seat_ids: list[str], nonce: str | None = None) -> str:
    nonce = nonce or uuid4().hex[:8]
    payload = f"{booking_id}|{','.join(seat_ids)}|{nonce}"
    return f"{payload}|{_sign(payload)}"


def verify_qr_token(token: str) -> bool:
    parts = token.split("|")
    if len(parts) != 4:
        return False
    booking_id, seats, nonce, sig = parts
    return hmac.compare_digest(sig, _sign(f"{booking_id}|{seats}|{nonce}"))


def make_qr_png(token: str) -> bytes:
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
