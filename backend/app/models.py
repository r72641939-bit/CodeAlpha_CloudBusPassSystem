"""
Database models.

Route    - a scheduled bus journey: origin, destination, departure time,
           fixed price, and total seat count.
Booking  - a single seat reservation on a route. `price_paid` is always
           copied server-side from the route's current price at booking
           time - the client can never submit its own price, which is
           what prevents the "incorrect pricing" failure mode the task
           calls out.

Seat-uniqueness is enforced with a PARTIAL unique index on
(route_id, seat_number) that only applies to CONFIRMED bookings. This
matters: a plain unique constraint would permanently lock a seat number
even after a booking is cancelled. The partial index means a cancelled
seat becomes bookable again, while two simultaneously CONFIRMED bookings
for the same seat are structurally impossible at the database level -
a second safety net underneath the row-locking logic in
app/core/booking_engine.py.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Boolean, Enum, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Route(Base):
    __tablename__ = "routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    total_seats = Column(Integer, nullable=False, default=40)
    operator_name = Column(String(100), nullable=False, default="CloudBus")
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="route")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    seat_number = Column(Integer, nullable=False)
    passenger_name = Column(String(255), nullable=False)
    passenger_email = Column(String(255), nullable=False)
    booking_reference = Column(String(12), nullable=False, unique=True, index=True)
    # Always copied server-side from Route.price at booking time - never
    # accepted from the client. See app/core/booking_engine.py.
    price_paid = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.CONFIRMED)
    # Whether the confirmation email was sent successfully. This is best-effort:
    # if email sending fails (bad SMTP config, network issue), the booking
    # itself still succeeds - a booking should never be lost because an email
    # provider had a bad moment. See app/core/email_service.py.
    email_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    route = relationship("Route", back_populates="bookings")


# Partial unique index: only one CONFIRMED booking may exist per
# (route_id, seat_number) at a time. Cancelled bookings are excluded,
# so a cancelled seat can be rebooked without violating this constraint.
Index(
    "uq_confirmed_seat_per_route",
    Booking.route_id,
    Booking.seat_number,
    unique=True,
    postgresql_where=(Booking.status == BookingStatus.CONFIRMED),
)
