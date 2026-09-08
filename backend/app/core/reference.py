"""
Short, human-readable booking reference codes (e.g. "CB-7X9K2M"),
distinct from the internal UUID primary key - the kind of code a
passenger would actually read off a ticket or SMS confirmation.
"""
import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_booking_reference() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return f"CB-{suffix}"
