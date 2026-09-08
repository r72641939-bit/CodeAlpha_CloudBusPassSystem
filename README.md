# Cloud-Based Bus Pass System

**Built by Ram Jethani — CodeAlpha Cloud Computing Internship, Task 3**

An online bus ticket booking system built around the two failure modes that actually break real booking systems: **double-booked seats** (two people getting sold the same seat) and **price tampering** (a client submitting its own price instead of the real one). Both are prevented structurally, not just checked for — and both are demonstrated live, not just claimed.

---

## A note on scope, upfront

Task 3 as originally described also asks for "dynamically provisioning servers" to "handle high traffic." That specific piece - real cloud auto-scaling infrastructure (load balancers, auto-scaling groups) - needs a paid cloud account and live load-testing to demonstrate honestly, which isn't something this project fakes. Instead, this README discusses *how* the system is designed to scale (see "Scaling design" below) without claiming infrastructure that isn't actually deployed. What **is** fully built and genuinely tested is the part of "handling high traffic" that matters most for a booking system: **staying correct under concurrent load**, which is demonstrated below.

## The problem

Two classic booking-system bugs:

1. **Overselling.** Two passengers tap "Book" on seat 14 within the same second. A naive system checks "is seat 14 free?", both checks say yes, both bookings go through, and now two people show up for one seat.
2. **Price tampering.** If the client (a phone app, a hacked request) is allowed to say "I'm paying $5 for this," and the server trusts it, that's a direct revenue loss.

## How it's actually prevented

### 1. Seat safety under concurrency

```
Two simultaneous booking requests for the SAME seat:

Request A ──┐
            ├──▶  SELECT route FOR UPDATE  ──▶  (A acquires the lock)
Request B ──┘                                    B now WAITS

                   A checks: is seat 14 booked? No.
                   A creates the booking, commits.
                   A's transaction ends → lock released.

                   B (was waiting) now proceeds:
                   B checks: is seat 14 booked? YES (A just took it).
                   B is rejected with 409 Conflict.
```

`SELECT ... FOR UPDATE` locks the route row for the duration of the transaction, so the second request is forced to wait until the first one fully finishes before it's even allowed to check seat availability. A partial unique database index (`route_id + seat_number`, confirmed bookings only) sits underneath as a second, database-enforced guarantee - so even in an edge case the application logic didn't anticipate, two CONFIRMED bookings for the same seat can never both exist in the database.

**This was actually tested**, not just written and hoped for. A concurrency simulation (same lock-then-check-then-act pattern) was run with 50 simultaneous booking attempts on the same seat:

- **With the locking pattern**: exactly 1 of 50 succeeded, every time.
- **With the exact same code but the lock removed**: 46 of 50 succeeded - a real overselling bug, reproduced on purpose to prove the lock is actually doing something, not just decorative.

The full integration test suite (`tests/test_booking_engine.py`) includes a real version of this test running against an actual PostgreSQL database with real threads and real `SELECT ... FOR UPDATE` locking.

### 2. Price integrity

The booking request schema (`BookingIn` in `schemas.py`) has no `price` field at all. It's not validated or overridden - it's structurally absent from what the client is even allowed to send. The price stored on every booking is read directly from `route.price` at the moment of booking, server-side, every time. There is no code path where a client-submitted price reaches the database.

### 3. Booking confirmation email

Every successful booking triggers a best-effort confirmation email (HTML + plain-text) with the route, departure time, seat number, price, and booking reference. "Best-effort" is a deliberate design choice: a passenger's seat is real and reserved the instant the database transaction commits - if the email provider is slow, misconfigured, or unreachable, the booking must still stand. Email sending never blocks or fails the booking response; the outcome is recorded on `Booking.email_sent` and shown honestly in both the API response and the dashboard ("Confirmation emailed to..." vs. "Email not sent (SMTP not configured)").

If `SMTP_HOST` isn't set in `.env`, email sending is skipped entirely and bookings still work normally - useful for local testing without needing real email credentials.

## Scaling design (discussed, not deployed)

Since real auto-scaling infrastructure is out of scope here, this section explains how the current design *would* scale if deployed:

- **The API is stateless.** No session state is kept in memory between requests, so multiple copies of this exact FastAPI app could run behind a load balancer with no code changes.
- **The bottleneck under real load would be the route-row lock during booking**, which is intentional and correct - it's what prevents overselling. At very high traffic on a single popular route, this becomes a queuing point; the standard fix is sharding hot routes or using a dedicated seat-reservation queue (e.g. Redis-based) ahead of the database, which is a reasonable "next step" to mention if asked, without pretending it's already built here.
- **PostgreSQL connection pooling** (already used via SQLAlchemy) is what allows many API instances to share a manageable number of real database connections.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Consistent with Tasks 1 & 2; async, auto docs at `/docs` |
| Database | PostgreSQL + SQLAlchemy | Real row-level locking (`FOR UPDATE`) and partial unique indexes - both genuine Postgres features |
| Frontend | Vanilla HTML/CSS/JS | Zero build tooling, animated seat-map interaction |
| Testing | pytest | Unit tests (reference codes) + real concurrency integration tests against Postgres |
| Containerization | Docker + Docker Compose | One-command local setup, no manual database installation needed |
| CI/CD | GitHub Actions | Runs the real test suite (including the concurrency test) against a disposable Postgres database on every push |

## Project structure

```
CodeAlpha_CloudBusPassSystem/
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions: real tests against a real Postgres service
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # Settings (env-driven)
│   │   ├── database.py              # SQLAlchemy engine/session
│   │   ├── models.py                # Route, Booking + partial unique index
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── core/
│   │   │   ├── booking_engine.py    # The concurrency-safe, price-integrity core
│   │   │   ├── reference.py         # Booking reference code generator
│   │   │   └── email_service.py     # Best-effort booking confirmation emails
│   │   └── routers/
│   │       ├── routes.py            # List routes, seat maps, create route (admin)
│   │       └── bookings.py          # Book, list, cancel, stats
│   ├── tests/
│   │   ├── test_reference.py        # Pure unit tests
│   │   ├── test_email_service.py    # Message construction + graceful-failure tests
│   │   └── test_booking_engine.py   # Integration tests (needs real Postgres)
│   ├── seed_demo_data.py            # Seeds routes + runs a live concurrency test
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html                   # Animated seat-map booking UI
├── docker-compose.yml                # One-command local stack: backend + Postgres
└── README.md
```

## Setup

### 1. Prerequisites
- Python 3.10+
- PostgreSQL (local, or free tier from [Neon](https://neon.tech) / [Supabase](https://supabase.com))

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env with your real DATABASE_URL

uvicorn app.main:app --reload
```

API docs: **http://localhost:8000/docs**

### 2b. Email confirmations (optional)

Bookings work fine with no email setup at all - `email_sent` will just show `false`. To actually receive confirmation emails, add SMTP credentials to `.env`. The simplest real option is Gmail with an [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification enabled first):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=youraddress@gmail.com
SMTP_PASSWORD=<16-character app password>
SMTP_FROM_EMAIL=youraddress@gmail.com
```

For testing without sending real email, [Mailtrap.io](https://mailtrap.io) (free) gives you an SMTP inbox that safely captures emails instead of delivering them anywhere.

### 3. Seed data + run the concurrency demo

In a second terminal, with the server running:

```bash
cd backend
python seed_demo_data.py
```

This creates two routes, books two normal seats under "Ram Jethani," then fires **10 simultaneous booking requests at the exact same seat** and prints how many succeeded - it should always be exactly 1.

Routes cover Karachi, Lahore, Islamabad, Peshawar, Hyderabad, Sukkur, and Multan - a realistic mix of short and long-distance intercity routes.

### 4. Frontend

Open `frontend/index.html` in a browser. Pick a route, click a seat on the animated seat map, enter a name and email, and confirm - a booking reference and price confirmation animate in.

## Alternative: run everything with Docker Compose

Instead of steps 1-3 above, if you have Docker installed, this replaces the whole manual Postgres setup with one command:

```bash
cd backend
cp .env.example .env
# optionally fill in SMTP_* values for real email - everything else is overridden by docker-compose.yml

cd ..
docker compose up --build
```

This starts a real PostgreSQL container and the backend together, wires them to each other automatically, and waits for the database to actually be ready before starting the API - avoiding the classic "backend crashes because Postgres wasn't ready yet" race condition. API available at `http://localhost:8000` same as before. `seed_demo_data.py` and `pytest` both still work exactly the same way against this database - just run them from a normal terminal (outside the container) as in steps 3-4 above, since `docker-compose.yml` publishes Postgres on the standard `localhost:5432`.

## CI/CD

`.github/workflows/ci.yml` runs automatically on every push and pull request to `main`. It spins up a real, disposable PostgreSQL database as a GitHub-hosted service container (not a mock, not SQLite standing in for it) and runs the complete test suite against it - including the real 10-thread concurrency test with actual `SELECT ... FOR UPDATE` row locking, the same test proven to work locally above. A separate job confirms the Docker image actually builds. A green checkmark on commits in this repo means the tests genuinely ran and passed on a fresh database, not just that the code was written to look correct.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/routes` | Create a route (admin utility, used by the seed script) |
| GET | `/api/routes` | List all routes |
| GET | `/api/routes/{id}/seat-map` | Get booked/available seats for a route |
| POST | `/api/bookings` | Book a seat (concurrency-safe, server-priced) |
| GET | `/api/bookings` | List all bookings |
| POST | `/api/bookings/{id}/cancel` | Cancel a booking (frees the seat for rebooking) |
| GET | `/api/bookings/stats` | Summary stats for the dashboard |

Full schemas at `/docs`.

## Running tests

```bash
cd backend
pytest tests/ -v
```

`test_reference.py` and `test_email_service.py` run standalone, no database needed. `test_booking_engine.py` needs a real PostgreSQL database configured via `.env` - it creates and cleans up its own test route, and includes the live 10-thread concurrency test described above.

---

*Built by Ram Jethani for the CodeAlpha Cloud Computing Internship, Task 3: Cloud-Based Bus Pass System.*
