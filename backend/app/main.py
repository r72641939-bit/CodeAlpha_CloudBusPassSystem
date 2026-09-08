"""
Cloud-Based Bus Pass System - API entrypoint.

CodeAlpha Cloud Computing Internship - Task 3
Built by Ram Jethani

Run locally with:
    uvicorn app.main:app --reload

Interactive API docs available at /docs once running.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import routes, bookings

Base.metadata.create_all(bind=engine)

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(bookings.router)


@app.get("/", tags=["health"], summary="Health check")
def root():
    return {
        "service": "Cloud-Based Bus Pass System",
        "status": "online",
        "docs": "/docs",
    }
