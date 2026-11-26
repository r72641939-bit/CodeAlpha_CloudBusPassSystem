"""Which caller a request comes from, for rate limiting."""
import hashlib
import os


def client_ip(headers, peer_host) -> str:
    """Forwarding headers can be forged, so they are trusted only on Vercel,
    which overwrites them itself."""
    if os.environ.get("VERCEL"):
        forwarded = headers.get("x-real-ip") or headers.get("x-forwarded-for", "").split(",")[0]
        if forwarded.strip():
            return forwarded.strip()
    return peer_host or "unknown"


def limit_key(action: str, ip: str) -> str:
    # Only a hash is stored, not the address itself.
    return f"{action}:{hashlib.sha256(ip.encode()).hexdigest()[:32]}"
