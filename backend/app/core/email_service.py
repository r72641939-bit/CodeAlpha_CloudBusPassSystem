"""
Booking confirmation email service.

Design principle: sending the email is BEST-EFFORT and must never break a
booking. A passenger's seat is real and reserved the moment the database
transaction commits - if the email provider is down, misconfigured, or the
network hiccups, the booking must still stand. This module never raises;
it returns True/False and the caller (booking_engine.book_seat) records
the outcome on the booking itself (Booking.email_sent) rather than failing
the request.

If SMTP isn't configured at all (no SMTP_HOST in .env), sending is skipped
outright - this keeps local development/demo usage friction-free without
requiring real email credentials just to test booking logic.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def is_email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def build_confirmation_message(
    to_email: str,
    passenger_name: str,
    origin: str,
    destination: str,
    departure_time_str: str,
    seat_number: int,
    price_paid: str,
    booking_reference: str,
) -> MIMEMultipart:
    """
    Builds the email message object. Separated from send_confirmation_email()
    so the message content itself can be tested without needing a real SMTP
    connection - see tests/test_email_service.py.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CloudBus Booking Confirmed - {booking_reference}"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    text_body = (
        f"Hi {passenger_name},\n\n"
        f"Your seat is confirmed.\n\n"
        f"Route: {origin} -> {destination}\n"
        f"Departure: {departure_time_str}\n"
        f"Seat: {seat_number}\n"
        f"Price paid: Rs {price_paid}\n"
        f"Booking reference: {booking_reference}\n\n"
        f"Thanks for booking with CloudBus.\n\n"
        f"Built by Ram Jethani\n"
        f"LinkedIn: https://www.linkedin.com/in/ram-jethani-86810b3a9"
    )

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#243B7A;">Booking Confirmed</h2>
      <p>Hi {passenger_name},</p>
      <p>Your seat is confirmed. Here are your ticket details:</p>
      <table style="width:100%; border-collapse: collapse; margin: 16px 0;">
        <tr><td style="padding:6px 0; color:#6E7078;">Route</td><td style="padding:6px 0; font-weight:600;">{origin} &rarr; {destination}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Departure</td><td style="padding:6px 0; font-weight:600;">{departure_time_str}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Seat</td><td style="padding:6px 0; font-weight:600;">{seat_number}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Price paid</td><td style="padding:6px 0; font-weight:600;">Rs {price_paid}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Reference</td><td style="padding:6px 0; font-weight:700; color:#FF6B4A;">{booking_reference}</td></tr>
      </table>
      <p style="color:#6E7078; font-size:13px;">Thanks for booking with CloudBus.</p>
      <p style="font-size:12px; color:#9AA3B5; margin-top:20px; border-top:1px solid #ECECE8; padding-top:12px;">
        Built by <strong style="color:#243B7A;">Ram Jethani</strong> &mdash;
        <a href="https://www.linkedin.com/in/ram-jethani-86810b3a9" style="color:#243B7A; text-decoration:none;">Connect on LinkedIn</a>
      </p>
    </div>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_confirmation_email(
    to_email: str,
    passenger_name: str,
    origin: str,
    destination: str,
    departure_time_str: str,
    seat_number: int,
    price_paid: str,
    booking_reference: str,
) -> bool:
    """Returns True if the email was sent successfully, False otherwise. Never raises."""
    if not is_email_configured():
        return False

    try:
        msg = build_confirmation_message(
            to_email, passenger_name, origin, destination,
            departure_time_str, seat_number, price_paid, booking_reference,
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [to_email], msg.as_string())
        return True
    except Exception:
        # Deliberately broad: any SMTP/network failure should degrade to
        # "email not sent" rather than break the booking response.
        return False
