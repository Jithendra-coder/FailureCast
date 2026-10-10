import pytest

from backend.app import security


def test_signed_session_expires_and_rejects_tampering(monkeypatch):
    now = [1_000]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    token, session_id, expiry = security.new_session("a" * 32)
    assert security.read_session(token, "a" * 32) == (session_id, expiry)

    payload, signature = token.split(".")
    tampered = ("A" if payload[0] != "A" else "B") + payload[1:] + "." + signature
    assert security.read_session(tampered, "a" * 32) is None
    assert security.read_session(token, "b" * 32) is None

    now[0] = expiry
    assert security.read_session(token, "a" * 32) is None


def test_production_requires_strong_credentials(monkeypatch):
    monkeypatch.setenv("FAILURECAST_ENV", "production")
    monkeypatch.setenv("FAILURECAST_ADMIN_PASSWORD", "weak")
    monkeypatch.setenv("FAILURECAST_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="Production requires"):
        security.validate_configuration()
