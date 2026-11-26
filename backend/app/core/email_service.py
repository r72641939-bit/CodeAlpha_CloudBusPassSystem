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
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from app.config import settings


logger = logging.getLogger(__name__)


def sender_address() -> str:
    """SMTP_FROM_EMAIL, falling back to the login address (the same for Gmail)."""
    return (settings.smtp_from_email or settings.smtp_username).strip()


def is_email_configured() -> bool:
    return bool(settings.smtp_host.strip() and sender_address())


def _smtp_password() -> str:
    # Google displays app passwords in groups of four; the spaces are not part of it.
    if settings.smtp_host.strip().lower() == "smtp.gmail.com":
        return "".join(settings.smtp_password.split())
    return settings.smtp_password


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
    msg["Subject"] = f"CloudBus Booking Confirmed - Ticket {booking_reference}"
    msg["From"] = sender_address()
    msg["To"] = to_email

    text_body = (
        f"Hi {passenger_name},\n\n"
        f"Your seat is confirmed.\n\n"
        f"Route: {origin} -> {destination}\n"
        f"Departure: {departure_time_str}\n"
        f"Seat: {seat_number}\n"
        f"Price paid: Rs {price_paid}\n"
        f"Ticket ID: {booking_reference}\n\n"
        f"Thanks for booking with CloudBus.\n\n"
        f"Built by Ram Jethani\n"
        f"LinkedIn: https://www.linkedin.com/in/ram-jethani-86810b3a9"
    )

    # Passenger and route text is user input: escape it before it goes into HTML.
    safe_name, safe_origin, safe_destination = (
        escape(passenger_name), escape(origin), escape(destination)
    )

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#0E2341;">Booking Confirmed</h2>
      <p>Hi {safe_name},</p>
      <p>Your seat is confirmed. Here are your ticket details:</p>
      <table style="width:100%; border-collapse: collapse; margin: 16px 0;">
        <tr><td style="padding:6px 0; color:#6E7078;">Route</td><td style="padding:6px 0; font-weight:600;">{safe_origin} &rarr; {safe_destination}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Departure</td><td style="padding:6px 0; font-weight:600;">{departure_time_str}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Seat</td><td style="padding:6px 0; font-weight:600;">{seat_number}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Price paid</td><td style="padding:6px 0; font-weight:600;">Rs {price_paid}</td></tr>
        <tr><td style="padding:6px 0; color:#6E7078;">Ticket ID</td><td style="padding:6px 0; font-weight:700; color:#0E2341;">{booking_reference}</td></tr>
      </table>
      <p style="color:#6E7078; font-size:13px;">Thanks for booking with CloudBus.</p>
      <p style="font-size:12px; color:#9AA3B5; margin-top:20px; border-top:1px solid #ECECE8; padding-top:12px;">
        Built by <strong style="color:#0E2341;">Ram Jethani</strong> &mdash;
        <a href="https://www.linkedin.com/in/ram-jethani-86810b3a9" style="color:#0E2341; text-decoration:none;">Connect on LinkedIn</a>
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
        logger.warning("Email skipped: set SMTP_HOST and SMTP_FROM_EMAIL (or SMTP_USERNAME).")
        return False

    try:
        msg = build_confirmation_message(
            to_email, passenger_name, origin, destination,
            departure_time_str, seat_number, price_paid, booking_reference,
        )
        host = settings.smtp_host.strip()
        context = ssl.create_default_context()
        # Port 465 is encrypted from the first byte; 587 upgrades with STARTTLS.
        if settings.smtp_port == 465:
            connection = smtplib.SMTP_SSL(host, 465, timeout=10, context=context)
        else:
            connection = smtplib.SMTP(host, settings.smtp_port, timeout=10)
        with connection as server:
            if settings.smtp_use_tls and settings.smtp_port != 465:
                server.starttls(context=context)
            if settings.smtp_username:
                server.login(settings.smtp_username.strip(), _smtp_password())
            server.sendmail(sender_address(), [to_email], msg.as_string())
        return True
    except Exception:
        # Deliberately broad: any SMTP/network failure should degrade to
        # "email not sent" rather than break the booking response. The reason
        # is logged so it can be found in the Vercel logs.
        logger.exception("Confirmation email failed for booking %s", booking_reference)
        return False
