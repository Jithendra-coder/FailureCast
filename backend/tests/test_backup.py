import io
import sqlite3
import tarfile

import pytest

from backend.app.backup import MANIFEST, create_backup, restore_backup, verify_backup


def test_backup_restores_data_and_a_consistent_sqlite_snapshot(tmp_path):
    source = tmp_path / "source"
    (source / "data" / "raw").mkdir(parents=True)
    (source / "artifacts" / "models").mkdir(parents=True)
    (source / "data" / "raw" / "source.txt").write_text("simulated source", encoding="utf-8")
    (source / "artifacts" / "models" / "model.bin").write_bytes(b"model artifact")
    database = source / "artifacts" / "failurecast.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('saved')")

    archive = tmp_path / "backups" / "failurecast.tar.gz"
    manifest = create_backup(source, archive)
    restored = tmp_path / "restored"
    restore_backup(archive, restored)

    assert verify_backup(archive)["files"] == manifest["files"]
    assert (restored / "data" / "raw" / "source.txt").read_text(encoding="utf-8") == "simulated source"
    with sqlite3.connect(restored / "artifacts" / "failurecast.sqlite3") as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("saved",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_restore_rejects_path_traversal_before_writing(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("../outside.txt")
        member.size = 1
        bundle.addfile(member, io.BytesIO(b"x"))
        manifest = tarfile.TarInfo(MANIFEST)
        manifest.size = 2
        bundle.addfile(manifest, io.BytesIO(b"{}"))

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="Unsafe or unsupported"):
        restore_backup(archive, destination)

    assert not destination.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_restore_creates_empty_compose_mount_roots(tmp_path):
    source = tmp_path / "source"
    (source / "data").mkdir(parents=True)
    (source / "artifacts").mkdir()
    archive = tmp_path / "empty.tar.gz"
    create_backup(source, archive)

    restored = tmp_path / "restored"
    restore_backup(archive, restored)

    assert (restored / "data").is_dir()
    assert (restored / "artifacts").is_dir()
