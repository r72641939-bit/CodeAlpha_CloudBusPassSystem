"""
Cloud-Based Bus Pass System - API entrypoint.

CodeAlpha Cloud Computing Internship - Task 3
Built by Ram Jethani

Run locally with:
    uvicorn app.main:app --reload

Interactive API docs available at /docs once running.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
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

app.include_router(routes.router)
app.include_router(bookings.router)


@app.get("/api/health", tags=["health"], summary="Health check")
def root():
    return {
        "service": "Cloud-Based Bus Pass System",
        "status": "online",
        "docs": "/docs",
    }
