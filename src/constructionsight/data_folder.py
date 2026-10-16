"""Integrity-checked local data snapshots and reversible folder changes."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from constructionsight.smarts_evidence_ledger import verify_smarts_journal

MANIFEST = "backup-manifest.json"
LOCATION = ".data-location.json"
MAX_UNCOMPRESSED = 8_000_000_000


def _is_investigation_input(relative: Path) -> bool:
    """Exact-byte worker inputs use content identities rather than format extensions."""
    return (
        len(relative.parts) == 2
        and relative.parts[0] == "investigation-inputs"
        and re.fullmatch(r"[0-9a-f]{64}", relative.name) is not None
    )


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            result.update(chunk)
    return result.hexdigest()


def resolve_folder(path: Path) -> Path:
    current = path.expanduser().resolve()
    seen = set()
    for _ in range(32):
        if current in seen:
            raise ValueError("Data-folder redirection cycle")
        seen.add(current)
        pointer = current / LOCATION
        if not pointer.exists():
            return current
        target = json.loads(pointer.read_text()).get("directory")
        if not isinstance(target, str) or not Path(target).is_absolute():
            raise ValueError("Invalid data-folder location record")
        current = Path(target)
    raise ValueError("Too many data-folder redirects")


def point_startup(startup: Path, target: Path) -> None:
    if startup.resolve() == target.resolve():
        (startup / LOCATION).unlink(missing_ok=True)
        return
    temporary = startup / (LOCATION + ".tmp")
    temporary.write_text(json.dumps({"directory": str(target.resolve())}) + "\n")
    temporary.chmod(0o600)
    temporary.replace(startup / LOCATION)


def snapshot_files(directory: Path, target: Path) -> dict[str, dict[str, Any]]:
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("Data snapshots do not follow symbolic links")
        if not path.is_file() or (
            path.suffix not in (".json", ".sqlite3", ".pmtiles")
            and not _is_investigation_input(relative)
        ):
            continue
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.suffix == ".sqlite3":
            with (
                sqlite3.connect(f"file:{path}?mode=ro", uri=True) as original,
                sqlite3.connect(dest) as copied,
            ):
                original.backup(copied)
        else:
            shutil.copyfile(path, dest)
        dest.chmod(0o600)
        files[relative.as_posix()] = {"sha256": digest(dest), "size": dest.stat().st_size}
    # A worker retains its immutable input before committing the job. Refresh the
    # input listing after the database snapshots so a concurrently queued job
    # cannot be backed up without bytes created after the initial rglob listing.
    inputs = directory / "investigation-inputs"
    if inputs.is_symlink():
        raise ValueError("Data snapshots do not follow symbolic links")
    for path in sorted(inputs.glob("*")):
        relative = path.relative_to(directory)
        if path.is_symlink():
            raise ValueError("Data snapshots do not follow symbolic links")
        if not _is_investigation_input(relative) or relative.as_posix() in files:
            continue
        if not path.is_file():
            raise ValueError("Retained investigation input is not a regular file")
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path, dest)
        dest.chmod(0o600)
        files[relative.as_posix()] = {"sha256": digest(dest), "size": dest.stat().st_size}
    return files


def validate_directory(directory: Path, files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sqlite_results = {}
    for name, details in files.items():
        path = directory / name
        if path.stat().st_size != details["size"] or digest(path) != details["sha256"]:
            raise ValueError("Backup integrity mismatch: " + name)
        if _is_investigation_input(Path(name)) and (
            details["sha256"] != path.name or not 0 < details["size"] <= 16 * 1024 * 1024
        ):
            raise ValueError("Retained investigation input identity mismatch: " + name)
        if path.suffix == ".json":
            json.loads(path.read_text())
        if path.suffix == ".sqlite3":
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                result = db.execute("PRAGMA integrity_check").fetchall()
                if result != [("ok",)]:
                    raise ValueError("SQLite integrity failed: " + name)
                if db.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("SQLite foreign-key integrity failed: " + name)
            sqlite_results[name] = "ok"
    journal = directory / "evidence.sqlite3"
    journal_result = verify_smarts_journal(journal, read_only=True) if journal.exists() else None
    active = directory / "active.json"
    if active.exists():
        value = json.loads(active.read_text())
        if not isinstance(value, dict) or not isinstance(value.get("rows"), list):
            raise ValueError("Backup active capture is malformed")
    return {
        "sqlite_integrity": sqlite_results,
        "journal_integrity": journal_result,
        "files_verified": len(files),
        "bytes_verified": sum(f["size"] for f in files.values()),
    }


def make_backup(directory: Path) -> bytes:
    output = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="cs-backup-") as temporary:
        root = Path(temporary)
        files = snapshot_files(directory, root)
        validate_directory(root, files)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(root / name, name)
            archive.writestr(MANIFEST, json.dumps({"version": 1, "files": files}, indent=2) + "\n")
    return output.getvalue()


def preview_restore(archive_path: Path, staging: Path) -> dict[str, Any]:
    staging.mkdir(parents=True, exist_ok=True, mode=0o700)
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Backup manifest missing or duplicate archive paths")
        if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
            raise ValueError("Backup exceeds the uncompressed size limit")
        if archive.getinfo(MANIFEST).file_size > 4_000_000:
            raise ValueError("Backup manifest exceeds size limit")
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("Unsupported backup manifest")
        files = manifest["files"]
        if set(names) != {MANIFEST, *files}:
            raise ValueError("Backup file set differs from manifest")
        for info in infos:
            if info.filename == MANIFEST:
                continue
            relative = Path(info.filename)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in info.filename
                or any(p.startswith(".") for p in relative.parts)
                or (
                    relative.suffix not in (".json", ".sqlite3", ".pmtiles")
                    and not _is_investigation_input(relative)
                )
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError("Unsafe backup path: " + info.filename)
            dest = staging / relative
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(info) as source, dest.open("wb") as target:
                shutil.copyfileobj(source, target)
            dest.chmod(0o600)
    checked = validate_directory(staging, files)
    return {**checked, "archive_sha256": digest(archive_path), "files": files, "dry_run": True}


def new_restore_path(current: Path) -> Path:
    return current.parent / (current.name + "-restored-" + uuid.uuid4().hex[:12])


def apply_restore(staging: Path, report: dict[str, Any], target: Path) -> dict[str, Any]:
    if target.exists():
        raise ValueError("Restore target must not exist")
    validate_directory(staging, report["files"])
    os.rename(staging, target)
    return {
        "directory": str(target.resolve()),
        "restored": True,
        "files_verified": report["files_verified"],
    }


def relocate(directory: Path, target: Path) -> dict[str, Any]:
    target = target.expanduser().resolve()
    if directory.resolve() == target.resolve() or target.is_relative_to(directory.resolve()):
        raise ValueError("Destination must be outside the active data folder")
    if target.exists() and any(target.iterdir()):
        raise ValueError("Destination folder must be empty")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cs-relocate-", dir=target.parent) as temporary:
        staged = Path(temporary) / "data"
        files = snapshot_files(directory, staged)
        checked = validate_directory(staged, files)
        if target.exists():
            target.rmdir()
        os.rename(staged, target)
    return {"directory": str(target.resolve()), "original_preserved": True, **checked}
