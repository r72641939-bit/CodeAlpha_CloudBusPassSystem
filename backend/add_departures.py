"""
Adds a daily bus schedule for the next 7 days, without creating any bookings.
Safe to run again: departures that already exist are skipped.

    BASE_URL=https://your-app.vercel.app ADMIN_API_KEY=your-key python add_departures.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
DAYS = 7
PKT = timezone(timedelta(hours=5))

# origin, destination, departure hour (Pakistan time), fare, seats
SCHEDULE = [
    ("Karachi", "Hyderabad", 7, "600.00", 16),
    ("Lahore", "Islamabad", 8, "1300.00", 12),
    ("Hyderabad", "Sukkur", 10, "900.00", 16),
    ("Islamabad", "Peshawar", 12, "1200.00", 12),
    ("Multan", "Lahore", 14, "1100.00", 12),
    ("Sukkur", "Multan", 16, "1400.00", 12),
    ("Karachi", "Multan", 19, "3200.00", 16),
    ("Karachi", "Lahore", 21, "2500.00", 12),
]


def call(path, body=None):
    headers = {"Content-Type": "application/json"}
    if ADMIN_KEY:
        headers["X-API-Key"] = ADMIN_KEY
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    existing = {(r["origin"], r["destination"], r["departure_time"][:16]) for r in call("/api/routes")}
    now = datetime.now(PKT)
    added = 0
    for offset in range(DAYS + 1):
        day = now + timedelta(days=offset)
        for origin, destination, hour, price, seats in SCHEDULE:
            local = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if local <= now or local > now + timedelta(days=DAYS):
                continue
            utc = local.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
            if (origin, destination, utc[:16]) in existing:
                continue
            call("/api/routes", {
                "origin": origin, "destination": destination, "departure_time": utc,
                "price": price, "total_seats": seats, "operator_name": "CloudBus Express",
            })
            added += 1
    print(f"Added {added} departures to {BASE_URL}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit(f"Failed: {error}")
