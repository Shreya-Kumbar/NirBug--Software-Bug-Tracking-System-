"""Security utilities (Cyber-security layer).

* Password hashing: PBKDF2-SHA256 with random salt (werkzeug)
* Password policy validation
* Signed, expiring bearer tokens (HMAC-SHA256 via itsdangerous)
* Account lockout after repeated failed logins (brute-force protection)
* Simple in-memory rate limiter (sliding window)
* Security HTTP headers (CSP, X-Frame-Options, ...)
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
TOKEN_TTL_SECONDS = 8 * 3600


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def password_problems(password: str) -> list[str]:
    """Returns a list of policy violations (empty list = strong enough)."""
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", password):
        problems.append("a lowercase letter")
    if not re.search(r"\d", password):
        problems.append("a digit")
    return problems


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


class TokenManager:
    """Issues and verifies tamper-proof tokens containing the user id and role."""

    def __init__(self, secret_key: str):
        self._s = URLSafeTimedSerializer(secret_key, salt="bugsense-auth")

    def issue(self, user_id: int, role: str) -> str:
        return self._s.dumps({"uid": user_id, "role": role})

    def verify(self, token: str, max_age: int = TOKEN_TTL_SECONDS):
        try:
            return self._s.loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max = max_requests
        self.window = window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return False
        q.append(now)
        return True


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"
    ),
}
