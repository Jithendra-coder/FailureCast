from __future__ import annotations

import json
import logging
import os
import socket
import time
import uuid

from . import db
from .data import generate_demo_records
from .ml import fit_candidate, load_estimator, train_lstm, utcnow

log = logging.getLogger("failurecast.worker")


def training_records(dataset_id: str) -> list[dict]:
    if dataset_id == "demo-fd001-v1":
        return generate_demo_records(40, 81)
    row = db.one("SELECT * FROM datasets WHERE id=?", (dataset_id,))
    if not row:
        raise ValueError("The dataset for this training job is no longer available.")
    from .main import load_uploaded_dataset
    return load_uploaded_dataset(row)["train_records"]


def run_once(worker_id: str) -> bool:
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM training_jobs WHERE status='queued' ORDER BY created_at, id LIMIT 1").fetchone()
        if not row:
            return False
        connection.execute("UPDATE training_jobs SET status='running', started_at=?, worker_id=? WHERE id=? AND status='queued'",
                           (utcnow(), worker_id, row["id"]))
        job = dict(row)
    try:
        existing = db.one("SELECT * FROM models WHERE training_job_id=?", (job["id"],))
        if existing:
            load_estimator(existing)
            result = {"model_id": existing["id"], "algorithm": existing["algorithm"],
                      "metrics": json.loads(existing["metrics"]), "artifact": existing["artifact_path"], "recovered": True}
        else:
            records = training_records(job["dataset_id"])
            result = train_lstm(records, job["dataset_id"], job["id"]) if job["algorithm"] == "LSTM" else fit_candidate(records, job["algorithm"], job["dataset_id"], job["id"])
        db.execute("UPDATE training_jobs SET status='completed', finished_at=?, result=?, error=NULL WHERE id=? AND status='running'",
                   (utcnow(), json.dumps(result), job["id"]))
    except Exception as exc:
        message = f"{type(exc).__name__}: {str(exc)}"[:800]
        log.exception("Training job %s failed", job["id"])
        db.execute("UPDATE training_jobs SET status='failed', finished_at=?, error=? WHERE id=? AND status='running'",
                   (utcnow(), message, job["id"]))
    return True


def try_worker_lock():
    lock = db.DB_PATH.with_name("failurecast-worker.lock").open("a+b")
    lock.seek(0, os.SEEK_END)
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    try:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except OSError:
        lock.close()
        return None


def main() -> None:
    db.init_db()
    lock = try_worker_lock()
    while lock is None:
        log.info("Another worker is active; waiting for its lock")
        time.sleep(1)
        lock = try_worker_lock()
    db.execute("UPDATE training_jobs SET status='queued', started_at=NULL, worker_id=NULL, error=NULL WHERE status='running'")
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    log.info("Training worker %s is ready", worker_id)
    interval = max(0.25, float(os.getenv("FAILURECAST_WORKER_POLL_SECONDS", "1")))
    while True:
        if not run_once(worker_id):
            time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("FAILURECAST_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
