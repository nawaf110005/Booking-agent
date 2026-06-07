from __future__ import annotations

from fastapi import APIRouter

from booking_agent.api.schemas import HealthResponse
from booking_agent.config import settings

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=settings.booking_agent_provider,
        model=settings.booking_agent_model,
        currency=settings.currency,
        vat_rate=settings.vat_rate,
        hold_ttl_minutes=settings.hold_ttl_minutes,
        llm_configured=settings.llm_configured,
    )
