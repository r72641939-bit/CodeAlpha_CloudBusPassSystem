"""
Simple API-key protection for admin-only endpoints.
"""
import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def is_staff(x_api_key: Optional[str]) -> bool:
    """True only when an admin key is configured and the caller sent it."""
    expected = settings.admin_api_key
    return bool(expected and x_api_key) and secrets.compare_digest(
        x_api_key.encode(), expected.encode()
    )


def require_admin(x_api_key: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency: the caller must send a matching `X-API-Key` header.
    Without ADMIN_API_KEY the check is skipped for local development only; on
    Vercel the admin endpoints stay locked."""
    expected = settings.admin_api_key
    if not expected:
        if os.environ.get("VERCEL"):
            raise HTTPException(status_code=503, detail="Admin access is not configured.")
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
