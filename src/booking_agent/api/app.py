from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from booking_agent.config import settings
from booking_agent.db import engine
from booking_agent.db.base import Base
from booking_agent.tools.errors import (
    CapExceededError,
    NotFoundError,
    SeatUnavailableError,
    ToolError,
    ValidationToolError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the schema exists so the API runs against a fresh DB out of the box.
    Base.metadata.create_all(bind=engine)
    yield


def _error_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"error": exc.__class__.__name__, "detail": str(exc)},
        )

    return handler


def create_app() -> FastAPI:
    app = FastAPI(
        title="Booking-Agent API",
        version="0.1.0",
        description="Event-ticket booking: events, quotes, seat maps, and atomic holds.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        # Accept any localhost port in dev (Next.js may use 3000/3001/…).
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Map tool-layer errors to HTTP status codes (most specific first).
    app.add_exception_handler(NotFoundError, _error_handler(404))
    app.add_exception_handler(SeatUnavailableError, _error_handler(409))
    app.add_exception_handler(CapExceededError, _error_handler(409))
    app.add_exception_handler(ValidationToolError, _error_handler(422))
    app.add_exception_handler(ToolError, _error_handler(400))

    # Routers (imported here to keep import side effects local).
    from booking_agent.api.routers import chat, events, health, holds, pay, quote

    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(chat.router, prefix="/v1", tags=["chat"])
    app.include_router(events.router, prefix="/v1", tags=["events"])
    app.include_router(quote.router, prefix="/v1", tags=["quote"])
    app.include_router(holds.router, prefix="/v1", tags=["holds"])
    app.include_router(pay.router, prefix="/v1", tags=["pay"])

    # Serve the WeBook-style website at / (mounted last so /v1 routes win).
    web_dir = Path(__file__).resolve().parents[1] / "web" / "static"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


app = create_app()
