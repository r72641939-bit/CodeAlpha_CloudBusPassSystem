"""
Pydantic request/response schemas.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RouteIn(BaseModel):
    origin: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    departure_time: datetime
    price: Decimal = Field(gt=0)
    total_seats: int = Field(gt=0, le=200)
    operator_name: str = Field(default="CloudBus", max_length=100)


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    origin: str
    destination: str
    departure_time: datetime
    price: Decimal
    total_seats: int
    operator_name: str


class SeatMapOut(BaseModel):
    route: RouteOut
    booked_seats: List[int]


class BookingIn(BaseModel):
    route_id: uuid.UUID
    seat_number: int = Field(gt=0)
    passenger_name: str = Field(min_length=1, max_length=255)
    passenger_email: EmailStr
    # Note: no `price` field here on purpose - price is never accepted
    # from the client. See app/core/booking_engine.py.


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    route_id: uuid.UUID
    seat_number: int
    passenger_name: str
    passenger_email: str
    booking_reference: str
    price_paid: Decimal
    status: str
    email_sent: bool
    created_at: datetime


class BookingStatsOut(BaseModel):
    total_routes: int
    total_confirmed_bookings: int
    total_cancelled_bookings: int
    seats_remaining_across_routes: int
