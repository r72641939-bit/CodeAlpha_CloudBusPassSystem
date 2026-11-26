"""
Booking endpoints - the concurrency-safe, price-integrity-guaranteed core.
"""
import logging
import uuid
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.booking_engine import (
    book_seat, cancel_booking,
    RouteNotFoundError, InvalidSeatError, SeatUnavailableError,
    RouteDepartedError, TooManyBookingsError,
    cancel_own_booking, BookingNotFoundError, CancelNotAllowedError,
)
from app.config import settings
from app.core.client_ip import client_ip, limit_key
from app.core.rate_limit import recent_events, record_event
from app.database import get_db
from app.models import Booking, Route
from app.security import is_staff, require_admin
from app.schemas import (
    BookingIn, BookingOut, BookingStatsOut, SelfCancelIn, SelfCancelOut, StaffBookingOut,
)

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, summary="Book a seat (concurrency-safe, server-priced)")
def create_booking(
    payload: BookingIn,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    peer = request.client.host if request.client else None
    key = limit_key("book", client_ip(request.headers, peer))
    staff = is_staff(x_api_key)
    if not staff and recent_events(db, key, timedelta(hours=1)) >= settings.bookings_per_ip_per_hour:
        raise HTTPException(status_code=429, detail="Too many bookings from this connection. Please try again later.")
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
    except RouteDepartedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TooManyBookingsError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    if not staff:
        try:
            record_event(db, key)
        except Exception:  # the seat is already booked; never fail it now
            db.rollback()
            logging.getLogger(__name__).exception("Could not record the booking for rate limiting")
        db.refresh(booking)

    return booking


@router.post("/self-cancel", response_model=SelfCancelOut,
             summary="Passenger cancellation (needs ticket ID and email)")
def self_cancel(payload: SelfCancelIn, request: Request, db: Session = Depends(get_db)):
    peer = request.client.host if request.client else None
    key = limit_key("cancel", client_ip(request.headers, peer))
    # Count the attempt first, so parallel guesses can't slip past the limit.
    record_event(db, key)
    if recent_events(db, key, timedelta(minutes=15)) > 10:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again in 15 minutes.")
    try:
        booking = cancel_own_booking(db, payload.ticket_id, payload.passenger_email)
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CancelNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SelfCancelOut(
        ticket_id=booking.booking_reference, seat_number=booking.seat_number,
        origin=booking.route.origin, destination=booking.route.destination,
    )


@router.get("/staff", response_model=List[StaffBookingOut], dependencies=[Depends(require_admin)],
            summary="Search bookings with trip details (admin only)")
def staff_bookings(q: str = Query(default="", max_length=100), db: Session = Depends(get_db)):
    query = db.query(Booking, Route).join(Route, Booking.route_id == Route.id)
    term = q.strip()
    if term:
        query = query.filter(or_(
            Booking.booking_reference == term.upper(),
            Booking.passenger_name.icontains(term, autoescape=True),
            Booking.passenger_email.icontains(term, autoescape=True),
        ))
    rows = query.order_by(Booking.created_at.desc()).limit(100).all()
    return [
        StaffBookingOut(
            **BookingOut.model_validate(booking).model_dump(),
            origin=route.origin, destination=route.destination, departure_time=route.departure_time,
        )
        for booking, route in rows
    ]


@router.get("", response_model=List[BookingOut], dependencies=[Depends(require_admin)],
            summary="List all bookings (admin only - needs X-API-Key)")
def list_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).order_by(Booking.created_at.desc()).all()


@router.post("/{booking_id}/cancel", response_model=BookingOut, dependencies=[Depends(require_admin)],
             summary="Cancel a booking (admin only - needs X-API-Key)")
def cancel(booking_id: uuid.UUID, db: Session = Depends(get_db)):
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
