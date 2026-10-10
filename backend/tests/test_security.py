import pytest

from backend.app import db, main, security
from fastapi.testclient import TestClient


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


def test_mutating_authenticated_request_rejects_an_unapproved_origin(client_for_origin):
    assert client_for_origin.get("/api/v1/overview").status_code == 200

    denied = client_for_origin.post("/api/v1/auth/logout", headers={"Origin": "https://attacker.example"})

    assert denied.status_code == 403
    assert client_for_origin.get("/api/v1/overview").status_code == 200


@pytest.fixture
def client_for_origin(tmp_path, monkeypatch):
    from backend.app import ml

    monkeypatch.setenv("FAILURECAST_ENV", "production")
    monkeypatch.setenv("FAILURECAST_ADMIN_PASSWORD", "a-unique-production-passphrase")
    monkeypatch.setenv("FAILURECAST_SECRET_KEY", "0123456789abcdef" * 3)
    monkeypatch.setenv("FAILURECAST_COOKIE_SECURE", "false")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "failurecast.sqlite3")
    monkeypatch.setattr(ml, "ROOT", tmp_path)
    monkeypatch.setattr(ml, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(ml, "EXPERIMENT_DIR", tmp_path / "experiments")
    ml.MODEL_DIR.mkdir()
    ml.EXPERIMENT_DIR.mkdir()
    ml.MODEL_CACHE.clear()
    monkeypatch.setattr(ml, "log_mlflow", lambda *_args: {"warning": "tracking disabled in tests"})
    with TestClient(main.app) as test_client:
        login = test_client.post("/api/v1/auth/login", headers={"Origin": "http://localhost:5173"},
                                 json={"password": "a-unique-production-passphrase"})
        assert login.status_code == 200
        yield test_client
