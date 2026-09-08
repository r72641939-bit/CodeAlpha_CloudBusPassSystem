"""
Centralized application configuration.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bus_pass_db"
    allowed_origin: str = "http://localhost:5500"

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


settings = Settings()
