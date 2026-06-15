"""Typed agent response (FR-010).

Every turn returns a structured payload; this Pydantic model types it at the API
boundary and adds a `response_type` discriminator (message | event_cards |
categories | quote | seatmap | confirmation | payment) so clients never receive
an untyped blob. Internal code keeps using the dict; FastAPI validates against
this model on the way out.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


def infer_response_type(payload: dict) -> str:
    if payload.get("payment") is not None:
        return "payment"
    if payload.get("confirmation") is not None:
        return "confirmation"
    if payload.get("quote") is not None and payload.get("seatmap_url") is not None:
        return "seatmap"
    if payload.get("quote") is not None:
        return "quote"
    if payload.get("events") is not None:
        return "event_cards"
    if payload.get("categories") is not None:
        return "categories"
    return "message"


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    reply: str
    step: str
    response_type: str = "message"
    suggestions: list[str] = []
    events: list[Any] | None = None
    member: dict | None = None
    categories: list[Any] | None = None
    quote: dict | None = None
    seatmap_url: str | None = None
    hold: dict | None = None
    confirmation: dict | None = None
    payment: dict | None = None
