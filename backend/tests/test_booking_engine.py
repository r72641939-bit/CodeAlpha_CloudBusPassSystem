"""
Integration tests for app.core.booking_engine.

Unlike test_reference.py, these require a REAL PostgreSQL database
configured via .env (DATABASE_URL) - row-locking (`SELECT ... FOR UPDATE`)
and the partial unique index are genuine Postgres features that can't be
meaningfully faked with an in-memory substitute. Run these against a
throwaway/test database, not your main one, since they create and delete
real rows.

Run with:
    pytest tests/test_booking_engine.py -v
"""
import threading
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import Route, Booking, BookingStatus
from app.core.booking_engine import book_seat, cancel_booking, SeatUnavailableError, InvalidSeatError


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_route(db_session):
    route = Route(
        origin="Karachi",
        destination="Lahore",
        departure_time=datetime.utcnow() + timedelta(hours=5),
        price=Decimal("2500.00"),
        total_seats=10,
        operator_name="Test Line",
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)

    yield route

    # Cleanup: remove bookings then the route itself.
    db_session.query(Booking).filter(Booking.route_id == route.id).delete()
    db_session.delete(route)
    db_session.commit()


def test_booking_a_seat_succeeds(db_session, test_route):
    booking = book_seat(db_session, test_route.id, seat_number=1, passenger_name="Ram Jethani", passenger_email="ram@example.com")
    assert booking.seat_number == 1
    assert booking.status == BookingStatus.CONFIRMED


def test_price_is_always_from_the_route_never_the_client(db_session, test_route):
    # BookingIn/book_seat take no price argument at all - this test
    # confirms the stored price always matches the route's price.
    booking = book_seat(db_session, test_route.id, seat_number=2, passenger_name="Ram Jethani", passenger_email="ram@example.com")
    assert booking.price_paid == test_route.price


def test_double_booking_the_same_seat_is_rejected(db_session, test_route):
    book_seat(db_session, test_route.id, seat_number=3, passenger_name="First Passenger", passenger_email="first@example.com")
    with pytest.raises(SeatUnavailableError):
        book_seat(db_session, test_route.id, seat_number=3, passenger_name="Second Passenger", passenger_email="second@example.com")


def test_seat_out_of_range_is_rejected(db_session, test_route):
    with pytest.raises(InvalidSeatError):
        book_seat(db_session, test_route.id, seat_number=999, passenger_name="Ram Jethani", passenger_email="ram@example.com")


def test_cancelling_a_booking_frees_the_seat_for_rebooking(db_session, test_route):
    booking = book_seat(db_session, test_route.id, seat_number=4, passenger_name="Ram Jethani", passenger_email="ram@example.com")
    cancel_booking(db_session, booking.id)

    # Should now succeed - the partial unique index only covers CONFIRMED bookings.
    rebooking = book_seat(db_session, test_route.id, seat_number=4, passenger_name="New Passenger", passenger_email="new@example.com")
    assert rebooking.status == BookingStatus.CONFIRMED


def test_concurrent_booking_attempts_only_one_wins(test_route):
    """
    The real test of the row-locking guarantee: fire many threads at the
    exact same seat simultaneously and confirm exactly one succeeds.
    Each thread gets its OWN database session, since sessions aren't
    thread-safe - this mirrors how separate concurrent HTTP requests
    would each get their own session in the real API.
    """
    num_attempts = 10
    results = []
    lock = threading.Lock()

    def attempt(passenger_name):
        session = SessionLocal()
        try:
            book_seat(session, test_route.id, seat_number=7, passenger_name=passenger_name, passenger_email=f"{passenger_name.replace(chr(32), chr(46)).lower()}@example.com")
            with lock:
                results.append(True)
        except SeatUnavailableError:
            with lock:
                results.append(False)
        finally:
            session.close()

    threads = [
        threading.Thread(target=attempt, args=(f"Race Tester {i}",))
        for i in range(num_attempts)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(results) == 1, f"Expected exactly 1 successful booking, got {sum(results)}"
