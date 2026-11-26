"""
End-to-end tests: the real app served over HTTP, backed by real PostgreSQL.
Like test_booking_engine.py, these need DATABASE_URL to point at a throwaway
database.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import uvicorn

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Booking, RateEvent, Route

BACKEND = Path(__file__).resolve().parent.parent
# Talk to the test server directly, even if a proxy is configured.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture(scope="module")
def base_url():
    Base.metadata.create_all(bind=engine)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started:
        assert thread.is_alive() and time.time() < deadline, "server did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def route_id():
    session = SessionLocal()
    session.query(RateEvent).delete()  # each test starts with a clean limit
    route = Route(
        origin="Karachi", destination="Lahore",
        departure_time=datetime.utcnow() + timedelta(minutes=30),
        price=Decimal("2500.00"), total_seats=10, operator_name="Test Line",
    )
    session.add(route)
    session.commit()
    identifier = str(route.id)
    yield identifier
    session.query(Booking).filter(Booking.route_id == route.id).delete()
    session.delete(route)
    session.commit()
    session.close()


def fetch(url, body=None):
    request = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with OPENER.open(request, timeout=30) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


@pytest.mark.parametrize("path, expected", [
    ("/", b"CloudBus"),
    ("/robots.txt", b"Sitemap:"),
    ("/sitemap.xml", b"<urlset"),
    ("/llms.txt", b"# CloudBus"),
    ("/og-image.png", b"PNG"),
    ("/api/health", b"email_configured"),
    ("/api/routes", b"["),
])
def test_public_addresses_respond(base_url, path, expected):
    status, headers, body = fetch(base_url + path)
    assert status == 200
    assert expected in body
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_home_page_has_a_content_security_policy(base_url):
    _, headers, body = fetch(base_url + "/")
    assert "script-src 'sha256-" in headers["Content-Security-Policy"]
    assert b"__SITE_URL__" not in body


def test_booking_over_http(base_url, route_id):
    booking = {
        "route_id": route_id, "seat_number": 2,
        "passenger_name": "Ram Kumar", "passenger_email": "ram.http@example.com",
    }
    status, _, body = fetch(base_url + "/api/bookings", booking)
    assert status == 200, body
    ticket = json.loads(body)
    assert int(ticket["booking_reference"]) >= 100
    assert Decimal(str(ticket["price_paid"])) == Decimal("2500.00")

    assert fetch(base_url + "/api/bookings", booking)[0] == 409
    _, _, seat_map = fetch(f"{base_url}/api/routes/{route_id}/seat-map")
    assert json.loads(seat_map)["booked_seats"] == [2]


def test_bad_input_is_refused(base_url, route_id):
    status, _, _ = fetch(base_url + "/api/bookings", {
        "route_id": route_id, "seat_number": 1,
        "passenger_name": "http://spam.example", "passenger_email": "a@example.com",
    })
    assert status == 422
    assert fetch(base_url + "/api/routes/not-an-id/seat-map")[0] == 422


def test_passenger_can_cancel_with_ticket_and_email(base_url, route_id):
    # More than an hour ahead, so cancelling is allowed.
    session = SessionLocal()
    session.get(Route, uuid.UUID(route_id)).departure_time = datetime.utcnow() + timedelta(hours=3)
    session.commit()
    session.close()
    email = "cancel.me@example.com"
    status, _, body = fetch(base_url + "/api/bookings", {
        "route_id": route_id, "seat_number": 3, "passenger_name": "Ali", "passenger_email": email,
    })
    assert status == 200, body
    ticket = json.loads(body)["booking_reference"]
    url = base_url + "/api/bookings/self-cancel"
    assert fetch(url, {"ticket_id": ticket, "passenger_email": "someone@example.com"})[0] == 404
    assert fetch(url, {"ticket_id": ticket, "passenger_email": email})[0] == 200
    assert fetch(url, {"ticket_id": ticket, "passenger_email": email})[0] == 400
    _, _, seat_map = fetch(f"{base_url}/api/routes/{route_id}/seat-map")
    assert json.loads(seat_map)["booked_seats"] == []


def test_cancel_guessing_is_limited(base_url, route_id):
    url = base_url + "/api/bookings/self-cancel"
    guess = {"ticket_id": "1", "passenger_email": "guess@example.com"}
    statuses = [fetch(url, guess)[0] for _ in range(11)]
    assert statuses[-1] == 429


def test_one_address_cannot_book_without_limit(base_url, route_id, monkeypatch):
    monkeypatch.setattr(settings, "bookings_per_ip_per_hour", 2)
    statuses = [fetch(base_url + "/api/bookings", {
        "route_id": route_id, "seat_number": seat,
        "passenger_name": "Sara", "passenger_email": f"sara{seat}@example.com",
    })[0] for seat in (4, 5, 6)]
    assert statuses == [200, 200, 429]


def test_staff_pages(base_url, route_id):
    status, headers, _ = fetch(base_url + "/staff")
    assert status == 200 and "noindex" in headers["X-Robots-Tag"]
    assert fetch(base_url + "/api/health/db")[0] == 200
    assert fetch(base_url + "/api/bookings/staff?q=nobody")[0] in (200, 401)


def test_500_people_booking_one_seat(base_url, route_id):
    result = subprocess.run(
        [sys.executable, "stress_test.py"],
        cwd=BACKEND,
        env={**os.environ, "BASE_URL": base_url, "PEOPLE": "500", "NO_PROXY": "127.0.0.1"},
        capture_output=True, text=True, timeout=240,
    )
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
