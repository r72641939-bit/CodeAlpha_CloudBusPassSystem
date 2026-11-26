"""
Cloud-Based Bus Pass System - API entrypoint.

CodeAlpha Cloud Computing Internship - Task 3
Built by Ram Jethani

Run locally with:
    uvicorn app.main:app --reload

Interactive API docs available at /docs once running.
The booking page itself is served at "/".
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session

from app import web
from app.config import settings
from app.core.email_service import is_email_configured
from app.database import Base, engine, get_db
from app.routers import routes, bookings

try:
    Base.metadata.create_all(bind=engine)
except Exception:  # keep the app importable so the real DB error shows up per-request
    logging.getLogger(__name__).exception("Could not create database tables - check DATABASE_URL")

app = FastAPI(
    title="Cloud-Based Bus Pass System",
    description=(
        "An online bus ticket booking system with concurrency-safe seat "
        "reservations (no double-booking, even under simultaneous requests) "
        "and server-side price integrity (the client can never submit its "
        "own price)."
    ),
    version="1.0.0",
    contact={"name": "Ram Jethani - CodeAlpha Cloud Computing Internship, Task 3"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,  # the API uses no cookies, so credentials are not needed
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in web.SECURITY_HEADERS.items():
        response.headers[name] = value
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"  # seat data must be live
    return response


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeoutError)
async def database_busy(request: Request, exc: Exception):
    """Too many connections or an unreachable database: ask the client to retry
    instead of failing with an unexplained 500."""
    logging.getLogger(__name__).error("Database unavailable: %s", exc)
    return JSONResponse(
        {"detail": "The service is busy. Please try again in a moment."},
        status_code=503,
        headers={"Retry-After": "3"},
    )


app.include_router(routes.router)
app.include_router(bookings.router)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
def frontend():
    """Serve the booking page (same domain as the API, so no CORS needed)."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>Frontend file not found</h1>", status_code=404)
    page = web.render_page(index.read_text(encoding="utf-8"))
    return HTMLResponse(page, headers={"Content-Security-Policy": web.content_security_policy(page)})


@app.get("/staff", include_in_schema=False)
def staff_page():
    """The page itself is harmless; every action on it needs the admin key."""
    page = (STATIC_DIR / "staff.html").read_text(encoding="utf-8")
    return HTMLResponse(page, headers={
        "Content-Security-Policy": web.content_security_policy(page),
        "X-Robots-Tag": "noindex, nofollow",
        "Cache-Control": "no-store",
    })


@app.get("/api/health/db", tags=["health"], summary="Health check including the database")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))  # a failure becomes the 503 handler above
    return {"database": "online"}


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse(web.robots_txt())


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return Response(web.sitemap_xml(), media_type="application/xml")


@app.get("/llms.txt", include_in_schema=False)
def llms():
    return PlainTextResponse(web.llms_txt())


@app.get("/og-image.png", include_in_schema=False)
def og_image():
    return FileResponse(STATIC_DIR / "og-image.png", media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/health", tags=["health"], summary="Health check")
def root():
    return {
        "service": "Cloud-Based Bus Pass System",
        "status": "online",
        # True/False only - never exposes any SMTP value.
        "email_configured": is_email_configured(),
        "docs": "/docs",
    }