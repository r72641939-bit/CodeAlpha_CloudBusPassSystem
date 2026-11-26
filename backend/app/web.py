"""
Security headers and the files search engines and AI assistants read.
Plain Python (no framework imports) so it can be tested on its own.
"""
import base64
import hashlib
import os
import re
from xml.sax.saxutils import escape

SITE_URL = (os.environ.get("SITE_URL") or "https://code-alpha-cloud-bus-pass-system.vercel.app").strip().rstrip("/")

CITIES = ["Karachi", "Hyderabad", "Sukkur", "Multan", "Lahore", "Islamabad", "Peshawar"]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def render_page(html: str) -> str:
    return html.replace("__SITE_URL__", SITE_URL)


def content_security_policy(html: str) -> str:
    """Only the page's own inline scripts (matched by hash) may run, so
    injected script is blocked by the browser."""
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, flags=re.S)
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
        for s in scripts
    )
    return "; ".join([
        "default-src 'self'",
        f"script-src {hashes}",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        # localhost is for opening the page as a local file during development.
        "connect-src 'self' http://localhost:8000",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


def robots_txt() -> str:
    # /api/routes stays crawlable: search engines need it to render departures.
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/bookings\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def sitemap_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{escape(SITE_URL + '/')}</loc></url>\n"
        "</urlset>\n"
    )


def llms_txt() -> str:
    return f"""# CloudBus

> Online seat booking for intercity buses in Pakistan. A cloud computing internship project built by Ram Jethani.

## Facts
- Cities: {", ".join(CITIES)}. Available trips change; check the live list.
- Booking needs a passenger name and email address. No account is needed.
- One booking reserves one seat. Two people cannot hold the same seat.
- Fares are in Pakistani rupees and set by the server.
- No online payment is taken on this website.
- Departure times are shown in Pakistan time (UTC+5).
- Passengers can cancel online up to 1 hour before departure, with the ticket ID and email.

## Pages and data
- [Book a seat]({SITE_URL}/): departures, seat map and ticket
- [Departures (JSON)]({SITE_URL}/api/routes): times in this data are UTC
- [API documentation]({SITE_URL}/docs)
"""
