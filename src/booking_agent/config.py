from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Process-wide settings, loaded from environment + .env.

    Read once at import time; downstream code imports the `settings` singleton.
    Tests override fields by constructing `Settings(...)` and patching the
    module-level binding via dependency injection (see `tests/conftest.py`).
    """

    # Storage
    database_url: str = Field(default=f"sqlite:///{PROJECT_ROOT / 'booking.db'}")
    log_level: str = Field(default="INFO")

    # LLM (F002). Provider: anthropic | openai | nanogpt (OpenAI-compatible proxy).
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    nanogpt_api_key: str = ""
    booking_agent_provider: str = Field(default="anthropic")
    booking_agent_model: str = Field(default="claude-sonnet-4-6")

    # Booking rules
    hold_ttl_minutes: int = Field(default=10)
    vat_rate: float = Field(default=0.15)
    currency: str = Field(default="SAR")

    # Payments (F003)
    payment_gateway: str = Field(default="fake")  # fake | moyasar
    moyasar_secret_key: str = ""
    moyasar_webhook_secret: str = ""

    # Ticket signing (F003) — HMAC key for the QR token.
    ticket_hmac_key: str = Field(default="dev-insecure-change-me")

    # Email (F003)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = Field(default="tickets@booking-agent.local")

    # API
    booking_agent_admin_token: str = ""
    booking_agent_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8501,http://127.0.0.1:8501"
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def vat_bps(self) -> int:
        """VAT rate in integer basis points (e.g. 0.15 -> 1500) for exact math."""

        return round(self.vat_rate * 10_000)

    @property
    def active_llm_key(self) -> str:
        """The API key for the configured provider (empty -> heuristic fallback)."""

        provider = self.booking_agent_provider.lower()
        if provider in {"nanogpt", "nano-gpt", "nano_gpt"}:
            return self.nanogpt_api_key or self.openai_api_key
        if provider == "openai":
            return self.openai_api_key
        return self.anthropic_api_key

    @property
    def llm_configured(self) -> bool:
        return bool(self.active_llm_key)

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.booking_agent_allowed_origins.split(",") if o.strip()]


settings = Settings()
