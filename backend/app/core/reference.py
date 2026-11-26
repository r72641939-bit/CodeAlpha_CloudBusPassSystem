"""
Ticket IDs (100, 101, 102, ...), distinct from the internal UUID primary
key - the number a passenger reads off a ticket.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ticket_id_seq


def generate_booking_reference(db: Session) -> str:
    return str(db.scalar(select(ticket_id_seq.next_value())))
