"""
Route browsing and seat-map endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.booking_engine import get_booked_seats
from app.database import get_db
from app.models import Route
from app.schemas import RouteIn, RouteOut, SeatMapOut

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("", response_model=RouteOut, summary="Create a new route (admin utility, used by the seed script)")
def create_route(payload: RouteIn, db: Session = Depends(get_db)):
    route = Route(**payload.model_dump())
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("", response_model=List[RouteOut], summary="List all available routes")
def list_routes(db: Session = Depends(get_db)):
    return db.query(Route).order_by(Route.departure_time).all()


@router.get("/{route_id}/seat-map", response_model=SeatMapOut, summary="Get seat availability for a route")
def get_seat_map(route_id: str, db: Session = Depends(get_db)):
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    booked = get_booked_seats(db, route_id)
    return SeatMapOut(route=RouteOut.model_validate(route), booked_seats=booked)
