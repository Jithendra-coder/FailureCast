import pytest
from fastapi.testclient import TestClient

from backend.app import db, main, ml
from backend.app.main import MAX_REQUEST_BYTES, RequestBodyLimitMiddleware, app, startup
from backend.app import worker


def cmapss_bytes(*engine_ids):
    lines = []
    for engine_id in engine_ids:
        for cycle in range(1, 4):
            values = [engine_id, cycle, .1, .2, .3, *[float(cycle)] * 21]
            lines.append(" ".join(map(str, values)))
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    for key in ("FAILURECAST_ENV", "FAILURECAST_ADMIN_PASSWORD", "FAILURECAST_SECRET_KEY", "FAILURECAST_COOKIE_SECURE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "failurecast.sqlite3")
    monkeypatch.setattr(ml, "ROOT", tmp_path)
    monkeypatch.setattr(ml, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(ml, "EXPERIMENT_DIR", tmp_path / "experiments")
    ml.MODEL_DIR.mkdir()
    ml.EXPERIMENT_DIR.mkdir()
    ml.MODEL_CACHE.clear()
    monkeypatch.setattr(ml, "log_mlflow", lambda *_args: {"warning": "tracking disabled in tests"})
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    with TestClient(app) as test_client:
        yield test_client


def test_health_overview_and_prediction_validation(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    overview = client.get("/api/v1/overview").json()
    assert overview["simulation_only"] is True
    assert overview["summary"]["engines"] == 16
    invalid = client.post("/api/v1/predictions", json={"engine_id": "ENG-test", "sequence": [{"cycle": 1}]})
    assert invalid.status_code == 422


def test_readiness_fails_when_the_stored_dataset_could_not_be_restored(client):
    main.app.state.startup_dataset_error = "stored dataset is unavailable"

    response = client.get("/api/v1/ready")
    inference = client.get("/api/v1/engines")

    main.app.state.startup_dataset_error = None
    assert response.status_code == 503
    assert response.json()["detail"] == "The stored dataset could not be restored."
    assert inference.status_code == 503


def test_dataset_import_is_validated_versioned_and_reusable(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setattr(main, "RAW_DIR", tmp_path / "data" / "raw")
    source_files = {
        "train_FD001.txt": cmapss_bytes(1, 2, 3),
        "test_FD001.txt": cmapss_bytes(10, 11),
        "RUL_FD001.txt": b"5\n7\n",
    }
    files = [("files", (name, content, "text/plain")) for name, content in source_files.items()]

    imported = client.post("/api/v1/datasets/import", data={"subset": "FD001"}, files=files)

    assert imported.status_code == 201
    assert imported.json()["active"] is True
    assert imported.json()["reused"] is False
    dataset_dir = main.RAW_DIR / imported.json()["id"]
    assert {path.name: path.read_bytes() for path in dataset_dir.iterdir()} == source_files
    assert client.get("/api/v1/overview").json()["dataset"]["id"] == imported.json()["id"]

    reused = client.post("/api/v1/datasets/import", data={"subset": "FD001"}, files=files)

    assert reused.status_code == 201
    assert reused.json()["id"] == imported.json()["id"]
    assert reused.json()["reused"] is True

    (dataset_dir / "train_FD001.txt").write_bytes(b"modified after import")
    row = db.one("SELECT * FROM datasets WHERE id=?", (imported.json()["id"],))
    with pytest.raises(ValueError, match="SHA-256 fingerprint"):
        main.load_uploaded_dataset(row)


def test_import_train_promote_and_evaluate_uses_the_same_dataset_version(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setattr(main, "RAW_DIR", tmp_path / "data" / "raw")
    files = [("files", (name, content, "text/plain")) for name, content in {
        "train_FD001.txt": cmapss_bytes(1, 2, 3, 4),
        "test_FD001.txt": cmapss_bytes(10, 11),
        "RUL_FD001.txt": b"5\n7\n",
    }.items()]

    imported = client.post("/api/v1/datasets/import", data={"subset": "FD001"}, files=files)
    assert imported.status_code == 201
    assert client.get("/api/v1/engines").status_code == 409
    assert client.get("/api/v1/overview").json()["model_ready"] is False

    queued = client.post("/api/v1/training/jobs", json={"algorithm": "MeanBaseline"})
    assert queued.status_code == 202
    assert queued.json()["dataset_id"] == imported.json()["id"]
    assert worker.run_once("dataset-e2e-test") is True
    job = client.get(f"/api/v1/training/jobs/{queued.json()['id']}").json()
    candidate_id = job["result"]["model_id"]
    candidate = client.post(f"/api/v1/models/{candidate_id}/promote", json={"approved": True})
    evaluation = client.post(f"/api/v1/models/{candidate_id}/evaluate")

    assert candidate.status_code == 200
    assert evaluation.status_code == 200
    assert evaluation.json()["dataset_id"] == imported.json()["id"]
    assert evaluation.json()["test_engines"] == 2
    assert evaluation.json()["simulation_only"] is False


def test_promotion_rejects_a_missing_candidate_artifact_without_switching_active_model(client):
    queued = client.post("/api/v1/training/jobs", json={"algorithm": "MeanBaseline"}).json()
    assert worker.run_once("missing-artifact-test") is True
    candidate_id = client.get(f"/api/v1/training/jobs/{queued['id']}").json()["result"]["model_id"]
    candidate = db.one("SELECT * FROM models WHERE id=?", (candidate_id,))
    active_before = db.one("SELECT id FROM models WHERE status='active'")["id"]
    (ml.ROOT / candidate["artifact_path"]).unlink()

    response = client.post(f"/api/v1/models/{candidate_id}/promote", json={"approved": True})

    assert response.status_code == 409
    assert db.one("SELECT id FROM models WHERE status='active'")["id"] == active_before


def test_replay_and_reversible_drift_simulation(client):
    replay = client.post("/api/v1/replay/sessions", json={"engine_id": "ENG-001", "speed": 1}).json()
    stepped = client.post(f"/api/v1/replay/{replay['id']}/step").json()
    assert stepped["latest"]["observed"] is True
    assert stepped["position"] == 1
    client.post("/api/v1/monitoring/drift/simulate", json={"enabled": True, "sensor": "sensor_2", "sigma": 4})
    assert client.get("/api/v1/monitoring/drift").json()["status"] == "investigate"
    client.post("/api/v1/monitoring/drift/simulate", json={"enabled": False})
    assert client.get("/api/v1/monitoring/drift").json()["simulation"] is None


def test_drift_baseline_samples_the_full_sorted_training_history(client, monkeypatch):
    from backend.app.data import SENSORS

    rows = [{sensor: value for sensor in SENSORS} for value in (0.0,) * 1000 + (100.0,) * 2000]
    history = [{sensor: 0.0 for sensor in SENSORS} for _ in range(12)]
    monkeypatch.setattr(main, "current_dataset", lambda: {"train_records": rows, "engines": [{"history": history}]})

    report = client.get("/api/v1/monitoring/drift").json()

    sensor = next(item for item in report["items"] if item["sensor"] == "sensor_2")
    assert sensor["shift_sigma"] < 3
    assert report["status"] == "stable"


def test_admin_session_protects_api_and_can_be_revoked(client, monkeypatch):
    monkeypatch.setenv("FAILURECAST_ENV", "production")
    monkeypatch.setenv("FAILURECAST_ADMIN_PASSWORD", "a-unique-production-passphrase")
    monkeypatch.setenv("FAILURECAST_SECRET_KEY", "0123456789abcdef" * 3)
    monkeypatch.setenv("FAILURECAST_COOKIE_SECURE", "false")
    origin = {"Origin": "http://localhost:5173"}

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/overview").status_code == 401
    denied = client.post("/api/v1/auth/login", headers=origin, json={"password": "wrong"})
    assert denied.status_code == 401
    logged_in = client.post("/api/v1/auth/login", headers=origin, json={"password": "a-unique-production-passphrase"})
    assert logged_in.status_code == 200
    assert "httponly" in logged_in.headers["set-cookie"].lower()
    assert client.get("/api/v1/overview").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=origin).json()["authenticated"] is False
    assert client.get("/api/v1/overview").status_code == 401


def test_login_attempts_are_limited(client, monkeypatch):
    monkeypatch.setenv("FAILURECAST_ENV", "production")
    monkeypatch.setenv("FAILURECAST_ADMIN_PASSWORD", "a-unique-production-passphrase")
    monkeypatch.setenv("FAILURECAST_SECRET_KEY", "0123456789abcdef" * 3)
    headers = {"Origin": "http://localhost:5173"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", headers=headers, json={"password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", headers=headers, json={"password": "wrong"}).status_code == 429


def test_training_job_survives_api_queue_and_is_completed_by_worker(client):
    queued = client.post("/api/v1/training/jobs", json={"algorithm": "MeanBaseline"})
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert worker.run_once("test-worker") is True
    job = client.get(f"/api/v1/training/jobs/{queued.json()['id']}").json()
    assert job["status"] == "completed"
    assert job["dataset_id"] == "demo-fd001-v1"
    assert job["result"]["algorithm"] == "MeanBaseline"


def test_candidate_requires_approval_and_can_be_evaluated_and_rolled_back(client):
    queued = client.post("/api/v1/training/jobs", json={"algorithm": "MeanBaseline"}).json()
    assert worker.run_once("registry-workflow-test") is True
    model_id = client.get(f"/api/v1/training/jobs/{queued['id']}").json()["result"]["model_id"]

    denied = client.post(f"/api/v1/models/{model_id}/promote", json={"approved": False})
    assert denied.status_code == 422
    promoted = client.post(f"/api/v1/models/{model_id}/promote", json={"approved": True})
    assert promoted.status_code == 200
    evaluation = client.post(f"/api/v1/models/{model_id}/evaluate")
    assert evaluation.status_code == 200
    assert evaluation.json()["simulation_only"] is True
    assert evaluation.json()["test_engines"] == 16

    rolled_back = client.post("/api/v1/models/rollback")
    assert rolled_back.status_code == 200
    assert rolled_back.json()["id"] != model_id
    assert next(model for model in client.get("/api/v1/models").json()["items"] if model["id"] == model_id)["status"] == "approved"


def test_worker_recovery_reuses_candidate_registered_before_restart(client):
    queued = client.post("/api/v1/training/jobs", json={"algorithm": "MeanBaseline"}).json()
    ml.fit_candidate(worker.training_records("demo-fd001-v1"), "MeanBaseline", "demo-fd001-v1", queued["id"])
    assert worker.run_once("restarted-worker") is True
    job = client.get(f"/api/v1/training/jobs/{queued['id']}").json()
    assert job["status"] == "completed"
    assert job["result"]["recovered"] is True
    assert len(db.rows("models", 100)) == 2


def test_replay_progress_is_restored_after_restart(client):
    replay = client.post("/api/v1/replay/sessions", json={"engine_id": "ENG-001", "speed": 1}).json()
    stepped = client.post(f"/api/v1/replay/{replay['id']}/step").json()
    assert stepped["position"] == 1
    startup()
    restored = client.get(f"/api/v1/replay/{replay['id']}/status").json()
    assert restored["position"] == 1
    assert restored["latest"]["cycle"] == stepped["latest"]["cycle"]
    assert client.get("/api/v1/replay/sessions").json()["items"][0]["id"] == replay["id"]


def test_chunked_request_body_is_limited():
    import asyncio

    messages = [{"type": "http.request", "body": b"x" * (MAX_REQUEST_BYTES + 1), "more_body": False}]
    sent = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        while (await receive()).get("more_body"):
            pass

    scope = {"type": "http", "method": "POST", "path": "/api/v1/predictions", "headers": [], "asgi": {"version": "3.0"}}
    asyncio.run(RequestBodyLimitMiddleware(downstream)(scope, receive, send))
    assert sent[0]["status"] == 413
