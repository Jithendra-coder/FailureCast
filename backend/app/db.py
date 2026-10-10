from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("FAILURECAST_DB", ROOT / "artifacts" / "failurecast.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect() as db:
        # shortcut: SQLite WAL is single-host storage, migrate before multi-host deployment.
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, subset TEXT NOT NULL, source TEXT NOT NULL, imported_at TEXT NOT NULL,
            checksum TEXT NOT NULL, quality TEXT NOT NULL, raw_dir TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY, algorithm TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
            metrics TEXT NOT NULL, artifact_path TEXT, dataset_id TEXT, parent_id TEXT, training_job_id TEXT
        );
        CREATE TABLE IF NOT EXISTS training_jobs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, algorithm TEXT NOT NULL, created_at TEXT NOT NULL,
            finished_at TEXT, result TEXT, error TEXT, dataset_id TEXT, started_at TEXT, worker_id TEXT
        );
        CREATE TABLE IF NOT EXISTS predictions (
            id TEXT PRIMARY KEY, engine_id TEXT NOT NULL, model_id TEXT NOT NULL, cycle INTEGER NOT NULL,
            rul REAL NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY, engine_id TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
            predicted_rul REAL NOT NULL, cycle INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, model_id TEXT, created_at TEXT NOT NULL, details TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS replay_sessions (
            id TEXT PRIMARY KEY, engine_id TEXT NOT NULL, position INTEGER NOT NULL, speed REAL NOT NULL,
            status TEXT NOT NULL, history TEXT NOT NULL, latest TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_attempts (
            client_key TEXT NOT NULL, attempted_at INTEGER NOT NULL
        );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(training_jobs)")}
        for name in ("dataset_id", "started_at", "worker_id"):
            if name not in columns:
                db.execute(f"ALTER TABLE training_jobs ADD COLUMN {name} TEXT")
        model_columns = {row[1] for row in db.execute("PRAGMA table_info(models)")}
        if "training_job_id" not in model_columns:
            db.execute("ALTER TABLE models ADD COLUMN training_job_id TEXT")
        db.execute("UPDATE training_jobs SET status='failed', finished_at=COALESCE(finished_at, datetime('now')), error='Interrupted job requires resubmission.' WHERE status IN ('queued','running') AND dataset_id IS NULL")
        db.execute("UPDATE models SET status='approved' WHERE status='active' AND id != (SELECT id FROM models WHERE status='active' ORDER BY created_at DESC, id DESC LIMIT 1)")
        db.executescript("""
        CREATE INDEX IF NOT EXISTS idx_predictions_engine_cycle ON predictions(engine_id, cycle);
        CREATE INDEX IF NOT EXISTS idx_alerts_status_created ON alerts(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_training_jobs_status_created ON training_jobs(status, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_model ON models(status) WHERE status='active';
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_training_job ON training_jobs ((1)) WHERE status IN ('queued','running');
        CREATE UNIQUE INDEX IF NOT EXISTS one_candidate_per_training_job ON models(training_job_id) WHERE training_job_id IS NOT NULL;
        """)


def rows(table: str, limit: int = 100) -> list[dict]:
    if table not in {"datasets", "models", "training_jobs", "predictions", "alerts", "audit_events", "replay_sessions"}:
        raise ValueError("Unsupported table")
    with connect() as db:
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,))]


def execute(sql: str, values: tuple = ()) -> None:
    with connect() as db:
        db.execute(sql, values)


def one(sql: str, values: tuple = ()) -> dict | None:
    with connect() as db:
        row = db.execute(sql, values).fetchone()
        return dict(row) if row else None


def decode(row: dict | None, *fields: str) -> dict | None:
    if row:
        for field in fields:
            if row.get(field):
                row[field] = json.loads(row[field])
    return row


def consume_login_attempt(client_key: str, now: int, limit: int = 5, window: int = 900) -> bool:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM auth_attempts WHERE attempted_at < ?", (now - window,))
        count = db.execute("SELECT COUNT(*) FROM auth_attempts WHERE client_key=?", (client_key,)).fetchone()[0]
        if count >= limit:
            return False
        db.execute("INSERT INTO auth_attempts (client_key, attempted_at) VALUES (?, ?)", (client_key, now))
        return True


def clear_login_attempts(client_key: str) -> None:
    execute("DELETE FROM auth_attempts WHERE client_key=?", (client_key,))
