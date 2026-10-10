from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import time

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from . import db
from .data import SENSORS, SETTINGS, feature_vector, generate_demo_records, make_dataset_engines, parse_cmapss, parse_rul, sha256, validate_records
from .ml import bootstrap_model, load_estimator, metrics_for, predict, utcnow
from . import security

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = 42 * 1024 * 1024
ALERT_THRESHOLDS = {"critical": int(os.getenv("FAILURECAST_CRITICAL_CYCLES", "15")),
                    "warning": int(os.getenv("FAILURECAST_WARNING_CYCLES", "30")),
                    "watch": int(os.getenv("FAILURECAST_WATCH_CYCLES", "60"))}
if not ALERT_THRESHOLDS["critical"] < ALERT_THRESHOLDS["warning"] < ALERT_THRESHOLDS["watch"]:
    raise RuntimeError("Alert thresholds must satisfy critical < warning < watch.")
_lock = threading.RLock()
_replays: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup()
    yield


PRODUCTION_MODE = os.getenv("FAILURECAST_ENV", "development").lower() == "production"
app = FastAPI(title="FailureCast API", version="1.0.0", description="Local-first simulated predictive-maintenance platform.",
              docs_url=None if PRODUCTION_MODE else "/api/docs", redoc_url=None if PRODUCTION_MODE else "/api/redoc",
              openapi_url=None if PRODUCTION_MODE else "/api/openapi.json",
              lifespan=lifespan)
origins = os.getenv("FAILURECAST_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
ALLOWED_ORIGINS = {origin.strip() for origin in origins if origin.strip()}


def secure_headers(response, request: Request):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    if request.url.scheme == "https" or os.getenv("FAILURECAST_COOKIE_SECURE", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        limit = MAX_UPLOAD_BODY_BYTES if path == "/api/v1/datasets/import" else MAX_REQUEST_BYTES
        header_size = next((value for name, value in scope.get("headers", []) if name == b"content-length"), None)
        if header_size:
            try:
                if int(header_size) > limit:
                    await JSONResponse({"detail": f"Request body exceeds the {limit // (1024 * 1024)} MB limit."}, status_code=413)(scope, receive, send)
                    return
            except ValueError:
                pass
        size = 0

        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > limit:
                raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await JSONResponse({"detail": f"Request body exceeds the {limit // (1024 * 1024)} MB limit."}, status_code=413)(scope, receive, send)


class RequestBodyTooLarge(Exception):
    pass


app.add_middleware(RequestBodyLimitMiddleware)


def session_id_from_request(request: Request) -> str | None:
    parsed = security.read_session(request.cookies.get(security.SESSION_COOKIE), os.getenv("FAILURECAST_SECRET_KEY", ""))
    if not parsed:
        return None
    session_id, expires_at = parsed
    session = db.one("SELECT expires_at FROM sessions WHERE id=?", (session_id,))
    if not session or session["expires_at"] != expires_at:
        return None
    return session_id


@app.middleware("http")
async def secure_api(request: Request, call_next):
    path = request.url.path
    auth_enabled = security.authentication_enabled()
    if auth_enabled and request.method not in {"GET", "HEAD", "OPTIONS"} and path.startswith("/api/v1/"):
        if request.headers.get("origin") not in ALLOWED_ORIGINS:
            return secure_headers(JSONResponse({"detail": "Request origin is not allowed."}, status_code=403), request)
    public_api = {"/api/v1/health", "/api/v1/ready", "/api/v1/auth/login", "/api/v1/auth/session"}
    if auth_enabled and path.startswith("/api/v1/") and path not in public_api and request.method != "OPTIONS":
        session_id = session_id_from_request(request)
        if not session_id:
            return secure_headers(JSONResponse({"detail": "Authentication required."}, status_code=401), request)
        request.state.session_id = session_id
    response = await call_next(request)
    return secure_headers(response, request)


app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS), allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


def state() -> dict:
    return app.state.data


def active_model() -> dict:
    model = db.one("SELECT * FROM models WHERE status='active' ORDER BY created_at DESC LIMIT 1")
    if not model:
        raise HTTPException(503, "No active model is available.")
    return db.decode(model, "metrics")


def current_dataset() -> dict:
    return state()["current"]


def level(rul: float) -> str:
    if rul <= ALERT_THRESHOLDS["critical"]:
        return "critical"
    if rul <= ALERT_THRESHOLDS["warning"]:
        return "warning"
    if rul <= ALERT_THRESHOLDS["watch"]:
        return "watch"
    return "normal"


def resolve_engine(engine_id: str) -> dict:
    normalized = str(engine_id).upper()
    for engine in current_dataset()["engines"]:
        if engine["id"].upper() == normalized or str(engine["engine_id"]) == normalized:
            return engine
    raise HTTPException(404, "Engine was not found in the selected dataset.")


def serialize_engine(engine: dict, model: dict | None = None) -> dict:
    model = model or active_model()
    estimate = predict(model, engine["history"])
    status = level(estimate)
    return {"id": engine["id"], "subset": engine["subset"], "cycle": engine["cycle"], "observed_cycles": len(engine["history"]),
            "rul": round(estimate, 1), "health": status}


def register_prediction(engine_id: str, cycle: int, rul: float, model_id: str) -> dict:
    prediction_id = uuid.uuid4().hex[:12]
    created_at = utcnow()
    severity = level(rul)
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO predictions (id, engine_id, model_id, cycle, rul, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                           (prediction_id, engine_id, model_id, cycle, rul, created_at))
        if severity != "normal":
            duplicate = connection.execute("SELECT id FROM alerts WHERE engine_id=? AND status='open' AND severity=? LIMIT 1",
                                            (engine_id, severity)).fetchone()
            if not duplicate:
                connection.execute("INSERT INTO alerts (id, engine_id, severity, status, predicted_rul, cycle, created_at) VALUES (?, ?, ?, 'open', ?, ?, ?)",
                                   (f"al-{prediction_id}", engine_id, severity, round(rul, 1), cycle, created_at))
    return {"id": prediction_id, "engine_id": engine_id, "cycle": cycle, "rul": round(rul, 1), "severity": severity,
            "model_id": model_id, "created_at": created_at}


def build_state() -> dict:
    demo_train = generate_demo_records(40, 81)
    demo_view = generate_demo_records(16, 220)
    demo_engines = make_dataset_engines(demo_view, demo=True)
    for index, engine in enumerate(demo_engines):
        engine["subset"] = "FD001"
        engine["id"] = f"ENG-{index + 1:03d}"
    demo = {"id": "demo-fd001-v1", "name": "Simulated C-MAPSS sample", "subset": "FD001", "source": "Generated local demo data",
            "created_at": None, "checksum": "synthetic", "quality": {"status": "demo", "train_engines": 40, "engines": len(demo_engines),
            "rows": len(demo_view), "schema_valid": True, "data_quality": "Simulated telemetry; not NASA source data."},
            "train_records": demo_train, "display_records": demo_view, "engines": demo_engines}
    return {"demo": demo, "current": demo, "versions": {demo["id"]: demo}}


def load_uploaded_dataset(row: dict) -> dict:
    raw_path = (ROOT / row["raw_dir"]).resolve()
    if not raw_path.is_relative_to(RAW_DIR.resolve()):
        raise ValueError("Stored dataset path is outside the raw data directory.")
    subset = row["subset"]
    train_path, test_path, rul_path = raw_path / f"train_{subset}.txt", raw_path / f"test_{subset}.txt", raw_path / f"RUL_{subset}.txt"
    train = parse_cmapss(train_path.read_bytes(), train_path.name)
    test = parse_cmapss(test_path.read_bytes(), test_path.name)
    rul = parse_rul(rul_path.read_bytes(), rul_path.name)
    engines = make_dataset_engines(test, rul)
    for engine in engines:
        engine["subset"] = subset
    return {"id": row["id"], "name": f"NASA C-MAPSS {subset}", "subset": subset, "source": "NASA C-MAPSS import",
            "created_at": row["imported_at"], "checksum": row["checksum"], "quality": json.loads(row["quality"]),
            "train_records": train, "display_records": test, "engines": engines}


def startup() -> None:
    security.validate_configuration()
    db.init_db()
    app.state.data = build_state()
    app.state.drift_override = None
    app.state.startup_dataset_error = None
    _replays.clear()
    for row in db.rows("replay_sessions", 100):
        row["history"] = json.loads(row["history"])
        row["latest"] = json.loads(row["latest"]) if row["latest"] else None
        _replays[row["id"]] = row
    existing = db.one("SELECT * FROM datasets WHERE id='demo-fd001-v1'")
    if not existing:
        demo = current_dataset()
        db.execute("INSERT INTO datasets (id, subset, source, imported_at, checksum, quality, raw_dir) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (demo["id"], demo["subset"], demo["source"], utcnow(), "synthetic", json.dumps(demo["quality"]), ""))
    latest = db.one("SELECT * FROM datasets WHERE id!='demo-fd001-v1' ORDER BY imported_at DESC LIMIT 1")
    if latest:
        try:
            restored = load_uploaded_dataset(latest)
            app.state.data["current"] = restored
            app.state.data["versions"][restored["id"]] = restored
        except (OSError, ValueError) as exc:
            app.state.startup_dataset_error = str(exc)
    bootstrap_model(app.state.data["demo"]["train_records"])
    if not db.one("SELECT id FROM predictions LIMIT 1"):
        model = active_model()
        for engine in current_dataset()["engines"]:
            register_prediction(engine["id"], engine["cycle"], predict(model, engine["history"]), model["id"])


class TrainingRequest(BaseModel):
    algorithm: str = Field(default="HistGradientBoostingRegressor", pattern="^(MeanBaseline|HistGradientBoostingRegressor|RandomForestRegressor|LSTM)$")


class ReplayRequest(BaseModel):
    engine_id: str = Field(min_length=1, max_length=32)
    speed: float = Field(default=1, ge=0.25, le=8)


class PromotionRequest(BaseModel):
    approved: bool


class DriftSimulationRequest(BaseModel):
    enabled: bool
    sensor: str = Field(default="sensor_2", pattern="^sensor_(?:[1-9]|1[0-9]|2[01])$")
    sigma: float = Field(default=4, ge=0, le=8)


class PredictionRequest(BaseModel):
    engine_id: str = Field(min_length=1, max_length=32)
    sequence: list[dict] = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "failurecast-api"}


@app.get("/api/v1/ready")
def ready():
    try:
        db.one("SELECT 1 AS ready")
        load_estimator(active_model())
        current_dataset()
    except Exception as exc:
        raise HTTPException(503, "Service dependencies are not ready.") from exc
    return {"status": "ready", "service": "failurecast-api"}


@app.get("/api/v1/auth/session")
def auth_session(request: Request):
    if not security.authentication_enabled():
        return {"required": False, "authenticated": True}
    return {"required": True, "authenticated": bool(session_id_from_request(request))}


@app.post("/api/v1/auth/login")
def login(request: Request, credentials: LoginRequest):
    if not security.authentication_enabled():
        raise HTTPException(404, "Authentication is not enabled.")
    secret = os.environ["FAILURECAST_SECRET_KEY"]
    address = request.client.host if request.client else "unknown"
    client_key = security.login_key(address, secret)
    now = int(time.time())
    if not db.consume_login_attempt(client_key, now):
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
    if not security.sign_in(credentials.password):
        raise HTTPException(401, "The password is incorrect.")
    db.clear_login_attempts(client_key)
    token, session_id, expires_at = security.new_session(secret)
    with db.connect() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute("INSERT INTO sessions (id, expires_at, created_at) VALUES (?, ?, ?)", (session_id, expires_at, now))
    response = JSONResponse({"authenticated": True})
    response.set_cookie(security.SESSION_COOKIE, token, max_age=security.SESSION_TTL, httponly=True,
                        secure=os.getenv("FAILURECAST_COOKIE_SECURE", "true" if os.getenv("FAILURECAST_ENV", "development").lower() == "production" else "false").lower() == "true",
                        samesite="strict", path="/api/v1")
    return response


@app.post("/api/v1/auth/logout")
def logout(request: Request):
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(security.SESSION_COOKIE, path="/api/v1", httponly=True,
                           secure=os.getenv("FAILURECAST_COOKIE_SECURE", "true" if os.getenv("FAILURECAST_ENV", "development").lower() == "production" else "false").lower() == "true",
                           samesite="strict")
    return response


@app.get("/api/v1/overview")
def overview():
    dataset, model = current_dataset(), active_model()
    engines = [serialize_engine(engine, model) for engine in dataset["engines"]]
    alerts = db.rows("alerts", 100)
    selected = dataset["engines"][min(3, len(dataset["engines"]) - 1)]
    history = selected["history"]
    stride = max(1, len(history) // 45)
    series = []
    for i in range(0, len(history), stride):
        window = history[:i + 1]
        prediction = predict(model, window)
        point = {"cycle": window[-1]["cycle"], "predicted_rul": round(prediction, 1)}
        truth = selected.get("rul")
        if truth is not None:
            point["actual_rul"] = round(max(0, truth + history[-1]["cycle"] - window[-1]["cycle"]), 1)
        series.append(point)
    if series[-1]["cycle"] != history[-1]["cycle"]:
        window = history
        point = {"cycle": window[-1]["cycle"], "predicted_rul": round(predict(model, window), 1)}
        if selected.get("rul") is not None:
            point["actual_rul"] = round(float(selected["rul"]), 1)
        series.append(point)
    open_alerts = [alert for alert in alerts if alert["status"] == "open"]
    return {"dataset": {"id": dataset["id"], "name": dataset["name"], "subset": dataset["subset"], "source": dataset["source"], "quality": dataset["quality"]},
            "model": {"id": model["id"], "algorithm": model["algorithm"], "status": model["status"], "metrics": model["metrics"]},
            "summary": {"engines": len(engines), "critical": sum(e["health"] == "critical" for e in engines),
                        "watch": sum(e["health"] in ("warning", "watch") for e in engines), "open_alerts": len(open_alerts),
                        "median_rul": round(float(np.median([engine["rul"] for engine in engines])), 1),
                        "running_replays": sum(item["status"] == "running" for item in _replays.values())},
            "engines": engines, "alerts": alerts[:8], "series": series, "selected_engine": selected["id"],
            "thresholds": ALERT_THRESHOLDS, "simulation_only": dataset["source"] == "Generated local demo data"}


@app.get("/api/v1/datasets")
def datasets():
    result = []
    for row in reversed(db.rows("datasets", 100)):
        item = db.decode(row, "quality")
        item.pop("raw_dir", None)
        item["active"] = item["id"] == current_dataset()["id"]
        result.append(item)
    return {"items": result}


@app.get("/api/v1/datasets/{dataset_id}/quality")
def dataset_quality(dataset_id: str):
    row = db.one("SELECT * FROM datasets WHERE id=?", (dataset_id,))
    if not row:
        raise HTTPException(404, "Dataset version was not found.")
    return {"id": dataset_id, "quality": json.loads(row["quality"]), "checksum": row["checksum"], "source": row["source"], "subset": row["subset"]}


@app.post("/api/v1/datasets/import", status_code=201)
async def import_dataset(files: list[UploadFile] = File(...), subset: str = Form("FD001")):
    subset = subset.upper()
    if subset not in {"FD001", "FD002", "FD003", "FD004"}:
        raise HTTPException(422, "Subset must be FD001, FD002, FD003, or FD004.")
    expected = {f"train_{subset}.txt", f"test_{subset}.txt", f"RUL_{subset}.txt"}
    contents = {}
    total = 0
    for upload in files:
        filename = Path(upload.filename or "").name
        if filename not in expected or filename in contents:
            raise HTTPException(422, f"Upload only the three expected files: {', '.join(sorted(expected))}.")
        content = await upload.read(MAX_FILE_BYTES + 1)
        total += len(content)
        if len(content) > MAX_FILE_BYTES or total > 40 * 1024 * 1024:
            raise HTTPException(413, "Dataset import exceeds the 20 MB per-file or 40 MB total limit.")
        contents[filename] = content
    if set(contents) != expected:
        raise HTTPException(422, f"Upload all three files: {', '.join(sorted(expected))}.")
    try:
        train = await run_in_threadpool(parse_cmapss, contents[f"train_{subset}.txt"], f"train_{subset}.txt")
        test = await run_in_threadpool(parse_cmapss, contents[f"test_{subset}.txt"], f"test_{subset}.txt")
        rul = await run_in_threadpool(parse_rul, contents[f"RUL_{subset}.txt"], f"RUL_{subset}.txt")
        train_quality = await run_in_threadpool(validate_records, train, f"train_{subset}.txt")
        test_quality = await run_in_threadpool(validate_records, test, f"test_{subset}.txt")
        if test_quality["engines"] != len(rul):
            raise ValueError(f"{test_quality['engines']} test engines but {len(rul)} RUL labels were supplied.")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    checksums = {name: sha256(data) for name, data in contents.items()}
    fingerprint = sha256("".join(checksums[name] for name in sorted(checksums)).encode())
    dataset_id = f"ds-{subset.lower()}-{fingerprint[:10]}"
    previous = db.one("SELECT * FROM datasets WHERE checksum=?", (fingerprint,))
    if previous:
        restored = load_uploaded_dataset(previous)
        with _lock:
            state()["current"] = restored
            state()["versions"][restored["id"]] = restored
        return {"id": previous["id"], "active": True, "reused": True, "quality": json.loads(previous["quality"])}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / dataset_id
    staging = RAW_DIR / f".{dataset_id}-{uuid.uuid4().hex}.upload"
    staging.mkdir(parents=False, exist_ok=False)
    try:
        for name, content in contents.items():
            (staging / name).write_bytes(content)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(500, "Could not persist uploaded dataset files.")
    quality = {"train": train_quality, "test": test_quality, "rul_labels": len(rul), "checksum_by_file": checksums,
               "status": "passed", "schema_valid": True, "missing_values": 0, "duplicate_engine_cycles": 0, "ordered_cycles": True}
    imported_at = utcnow()
    moved = False
    try:
        os.replace(staging, target)
        moved = True
        db.execute("INSERT INTO datasets (id, subset, source, imported_at, checksum, quality, raw_dir) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (dataset_id, subset, "NASA C-MAPSS import", imported_at, fingerprint, json.dumps(quality), str(target.relative_to(ROOT))))
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if moved:
            shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(500, "Could not commit the dataset version.") from exc
    dataset = {"id": dataset_id, "name": f"NASA C-MAPSS {subset}", "subset": subset, "source": "NASA C-MAPSS import", "created_at": imported_at,
               "checksum": fingerprint, "quality": quality, "train_records": train, "display_records": test, "engines": make_dataset_engines(test, rul)}
    for engine in dataset["engines"]:
        engine["subset"] = subset
    with _lock:
        state()["current"] = dataset
        state()["versions"][dataset_id] = dataset
    return {"id": dataset_id, "active": True, "reused": False, "quality": quality}


@app.get("/api/v1/engines")
def engines():
    model = active_model()
    return {"items": [serialize_engine(engine, model) for engine in current_dataset()["engines"]]}


@app.get("/api/v1/engines/{engine_id}/history")
def engine_history(engine_id: str):
    engine = resolve_engine(engine_id)
    model = active_model()
    rows = engine["history"]
    estimate = predict(model, rows)
    return {"engine": serialize_engine(engine, model), "history": rows, "prediction": round(estimate, 1),
            "series": [{"cycle": row["cycle"], "sensor_2": row["sensor_2"], "sensor_3": row["sensor_3"],
                        **{sensor: row[sensor] for sensor in SENSORS},
                        "predicted_rul": round(predict(model, rows[:index + 1]), 1),
                        **({"actual_rul": round(max(0, engine["rul"] + rows[-1]["cycle"] - row["cycle"]), 1)} if engine["rul"] is not None else {})}
                       for index, row in enumerate(rows[max(0, len(rows) - 60):], max(0, len(rows) - 60))]}


@app.post("/api/v1/predictions")
def predict_rul(request: PredictionRequest):
    required = set(SETTINGS + SENSORS + ["cycle"])
    cleaned = []
    previous_cycle = 0
    for index, row in enumerate(request.sequence):
        if not required.issubset(row):
            missing = sorted(required - set(row))
            raise HTTPException(422, f"Sequence row {index + 1} is missing required fields: {', '.join(missing)}.")
        values = [row[key] for key in required]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) for value in values):
            raise HTTPException(422, f"Sequence row {index + 1} contains an invalid numeric value.")
        if abs(row["cycle"]) > 1_000_000 or not float(row["cycle"]).is_integer() or row["cycle"] <= previous_cycle:
            raise HTTPException(422, "Sequence cycles must be strictly increasing.")
        previous_cycle = row["cycle"]
        cleaned.append({key: row[key] for key in required})
    model = active_model()
    try:
        rul = predict(model, cleaned)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, f"Active model could not produce a prediction: {exc}") from exc
    return register_prediction(request.engine_id, previous_cycle, rul, model["id"])


@app.post("/api/v1/training/jobs", status_code=202)
def start_training(request: TrainingRequest):
    dataset = current_dataset()
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM training_jobs WHERE status IN ('queued','running') LIMIT 1").fetchone():
            raise HTTPException(409, "A training job is already queued or running.")
        connection.execute("INSERT INTO training_jobs (id, status, algorithm, created_at, dataset_id) VALUES (?, 'queued', ?, ?, ?)",
                           (job_id, request.algorithm, utcnow(), dataset["id"]))
    return {"id": job_id, "status": "queued", "algorithm": request.algorithm, "dataset_id": dataset["id"]}


@app.get("/api/v1/training/jobs")
def training_jobs():
    items = [db.decode(row, "result") for row in db.rows("training_jobs", 100)]
    return {"items": items}


@app.get("/api/v1/training/jobs/{job_id}")
def training_job(job_id: str):
    result = db.decode(db.one("SELECT * FROM training_jobs WHERE id=?", (job_id,)), "result")
    if not result:
        raise HTTPException(404, "Training job was not found.")
    return result


@app.get("/api/v1/models")
def models():
    items = [db.decode(row, "metrics") for row in db.rows("models", 100)]
    return {"items": items}


@app.get("/api/v1/models/{model_id}/metrics")
def model_metrics(model_id: str):
    result = db.decode(db.one("SELECT * FROM models WHERE id=?", (model_id,)), "metrics")
    if not result:
        raise HTTPException(404, "Model version was not found.")
    return result


@app.post("/api/v1/models/{model_id}/promote")
def promote_model(model_id: str, request: PromotionRequest):
    if not request.approved:
        raise HTTPException(422, "Explicit approval is required to activate a candidate model.")
    candidate = db.one("SELECT * FROM models WHERE id=?", (model_id,))
    if not candidate or candidate["status"] != "candidate":
        raise HTTPException(409, "Only a registered candidate model can be promoted.")
    metrics = json.loads(candidate["metrics"])
    if not metrics.get("validation_engines", 0) or not np.isfinite(metrics.get("mae", float("nan"))):
        raise HTTPException(409, "Candidate has no valid engine-level validation report.")
    with db.connect() as connection:
        connection.execute("UPDATE models SET status='approved' WHERE status='active'")
        connection.execute("UPDATE models SET status='active' WHERE id=?", (model_id,))
        connection.execute("INSERT INTO audit_events (action, model_id, created_at, details) VALUES (?, ?, ?, ?)",
                           ("promote", model_id, utcnow(), json.dumps({"approved": True, "previous_model": candidate["parent_id"]})))
    return {"id": model_id, "status": "active", "message": "Candidate model is now active."}


@app.post("/api/v1/models/{model_id}/evaluate")
def evaluate_active_model(model_id: str):
    model = db.decode(db.one("SELECT * FROM models WHERE id=?", (model_id,)), "metrics")
    if not model or model["status"] != "active":
        raise HTTPException(409, "Only the active, selected model can be evaluated against the official test protocol.")
    labeled = [engine for engine in current_dataset()["engines"] if engine.get("rul") is not None]
    if not labeled:
        raise HTTPException(409, "The selected dataset has no final-cycle RUL ground truth.")
    actual, predicted = [], []
    for engine in labeled:
        actual.append(float(engine["rul"]))
        predicted.append(predict(model, engine["history"]))
    report = metrics_for(actual, predicted)
    simulation = current_dataset()["source"] == "Generated local demo data"
    report.update({"protocol": "simulated final cycle + generated RUL labels" if simulation else "final observed cycle + supplied RUL_FD00x labels",
                   "simulation_only": simulation, "test_engines": len(labeled), "dataset_id": current_dataset()["id"],
                   "model_id": model_id, "evaluated_at": utcnow()})
    db.execute("INSERT INTO audit_events (action, model_id, created_at, details) VALUES (?, ?, ?, ?)",
               ("official_test_evaluation", model_id, utcnow(), json.dumps(report)))
    return report


@app.post("/api/v1/models/rollback")
def rollback_model():
    previous = db.one("SELECT * FROM models WHERE status='approved' ORDER BY created_at DESC LIMIT 1")
    current = active_model()
    if not previous:
        raise HTTPException(409, "No previously active approved model is available for rollback.")
    try:
        load_estimator(previous)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(409, f"Rollback model is unavailable: {exc}") from exc
    with db.connect() as connection:
        connection.execute("UPDATE models SET status='approved' WHERE id=?", (current["id"],))
        connection.execute("UPDATE models SET status='active' WHERE id=?", (previous["id"],))
        connection.execute("INSERT INTO audit_events (action, model_id, created_at, details) VALUES (?, ?, ?, ?)",
                           ("rollback", previous["id"], utcnow(), json.dumps({"from": current["id"]})))
    return {"id": previous["id"], "status": "active", "restored_from": current["id"]}


@app.get("/api/v1/alerts")
def alerts():
    items = db.rows("alerts", 100)
    return {"items": items, "thresholds": ALERT_THRESHOLDS}


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    alert = db.one("SELECT * FROM alerts WHERE id=?", (alert_id,))
    if not alert:
        raise HTTPException(404, "Alert was not found.")
    if alert["status"] == "open":
        db.execute("UPDATE alerts SET status='acknowledged' WHERE id=?", (alert_id,))
        db.execute("INSERT INTO audit_events (action, model_id, created_at, details) VALUES (?, NULL, ?, ?)",
                   ("acknowledge_alert", utcnow(), json.dumps({"alert_id": alert_id})))
    return {"id": alert_id, "status": "acknowledged"}


@app.post("/api/v1/replay/sessions", status_code=201)
def start_replay(request: ReplayRequest):
    engine = resolve_engine(request.engine_id)
    replay_id = f"replay-{uuid.uuid4().hex[:8]}"
    with _lock:
        _replays[replay_id] = {"id": replay_id, "engine_id": engine["id"], "position": 0, "speed": request.speed,
                               "status": "running", "history": engine["history"], "created_at": utcnow(), "latest": None}
        persist_replay(_replays[replay_id])
    return replay_status(replay_id)


def persist_replay(session: dict) -> None:
    db.execute("INSERT INTO replay_sessions (id, engine_id, position, speed, status, history, latest, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
               "ON CONFLICT(id) DO UPDATE SET position=excluded.position, speed=excluded.speed, status=excluded.status, history=excluded.history, latest=excluded.latest",
               (session["id"], session["engine_id"], session["position"], session["speed"], session["status"],
                json.dumps(session["history"]), json.dumps(session["latest"]) if session["latest"] else None, session["created_at"]))


def replay_status(replay_id: str) -> dict:
    session = _replays.get(replay_id)
    if not session:
        raise HTTPException(404, "Replay session was not found.")
    return {key: value for key, value in session.items() if key != "history"}


@app.get("/api/v1/replay/sessions")
def replay_sessions():
    items = sorted((replay_status(replay_id) for replay_id in _replays), key=lambda item: item["created_at"], reverse=True)
    return {"items": items[:20]}


@app.get("/api/v1/replay/{replay_id}/status")
def replay_get_status(replay_id: str):
    return replay_status(replay_id)


@app.post("/api/v1/replay/{replay_id}/{action}")
def replay_action(replay_id: str, action: str):
    if action not in {"pause", "resume", "reset", "step"}:
        raise HTTPException(404, "Replay action was not found.")
    session = _replays.get(replay_id)
    if not session:
        raise HTTPException(404, "Replay session was not found.")
    with _lock:
        if action == "pause":
            session["status"] = "paused"
        elif action == "resume":
            session["status"] = "running"
        elif action == "reset":
            session["position"], session["status"], session["latest"] = 0, "running", None
        elif action == "step" and session["status"] == "running":
            if session["position"] < len(session["history"]):
                next_position = session["position"] + 1
                sequence = session["history"][:next_position]
                model = active_model()
                estimate = predict(model, sequence)
                observation = {"cycle": sequence[-1]["cycle"], "sensor_2": sequence[-1]["sensor_2"],
                               "sensor_3": sequence[-1]["sensor_3"], "sensor_7": sequence[-1]["sensor_7"],
                               "observed": True, "rul": round(estimate, 1), "severity": level(estimate)}
                session["position"] = next_position
                session["latest"] = observation
                register_prediction(session["engine_id"], observation["cycle"], estimate, model["id"])
            else:
                session["status"] = "completed"
        persist_replay(session)
    return replay_status(replay_id)


@app.get("/api/v1/monitoring/drift")
def drift():
    baseline = current_dataset()["train_records"]
    if not baseline:
        raise HTTPException(409, "No baseline observations are available.")
    reference = np.asarray([[row[name] for name in SENSORS] for row in baseline[-min(2000, len(baseline)):]], dtype=float)
    engine = current_dataset()["engines"][0]
    current = np.asarray([[row[name] for row in engine["history"][-12:]] for name in SENSORS], dtype=float).T
    base_mean, base_std = reference.mean(axis=0), reference.std(axis=0)
    override = app.state.drift_override
    if override:
        sensor_index = SENSORS.index(override["sensor"])
        current[:, sensor_index] += override["sigma"] * max(base_std[sensor_index], 1e-6)
    shift = np.abs(current.mean(axis=0) - base_mean) / np.maximum(base_std, 1e-6)
    items = [{"sensor": name, "shift_sigma": round(float(value), 2), "status": "shift" if value >= 3 else "stable"}
             for name, value in sorted(zip(SENSORS, shift), key=lambda pair: pair[1], reverse=True)]
    score = round(float(np.mean(shift >= 3)), 3)
    return {"window": "last 12 observations", "baseline": "training sensor distribution", "score": score,
            "status": "investigate" if float(np.max(shift)) >= 3 else "stable", "items": items[:8],
            "simulation": override,
            "note": "Statistical distribution shift is a review signal, not evidence of failure or a promotion trigger."}


@app.post("/api/v1/monitoring/drift/simulate")
def simulate_drift(request: DriftSimulationRequest):
    app.state.drift_override = {"sensor": request.sensor, "sigma": request.sigma} if request.enabled else None
    return {"simulation": app.state.drift_override, "source_data_changed": False}


@app.get("/api/v1/explain/{engine_id}")
def explain(engine_id: str):
    engine, model = resolve_engine(engine_id), active_model()
    vector = np.asarray(feature_vector(engine["history"][-1], engine["history"][:-1]), dtype=np.float32)
    estimator = load_estimator(model)
    if model["algorithm"] == "LSTM":
        import torch
        offset = max(0, len(engine["history"]) - 30)
        sequence = [feature_vector(row, engine["history"][max(0, index - 4):index])
                    for index, row in enumerate(engine["history"][offset:], offset)]
        sequence = [sequence[0]] * (30 - len(sequence)) + sequence
        raw = np.asarray(sequence, dtype=np.float32)
        mean, std = estimator["mean"], estimator["std"]
        with torch.no_grad():
            baseline = float(estimator["estimator"](torch.tensor([(raw - mean) / std], dtype=torch.float32)).item())
            sensitivities = []
            for index, sensor in enumerate(SENSORS):
                changed = raw.copy()
                feature_indices = [3 + index, 25 + index * 2, 26 + index * 2]
                changed[:, feature_indices] = mean[feature_indices]
                value = float(estimator["estimator"](torch.tensor([(changed - mean) / std], dtype=torch.float32)).item())
                sensitivities.append({"sensor": sensor, "sensitivity": round(abs(baseline - value), 3)})
        sensitivities.sort(key=lambda item: item["sensitivity"], reverse=True)
    elif isinstance(estimator, dict):
        medians = np.asarray(estimator["medians"], dtype=np.float32)
        estimator = estimator["estimator"]
        predicted = float(estimator.predict([vector])[0])
        sensitivities = []
        for index, sensor in enumerate(SENSORS):
            changed = vector.copy()
            changed[3 + index] = medians[3 + index]
            changed[25 + index * 2:27 + index * 2] = medians[25 + index * 2:27 + index * 2]
            contribution = abs(predicted - float(estimator.predict([changed])[0]))
            sensitivities.append({"sensor": sensor, "sensitivity": round(contribution, 3)})
        sensitivities.sort(key=lambda item: item["sensitivity"], reverse=True)
    else:
        sensitivities = [{"sensor": sensor, "sensitivity": 0.0} for sensor in SENSORS[:6]]
    return {"engine": engine["id"], "model": model["id"], "type": "local feature sensitivity",
            "items": sensitivities[:8], "note": "Perturbation sensitivity is not causal attribution and is not a confidence score."}


@app.get("/api/v1/audit")
def audit():
    return {"items": db.rows("audit_events", 50)}


FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(FRONTEND_DIST / "index.html")

