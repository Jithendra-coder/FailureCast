from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

SESSION_TTL = 12 * 60 * 60
SESSION_COOKIE = "failurecast_session"


def authentication_enabled() -> bool:
    return os.getenv("FAILURECAST_ENV", "development").lower() == "production" or bool(
        os.getenv("FAILURECAST_ADMIN_PASSWORD") or os.getenv("FAILURECAST_SECRET_KEY")
    )


def validate_configuration() -> None:
    password = os.getenv("FAILURECAST_ADMIN_PASSWORD", "")
    secret = os.getenv("FAILURECAST_SECRET_KEY", "")
    production = os.getenv("FAILURECAST_ENV", "development").lower() == "production"
    if production and (len(password) < 14 or len(secret.encode()) < 32):
        raise RuntimeError("Production requires FAILURECAST_ADMIN_PASSWORD (14+ characters) and FAILURECAST_SECRET_KEY (32+ bytes).")
    if bool(password) != bool(secret):
        raise RuntimeError("Set both FAILURECAST_ADMIN_PASSWORD and FAILURECAST_SECRET_KEY to enable authentication.")
    if password and (len(password) < 14 or len(secret.encode()) < 32):
        raise RuntimeError("Authentication requires a 14+ character admin password and a 32+ byte session secret.")


def sign_in(password: str) -> bool:
    configured = os.getenv("FAILURECAST_ADMIN_PASSWORD", "")
    return bool(configured) and hmac.compare_digest(hashlib.sha256(password.encode()).digest(), hashlib.sha256(configured.encode()).digest())


def new_session(secret: str) -> tuple[str, str, int]:
    session_id = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + SESSION_TTL
    payload = f"{session_id}:{expires_at}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    token = f"{_encode(payload)}.{_encode(signature)}"
    return token, session_id, expires_at


def read_session(token: str | None, secret: str) -> tuple[str, int] | None:
    if not token:
        return None
    try:
        payload_text, signature_text = token.split(".", 1)
        payload, signature = _decode(payload_text), _decode(signature_text)
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        session_id, expires_text = payload.decode().rsplit(":", 1)
        expires_at = int(expires_text)
        if expires_at <= int(time.time()):
            return None
        return session_id, expires_at
    except (ValueError, UnicodeDecodeError):
        return None


def login_key(address: str, secret: str) -> str:
    return hmac.new(secret.encode(), address.encode(), hashlib.sha256).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
