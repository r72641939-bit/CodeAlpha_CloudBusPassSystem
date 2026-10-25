"""
Simple API-key protection for admin-only endpoints.
"""
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def require_admin(x_api_key: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency. If ADMIN_API_KEY is not configured the check is
    skipped (local development); otherwise the caller must send a matching
    `X-API-Key` header."""
    expected = settings.admin_api_key
    if not expected:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
