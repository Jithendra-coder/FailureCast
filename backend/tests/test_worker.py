from backend.app import db, worker


def test_only_one_worker_can_hold_the_local_queue_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "failurecast.sqlite3")
    first = worker.try_worker_lock()
    assert first is not None
    try:
        assert worker.try_worker_lock() is None
    finally:
        first.close()
    replacement = worker.try_worker_lock()
    assert replacement is not None
    replacement.close()
