"""
Vercel entrypoint. Vercel auto-detects a top-level `app` in this file and
serves it as the FastAPI function. The real application lives in backend/app.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
