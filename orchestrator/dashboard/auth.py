"""Session auth for Mission Control — active when DASHBOARD_PASSWORD is set.

Signed-cookie sessions with no extra dependencies:
    cookie = "<expiry>:<hmac_sha256(secret, user + expiry)>"
The secret is DASHBOARD_SECRET, or derived from the credentials so sessions
survive pod restarts without extra configuration.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

COOKIE_NAME = "zyvor_qa_session"
SESSION_HOURS = 12
REMEMBER_DAYS = 30

OPEN_PATHS = {"/health", "/login", "/api/login", "/favicon.ico"}
PROTECTED_PREFIXES = ("/dashboard", "/api/dashboard", "/reports", "/screenshots")


def enabled() -> bool:
    return bool(os.environ.get("DASHBOARD_PASSWORD"))


def username() -> str:
    return os.environ.get("DASHBOARD_USER", "admin")


def _secret() -> bytes:
    explicit = os.environ.get("DASHBOARD_SECRET")
    if explicit:
        return explicit.encode()
    seed = f"{username()}:{os.environ.get('DASHBOARD_PASSWORD', '')}"
    return hashlib.sha256(seed.encode()).digest()


def verify_credentials(user: str, password: str) -> bool:
    ok_user = hmac.compare_digest((user or "").encode(), username().encode())
    ok_pass = hmac.compare_digest(
        (password or "").encode(),
        os.environ.get("DASHBOARD_PASSWORD", "").encode(),
    )
    if not (ok_user and ok_pass):
        time.sleep(1.0)  # cheap brute-force damping
        return False
    return True


def _sign(expiry: int) -> str:
    return hmac.new(_secret(), f"{username()}:{expiry}".encode(), hashlib.sha256).hexdigest()


def issue_token(remember: bool = False) -> tuple[str, int]:
    """Return (cookie value, max_age seconds)."""
    max_age = REMEMBER_DAYS * 86400 if remember else SESSION_HOURS * 3600
    expiry = int(time.time()) + max_age
    return f"{expiry}:{_sign(expiry)}", max_age


def validate_token(token: str | None) -> bool:
    if not token or ":" not in token:
        return False
    expiry_raw, sig = token.split(":", 1)
    try:
        expiry = int(expiry_raw)
    except ValueError:
        return False
    if expiry < time.time():
        return False
    return hmac.compare_digest(sig, _sign(expiry))


def is_authenticated(request: Any) -> bool:
    if not enabled():
        return True
    return validate_token(request.cookies.get(COOKIE_NAME))


def requires_auth(path: str) -> bool:
    if not enabled():
        return False
    if path.rstrip("/") in OPEN_PATHS or path == "/webhook/github":
        return False
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?") or path.startswith(p)
               for p in PROTECTED_PREFIXES)
