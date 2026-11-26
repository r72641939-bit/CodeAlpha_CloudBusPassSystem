"""
Fires many booking requests (500 by default) at ONE seat at the same moment.
Passes only if exactly 1 succeeds and all others get 409 Conflict.

    python stress_test.py                          # local server
    BASE_URL=https://your-app.vercel.app python stress_test.py
    PEOPLE=1000 python stress_test.py

Needs no extra packages. It creates one real booking. If ADMIN_API_KEY is
set, that booking is cancelled afterwards so the seat is free again.
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
PEOPLE = int(os.environ.get("PEOPLE", "500"))


def call(path, body=None, headers=None, method=None):
    """Returns (status, json). Status 0 means no response at all."""
    request = urllib.request.Request(
        BASE_URL + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None
    except Exception as error:
        return 0, str(error)


def find_free_seat():
    status, routes = call("/api/routes")
    if status != 200 or not routes:
        sys.exit(f"Could not load routes from {BASE_URL} (status {status}).")
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    upcoming = [r for r in routes if r["departure_time"] > now]
    for route in sorted(upcoming, key=lambda r: r["departure_time"]):
        status, seat_map = call(f"/api/routes/{route['id']}/seat-map")
        if status != 200:
            continue
        for seat in range(1, route["total_seats"] + 1):
            if seat not in seat_map["booked_seats"]:
                return route, seat
    sys.exit("No upcoming route has a free seat. Run add_departures.py first.")


def main():
    route, seat = find_free_seat()
    print(f"Target: {BASE_URL}")
    print(f"{PEOPLE} people booking seat {seat}, {route['origin']} to {route['destination']}\n")
    start = threading.Barrier(PEOPLE)

    def person(number):
        start.wait()  # everyone sends at the same moment
        return call("/api/bookings", {
            "route_id": route["id"],
            "seat_number": seat,
            "passenger_name": f"Race Tester {number}",
            "passenger_email": f"race.tester{number}@example.com",
        })

    with ThreadPoolExecutor(max_workers=PEOPLE) as pool:
        results = list(pool.map(person, range(1, PEOPLE + 1)))

    counts = Counter(status for status, _ in results)
    won = [data for status, data in results if status == 200]
    errors = PEOPLE - counts[200] - counts[409]
    print(f"Booked (200):          {counts[200]}")
    print(f"Seat taken (409):      {counts[409]}")
    print(f"Other errors:          {errors}")
    for status, count in counts.items():
        if status not in (200, 409):
            print(f"  status {status}: {count}")

    status, seat_map = call(f"/api/routes/{route['id']}/seat-map")
    stored = seat_map["booked_seats"].count(seat) if status == 200 else "unknown"
    print(f"Bookings for the seat: {stored}")

    if ADMIN_KEY:
        for booking in won:
            status, _ = call(f"/api/bookings/{booking['id']}/cancel", headers={"X-API-Key": ADMIN_KEY}, method="POST")
            print("Test booking cancelled." if status == 200 else f"Could not cancel the test booking ({status}).")

    passed = counts[200] == 1 and counts[409] == PEOPLE - 1 and stored == 1
    if not passed and counts[200] <= 1 and stored in (0, 1):
        print("\nNo double booking, but not every request got a normal answer.")
    print("\nPASS" if passed else "\nFAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
