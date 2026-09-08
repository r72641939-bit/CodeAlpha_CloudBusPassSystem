"""
Unit tests for app.core.reference - pure function, no DB required.
"""
import re

from app.core.reference import generate_booking_reference


def test_reference_has_correct_format():
    ref = generate_booking_reference()
    assert re.match(r"^CB-[A-Z0-9]{6}$", ref)


def test_references_are_unique_across_many_calls():
    refs = {generate_booking_reference() for _ in range(1000)}
    # With 36^6 possible suffixes, 1000 draws colliding is astronomically
    # unlikely - this is really checking the generator isn't broken
    # (e.g. accidentally deterministic).
    assert len(refs) == 1000
