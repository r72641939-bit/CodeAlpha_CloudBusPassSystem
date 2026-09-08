"""
Booking endpoints - the concurrency-safe, price-integrity-guaranteed core.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.booking_engine import (
    book_seat, cancel_booking,
    RouteNotFoundError, InvalidSeatError, SeatUnavailableError,
)
from app.database import get_db
from app.models import Booking
from app.schemas import BookingIn, BookingOut, BookingStatsOut

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, summary="Book a seat (concurrency-safe, server-priced)")
def create_booking(payload: BookingIn, db: Session = Depends(get_db)):
    try:
        booking = book_seat(
            db,
            route_id=payload.route_id,
            seat_number=payload.seat_number,
            passenger_name=payload.passenger_name,
            passenger_email=payload.passenger_email,
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidSeatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SeatUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return booking


@router.get("", response_model=List[BookingOut], summary="List all bookings")
def list_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).order_by(Booking.created_at.desc()).all()


@router.post("/{booking_id}/cancel", response_model=BookingOut, summary="Cancel a booking (frees the seat)")
def cancel(booking_id: str, db: Session = Depends(get_db)):
    try:
        return cancel_booking(db, booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stats", response_model=BookingStatsOut, summary="Booking system summary stats")
def get_stats(db: Session = Depends(get_db)):
    from app.models import Route, BookingStatus

    total_routes = db.query(Route).count()
    confirmed = db.query(Booking).filter(Booking.status == BookingStatus.CONFIRMED).count()
    cancelled = db.query(Booking).filter(Booking.status == BookingStatus.CANCELLED).count()

    total_seats = sum(r.total_seats for r in db.query(Route).all())
    seats_remaining = total_seats - confirmed

    return BookingStatsOut(
        total_routes=total_routes,
        total_confirmed_bookings=confirmed,
        total_cancelled_bookings=cancelled,
        seats_remaining_across_routes=max(seats_remaining, 0),
    )
