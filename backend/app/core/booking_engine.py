"""
Booking Engine
==============
This is the core of the "prevent ticket loss/theft/incorrect pricing"
requirement. Two real, testable guarantees:

1. SEAT SAFETY UNDER CONCURRENCY. Two people tapping "Book" on the same
   seat at the same instant is the classic overselling bug. This is
   prevented two ways, layered:

     a) `SELECT ... FOR UPDATE` locks the route row for the duration of
        the transaction, so concurrent booking attempts on the SAME
        route are serialized - the second request has to wait for the
        first to fully commit or fail before it can even check seat
        availability. This is pessimistic locking, and it's the correct
        tool here because seat inventory is a small, hot, contended
        resource.
     b) The partial unique index on the Booking table (see models.py)
        is a second, database-level guarantee: even in an edge case the
        application logic didn't anticipate, the database itself will
        refuse to store two CONFIRMED bookings for the same seat.

2. PRICE INTEGRITY. `price_paid` is read from `route.price` at booking
   time - the client-submitted request never contains a price at all
   (see BookingIn in schemas.py). This makes client-side price
   tampering structurally impossible, not just "checked for."
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.email_service import send_confirmation_email
from app.core.reference import generate_booking_reference
from app.models import Route, Booking, BookingStatus


class RouteNotFoundError(Exception):
    pass


class InvalidSeatError(Exception):
    pass


class SeatUnavailableError(Exception):
    pass


def get_booked_seats(db: Session, route_id) -> List[int]:
    rows = db.execute(
        select(Booking.seat_number).where(
            Booking.route_id == route_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    ).all()
    return sorted(r[0] for r in rows)


def book_seat(db: Session, route_id, seat_number: int, passenger_name: str, passenger_email: str) -> Booking:
    # Lock the route row - serializes concurrent booking attempts for
    # this specific route until each transaction commits or rolls back.
    route = db.execute(
        select(Route).where(Route.id == route_id).with_for_update()
    ).scalar_one_or_none()

    if route is None:
        raise RouteNotFoundError(f"Route {route_id} does not exist.")

    if seat_number < 1 or seat_number > route.total_seats:
        raise InvalidSeatError(
            f"Seat {seat_number} is out of range for this route (1-{route.total_seats})."
        )

    already_booked = db.execute(
        select(Booking).where(
            Booking.route_id == route_id,
            Booking.seat_number == seat_number,
            Booking.status == BookingStatus.CONFIRMED,
        )
    ).scalar_one_or_none()

    if already_booked is not None:
        raise SeatUnavailableError(f"Seat {seat_number} is already booked on this route.")

    booking = Booking(
        route_id=route_id,
        seat_number=seat_number,
        passenger_name=passenger_name,
        passenger_email=passenger_email,
        booking_reference=generate_booking_reference(),
        price_paid=route.price,  # server-side, never client-supplied
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)

    try:
        db.commit()
    except IntegrityError:
        # Defense-in-depth: the partial unique index catches any race
        # the row lock somehow didn't (e.g. a lock timeout/retry edge case).
        db.rollback()
        raise SeatUnavailableError(f"Seat {seat_number} was just booked by someone else.")

    db.refresh(booking)

    # Best-effort confirmation email - see app/core/email_service.py for
    # why this can never fail the booking itself. The booking is already
    # committed above; this only updates the email_sent flag afterward.
    sent = send_confirmation_email(
        to_email=passenger_email,
        passenger_name=passenger_name,
        origin=route.origin,
        destination=route.destination,
        departure_time_str=route.departure_time.strftime("%a, %d %b %Y at %I:%M %p"),
        seat_number=seat_number,
        price_paid=str(booking.price_paid),
        booking_reference=booking.booking_reference,
    )
    if sent:
        booking.email_sent = True
        db.commit()
        db.refresh(booking)

    return booking


def cancel_booking(db: Session, booking_id) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise ValueError("Booking not found.")
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return booking
