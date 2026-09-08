"""
Seeds a few bus routes, books a couple of normal seats, then fires many
SIMULTANEOUS booking requests at the exact same seat - the classic
overselling race condition - to prove only one of them can ever succeed.

Run this AFTER the server is up:
    python seed_demo_data.py
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx

BASE_URL = "http://localhost:8000"

ROUTES = [
    {"origin": "Karachi", "destination": "Lahore", "hours_from_now": 6, "price": "2500.00", "total_seats": 12, "operator_name": "CloudBus Express"},
    {"origin": "Islamabad", "destination": "Peshawar", "hours_from_now": 10, "price": "1200.00", "total_seats": 12, "operator_name": "CloudBus Express"},
    {"origin": "Karachi", "destination": "Hyderabad", "hours_from_now": 3, "price": "600.00", "total_seats": 16, "operator_name": "CloudBus Express"},
    {"origin": "Hyderabad", "destination": "Sukkur", "hours_from_now": 5, "price": "900.00", "total_seats": 16, "operator_name": "CloudBus Express"},
    {"origin": "Sukkur", "destination": "Multan", "hours_from_now": 8, "price": "1400.00", "total_seats": 12, "operator_name": "CloudBus Express"},
    {"origin": "Multan", "destination": "Lahore", "hours_from_now": 4, "price": "1100.00", "total_seats": 12, "operator_name": "CloudBus Express"},
    {"origin": "Lahore", "destination": "Islamabad", "hours_from_now": 3, "price": "1300.00", "total_seats": 12, "operator_name": "CloudBus Express"},
    {"origin": "Karachi", "destination": "Multan", "hours_from_now": 9, "price": "3200.00", "total_seats": 16, "operator_name": "CloudBus Express"},
]


def seed_routes():
    print("=== Seeding routes ===")
    created_ids = []
    now = datetime.utcnow()
    for r in ROUTES:
        payload = {
            "origin": r["origin"],
            "destination": r["destination"],
            "departure_time": (now + timedelta(hours=r["hours_from_now"])).isoformat(),
            "price": r["price"],
            "total_seats": r["total_seats"],
            "operator_name": r["operator_name"],
        }
        res = httpx.post(f"{BASE_URL}/api/routes", json=payload, timeout=10)
        if res.status_code == 200:
            route = res.json()
            created_ids.append(route["id"])
            print(f"[CREATED] {r['origin']} -> {r['destination']} ({route['id']})")
        else:
            print(f"[FAILED]  {r['origin']} -> {r['destination']} -> {res.status_code} {res.text}")
    print()
    return created_ids


def book_normal_seat(route_id, seat_number, name, email):
    res = httpx.post(
        f"{BASE_URL}/api/bookings",
        json={"route_id": route_id, "seat_number": seat_number, "passenger_name": name, "passenger_email": email},
        timeout=10,
    )
    status = "CONFIRMED" if res.status_code == 200 else f"FAILED ({res.status_code})"
    email_note = ""
    if res.status_code == 200:
        email_note = " · email sent" if res.json().get("email_sent") else " · email skipped (SMTP not configured)"
    print(f"[{status}] Seat {seat_number} for {name}{email_note}")
    return res


def attempt_book(route_id, seat_number, name):
    """Used by the concurrency test - returns True if this attempt won the seat."""
    email = f"{name.replace(' ', '.').lower()}@example.com"
    res = httpx.post(
        f"{BASE_URL}/api/bookings",
        json={"route_id": route_id, "seat_number": seat_number, "passenger_name": name, "passenger_email": email},
        timeout=10,
    )
    return res.status_code == 200


def run_concurrency_test(route_id, seat_number=5, num_attempts=10):
    print(f"\n=== Firing {num_attempts} SIMULTANEOUS booking requests at seat {seat_number} ===")
    names = [f"Race Tester {i}" for i in range(num_attempts)]

    with ThreadPoolExecutor(max_workers=num_attempts) as executor:
        results = list(executor.map(lambda n: attempt_book(route_id, seat_number, n), names))

    succeeded = sum(results)
    print(f"\nResult: {succeeded} of {num_attempts} simultaneous requests succeeded.")
    if succeeded == 1:
        print("CORRECT: exactly one booking won the race - no double-booking occurred.")
    else:
        print(f"UNEXPECTED: {succeeded} bookings succeeded for the same seat - investigate.")


def run():
    route_ids = seed_routes()
    if not route_ids:
        print("No routes were created - check the server is running and try again.")
        return
    route_id = route_ids[0]

    print(f"Using route: {route_id}\n")
    book_normal_seat(route_id, 1, "Ram Jethani", "ram@example.com")
    book_normal_seat(route_id, 2, "Ram Jethani (test 2)", "ram.test2@example.com")

    run_concurrency_test(route_id, seat_number=5, num_attempts=10)

    print("\nDone. Open the dashboard or GET /api/bookings/stats to see the results.")


if __name__ == "__main__":
    run()
