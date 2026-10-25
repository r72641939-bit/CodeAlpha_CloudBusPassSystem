"""
Centralized application configuration.
"""
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bus_pass_db"

    # Comma-separated list of frontend origins allowed to call the API,
    # e.g. "https://cloudbus-frontend.onrender.com,http://localhost:5500"
    allowed_origin: str = "http://localhost:5500"

    # Protects admin-only endpoints (create route, list all bookings, cancel).
    # Clients must send it in the `X-API-Key` header. If left empty the
    # endpoints stay open (convenient for local development) - ALWAYS set
    # this in production.
    admin_api_key: str = ""

    # SMTP settings for booking confirmation emails. If smtp_host is empty,
    # email sending is skipped entirely (booking still succeeds) - see
    # app/core/email_service.py.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_psycopg3_driver(cls, value: str) -> str:
        """Hosts like Neon/Render hand out `postgres://` or `postgresql://`
        URLs. SQLAlchemy would then look for the old psycopg2 driver, which
        is not installed - so normalise to the psycopg v3 driver we use."""
        if isinstance(value, str):
            value = value.strip()
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def allowed_origins(self) -> List[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origin.split(",") if o.strip()]


settings = Settings()
