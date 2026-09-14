from __future__ import annotations

import time
import uuid
from collections import defaultdict

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_hasher = PasswordHasher()

SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(hash_: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(hash_, plaintext)
    except VerifyMismatchError:
        return False


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="admin-session")


def issue_session(secret_key: str, admin_id: uuid.UUID) -> str:
    return _serializer(secret_key).dumps({"admin_id": str(admin_id)})


def verify_session(secret_key: str, token: str) -> uuid.UUID | None:
    try:
        data = _serializer(secret_key).loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return uuid.UUID(data["admin_id"])
    except (KeyError, ValueError, TypeError):
        return None


class RateLimiter:
    """In-memory sliding-window limiter. Fine for a single Render instance in
    test; swap for a shared store (e.g. Redis) if the admin API is ever
    scaled to multiple instances."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.time()
        self._hits[key] = [t for t in self._hits[key] if now - t < self._window]
        if len(self._hits[key]) >= self._max_attempts:
            return False
        self._hits[key].append(now)
        return True


login_rate_limiter = RateLimiter()
