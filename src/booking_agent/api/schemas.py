from __future__ import annotations

from pydantic import BaseModel, Field


class QuoteRequest(BaseModel):
    event_id: int
    category: str = Field(examples=["gold"])
    quantity: int = Field(ge=1, examples=[4])
    email: str | None = Field(default=None, examples=["nawaf@example.com"])


class HoldRequest(BaseModel):
    event_id: int
    seat_ids: list[str] = Field(min_length=1, examples=[["G12", "G13"]])
    email: str = Field(examples=["nawaf@example.com"])


class HealthResponse(BaseModel):
    status: str = "ok"
    provider: str
    model: str
    currency: str
    vat_rate: float
    hold_ttl_minutes: int
    llm_configured: bool
