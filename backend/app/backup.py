from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

MANIFEST = "FAILURECAST-MANIFEST.json"
BACKUP_ROOTS = ("data", "artifacts")
SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3")
MAX_BACKUP_FILES = 100_000


def _files(root: Path):
    for name in BACKUP_ROOTS:
        base = root / name
        if base.is_symlink():
            raise ValueError(f"Refusing symlink in backup source: {base}")
        if not base.exists():
            continue
        for current, directories, filenames in os.walk(base, followlinks=False):
            for directory in directories:
                if (Path(current) / directory).is_symlink():
                    raise ValueError("Backup source contains a symlink.")
            for filename in filenames:
                path = Path(current) / filename
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Backup source contains a non-regular file.")
                relative = path.relative_to(root).as_posix()
                if not filename.endswith(("-wal", "-shm")):
                    yield relative, path


def _sqlite_ok(path: Path) -> None:
    try:
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise ValueError(f"SQLite integrity check failed for {path.name}: {exc}") from exc
    if not result or result[0] != "ok":
        raise ValueError(f"SQLite integrity check failed for {path.name}.")


def _sha256(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def create_backup(source: Path, archive: Path) -> dict:
    source, archive = source.resolve(), archive.resolve()
    if not source.is_dir():
        raise ValueError("Backup source must be an existing application directory.")
    if archive.is_relative_to(source):
        raise ValueError("Backup archives must be stored outside the application root.")
    if archive.exists() or archive.is_symlink():
        raise FileExistsError(f"Backup archive already exists: {archive}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = list(_files(source))
    with tempfile.TemporaryDirectory(prefix="failurecast-backup-") as temporary:
        snapshot = Path(temporary)
        entries = []
        for relative, path in files:
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.name.lower().endswith(SQLITE_SUFFIXES):
                original = copy = None
                try:
                    original = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15)
                    copy = sqlite3.connect(target)
                    original.backup(copy)
                except sqlite3.Error as exc:
                    raise ValueError(f"Could not snapshot SQLite database {relative}: {exc}") from exc
                finally:
                    if original:
                        original.close()
                    if copy:
                        copy.close()
                _sqlite_ok(target)
            else:
                shutil.copyfile(path, target)
            digest, size = _sha256(target)
            entries.append({"path": relative, "size": size, "sha256": digest})

        manifest = {"format_version": 1, "files": entries}
        temporary_archive = archive.with_name(f".{archive.name}.tmp")
        if temporary_archive.exists() or temporary_archive.is_symlink():
            raise FileExistsError(f"Temporary backup path already exists: {temporary_archive}")
        try:
            with tarfile.open(temporary_archive, "w:gz") as bundle:
                for entry in entries:
                    bundle.add(snapshot / entry["path"], arcname=entry["path"], recursive=False)
                encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
                info = tarfile.TarInfo(MANIFEST)
                info.size = len(encoded)
                info.mode = 0o600
                bundle.addfile(info, io.BytesIO(encoded))
            temporary_archive.chmod(0o600)
            verify_backup(temporary_archive)
            temporary_archive.rename(archive)
        except Exception:
            temporary_archive.unlink(missing_ok=True)
            raise
    return manifest


def _archive_manifest(bundle: tarfile.TarFile) -> tuple[dict, dict[str, tarfile.TarInfo]]:
    members = bundle.getmembers()
    if len(members) > MAX_BACKUP_FILES + 1:
        raise ValueError("Backup contains too many archive entries.")
    by_name = {}
    for member in members:
        name = member.name
        if name in by_name:
            raise ValueError("Backup archive contains duplicate paths.")
        if name != MANIFEST:
            path = PurePosixPath(name)
            if ("\\" in name or ":" in name or path.is_absolute() or len(path.parts) < 2 or
                    path.parts[0] not in BACKUP_ROOTS or any(part in {"", ".", ".."} for part in path.parts) or
                    not member.isfile() or member.size < 0):
                raise ValueError(f"Unsafe or unsupported backup entry: {name}")
        elif not member.isfile() or member.size > 4 * 1024 * 1024:
            raise ValueError("Backup manifest is not a supported regular file.")
        by_name[name] = member
    manifest_member = by_name.get(MANIFEST)
    if not manifest_member:
        raise ValueError("Backup manifest is missing.")
    stream = bundle.extractfile(manifest_member)
    if stream is None:
        raise ValueError("Backup manifest cannot be read.")
    try:
        manifest = json.loads(stream.read())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Backup manifest is invalid.") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("Backup format version is unsupported.")
    if len(manifest["files"]) > MAX_BACKUP_FILES:
        raise ValueError("Backup contains too many files.")
    expected = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Backup manifest contains an invalid file entry.")
        name = entry["path"]
        path = PurePosixPath(name)
        if (name == MANIFEST or "\\" in name or ":" in name or path.is_absolute() or len(path.parts) < 2 or
                path.parts[0] not in BACKUP_ROOTS or any(part in {"", ".", ".."} for part in path.parts) or
                name in expected or not isinstance(entry.get("size"), int) or entry["size"] < 0 or
                not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64 or
                any(character not in "0123456789abcdef" for character in entry["sha256"])):
            raise ValueError("Backup manifest contains an unsafe or invalid file entry.")
        expected[name] = entry
    if set(by_name) - {MANIFEST} != set(expected):
        raise ValueError("Backup archive contents do not match the manifest.")
    return manifest, {name: member for name, member in by_name.items() if name != MANIFEST}


def verify_backup(archive: Path) -> dict:
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            manifest, members = _archive_manifest(bundle)
            expected = {entry["path"]: entry for entry in manifest["files"]}
            for name, member in members.items():
                digest = hashlib.sha256()
                size = 0
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError(f"Backup entry cannot be read: {name}")
                with source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                if size != expected[name]["size"] or digest.hexdigest() != expected[name]["sha256"]:
                    raise ValueError(f"Backup checksum mismatch: {name}")
            return manifest
    except (tarfile.TarError, OSError) as exc:
        raise ValueError(f"Could not read backup archive: {exc}") from exc


def restore_backup(archive: Path, destination: Path) -> dict:
    if destination.is_symlink():
        raise ValueError("Restore destination cannot be a symlink.")
    archive, destination = archive.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError("Restore destination must not already exist.")
    manifest = verify_backup(archive)
    destination.parent.mkdir(parents=True, exist_ok=True)
    required_space = sum(entry["size"] for entry in manifest["files"])
    if required_space > shutil.disk_usage(destination.parent).free:
        raise OSError("Restore destination does not have enough free space.")
    staging = destination.with_name(f".{destination.name}.restore")
    if staging.exists():
        raise FileExistsError(f"Restore staging path already exists: {staging}")
    staging.mkdir(mode=0o700)
    try:
        for name in BACKUP_ROOTS:
            (staging / name).mkdir()
        entries = {entry["path"]: entry for entry in manifest["files"]}
        with tarfile.open(archive, "r:gz") as bundle:
            _, members = _archive_manifest(bundle)
            for name, member in members.items():
                target = staging.joinpath(*PurePosixPath(name).parts)
                if not target.resolve().is_relative_to(staging.resolve()):
                    raise ValueError(f"Backup path escapes restore destination: {name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError(f"Backup entry cannot be read: {name}")
                digest = hashlib.sha256()
                size = 0
                with source, target.open("xb") as output:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                target.chmod(0o600)
                entry = entries[name]
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(f"Restored file checksum mismatch: {name}")
        for relative, _source in _files(staging):
            path = staging / relative
            if path.name.lower().endswith(SQLITE_SUFFIXES):
                _sqlite_ok(path)
        staging.rename(destination)
        return manifest
    except Exception:
        shutil.rmtree(staging)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(prog="failurecast-backup", description="Create and verify safe FailureCast data backups.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create an archive of data/ and artifacts/.")
    create.add_argument("--source", type=Path, default=Path.cwd())
    create.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="Verify archive paths and SHA-256 checksums.")
    verify.add_argument("--archive", type=Path, required=True)
    restore = commands.add_parser("restore", help="Restore to a new, empty path after checksum and SQLite checks.")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_backup(args.source, args.output)
        elif args.command == "verify":
            result = verify_backup(args.archive)
        else:
            result = restore_backup(args.archive, args.destination)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "ok", "files": len(result["files"]), "destination": str(args.output if args.command == "create" else args.destination if args.command == "restore" else args.archive)}))


if __name__ == "__main__":
    main()
