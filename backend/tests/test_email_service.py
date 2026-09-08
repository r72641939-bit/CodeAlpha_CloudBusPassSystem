"""
Unit tests for app.core.email_service.

build_confirmation_message() is pure - no network involved - so it's
fully testable here. send_confirmation_email() actually contacting a
real SMTP server is NOT tested here (would need real credentials and
network access); what IS tested is that it degrades gracefully (returns
False, never raises) when SMTP isn't configured at all.
"""
from app.core.email_service import build_confirmation_message, is_email_configured, send_confirmation_email
from app.config import settings


def test_message_has_correct_recipient_and_subject():
    msg = build_confirmation_message(
        to_email="ram@example.com",
        passenger_name="Ram Jethani",
        origin="Karachi",
        destination="Lahore",
        departure_time_str="Mon, 07 Sep 2026 at 06:00 AM",
        seat_number=5,
        price_paid="2500.00",
        booking_reference="CB-ABC123",
    )
    assert msg["To"] == "ram@example.com"
    assert "CB-ABC123" in msg["Subject"]


def test_message_body_contains_booking_details():
    msg = build_confirmation_message(
        to_email="ram@example.com",
        passenger_name="Ram Jethani",
        origin="Karachi",
        destination="Lahore",
        departure_time_str="Mon, 07 Sep 2026 at 06:00 AM",
        seat_number=5,
        price_paid="2500.00",
        booking_reference="CB-ABC123",
    )
    # The message has both a plain-text and an HTML part - check both
    # actually contain the booking details, not just the subject line.
    parts = [part.get_payload(decode=True).decode("utf-8") for part in msg.get_payload()]
    full_body = "\n".join(parts)

    assert "Ram Jethani" in full_body
    assert "Karachi" in full_body
    assert "Lahore" in full_body
    assert "5" in full_body  # seat number
    assert "2500.00" in full_body
    assert "CB-ABC123" in full_body


def test_email_skipped_gracefully_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from_email", "")

    assert is_email_configured() is False

    result = send_confirmation_email(
        to_email="ram@example.com",
        passenger_name="Ram Jethani",
        origin="Karachi",
        destination="Lahore",
        departure_time_str="Mon, 07 Sep 2026 at 06:00 AM",
        seat_number=5,
        price_paid="2500.00",
        booking_reference="CB-ABC123",
    )
    # Should return False, not raise - a booking must never fail because
    # email isn't set up.
    assert result is False


def test_send_never_raises_even_with_unreachable_host(monkeypatch):
    # Point at a real-looking but unreachable host to prove failures are
    # swallowed gracefully rather than propagating as exceptions.
    monkeypatch.setattr(settings, "smtp_host", "smtp.invalid.example")
    monkeypatch.setattr(settings, "smtp_from_email", "test@example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)

    result = send_confirmation_email(
        to_email="ram@example.com",
        passenger_name="Ram Jethani",
        origin="Karachi",
        destination="Lahore",
        departure_time_str="Mon, 07 Sep 2026 at 06:00 AM",
        seat_number=5,
        price_paid="2500.00",
        booking_reference="CB-ABC123",
    )
    assert result is False
