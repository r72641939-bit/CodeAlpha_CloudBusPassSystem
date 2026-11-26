"""
Unit tests for ticket IDs - no database server required.
"""
from sqlalchemy.dialects import postgresql

from app.core.reference import generate_booking_reference
from app.models import ticket_id_seq


class FakeSession:
    def __init__(self):
        self.statements = []

    def scalar(self, statement):
        self.statements.append(str(statement.compile(dialect=postgresql.dialect())))
        return 100


def test_ticket_id_is_a_plain_number_from_the_sequence():
    session = FakeSession()
    assert generate_booking_reference(session) == "100"
    assert "nextval" in session.statements[0]


def test_numbering_starts_at_100():
    assert ticket_id_seq.start == 100
