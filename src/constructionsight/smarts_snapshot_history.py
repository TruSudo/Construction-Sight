"""Private, append-only SMARTS facility CSV snapshot and change history.

An explicit offline operator action retains original CSV bytes, source-scoped
row hashes, and a deterministic candidate-change ledger in one SQLite
transaction. No network acquisition, county completeness assertion, parcel
matching, lead promotion, or unattended scheduling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from constructionsight.smarts_evidence_ledger import _safe_database_path
from constructionsight.smarts_snapshot_diff import (
    COUNTIES,
    MAX_CSV_BYTES,
    FacilitySnapshot,
    SmartsSnapshotError,
    parse_facility_snapshot_bytes,
    reconcile_snapshots,
)

_APPLICATION_ID = 0x43535348  # CSSH
_VERSION = 1
_TABLES = frozenset({"snapshot_blobs", "snapshot_captures", "snapshot_rows", "snapshot_events"})
_COLUMNS = {
    "snapshot_blobs": ("sha256", "raw_csv"),
    "snapshot_captures": (
        "id", "county", "recorded_at", "reported_publication_at", "file_sha256",
        "columns_json", "total_rows", "selected_rows", "previous_id",
    ),
    "snapshot_rows": ("snapshot_id", "source_key", "row_sha256", "app_id", "wdid"),
    "snapshot_events": (
        "snapshot_id", "source_key", "outcome", "previous_sha256", "current_sha256",
    ),
}


class SmartsHistoryError(ValueError):
    """An evidence file, ledger, schema, or transition is not trustworthy."""


@dataclass(frozen=True)
class SnapshotHistoryReceipt:
    snapshot_id: int
    county: str
    file_sha256: str
    baseline: bool
    replayed: bool
    new: int
    changed: int
    unchanged: int
    missing_from_new: int
    source_publication_verified: bool = False
    county_coverage_verified: bool = False
    commercial_actions_authorized: bool = False


def _database(path: Path, *, read_only: bool) -> sqlite3.Connection:
    try:
        db = _safe_database_path(path, create=not read_only)
    except (OSError, ValueError) as exc:
        raise SmartsHistoryError("Private snapshot ledger path is unavailable") from exc
    try:
        if read_only:
            connection = sqlite3.connect(
                f"file:{quote(str(db))}?mode=ro", uri=True, timeout=10,
                isolation_level=None,
            )
        else:
            connection = sqlite3.connect(str(db), timeout=10, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA foreign_keys=ON")
            if read_only:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
            else:
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("BEGIN IMMEDIATE")
            app_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            found = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not read_only and not found and app_id == 0 and version == 0:
                for sql in (
                    "CREATE TABLE snapshot_blobs ("
                    "sha256 TEXT PRIMARY KEY, raw_csv BLOB NOT NULL)",
                    "CREATE TABLE snapshot_captures ("
                    "id INTEGER PRIMARY KEY, county TEXT NOT NULL, recorded_at TEXT NOT NULL, "
                    "reported_publication_at TEXT, file_sha256 TEXT NOT NULL "
                    "REFERENCES snapshot_blobs(sha256), columns_json TEXT NOT NULL, "
                    "total_rows INTEGER NOT NULL, selected_rows INTEGER NOT NULL, "
                    "previous_id INTEGER REFERENCES snapshot_captures(id))",
                    "CREATE TABLE snapshot_rows ("
                    "snapshot_id INTEGER NOT NULL REFERENCES snapshot_captures(id), "
                    "source_key TEXT NOT NULL, row_sha256 TEXT NOT NULL, "
                    "app_id TEXT, wdid TEXT, PRIMARY KEY(snapshot_id,source_key))",
                    "CREATE TABLE snapshot_events ("
                    "snapshot_id INTEGER NOT NULL REFERENCES snapshot_captures(id), "
                    "source_key TEXT NOT NULL, "
                    "outcome TEXT NOT NULL CHECK(outcome IN "
                    "('new','changed','missing_from_new')), "
                    "previous_sha256 TEXT, current_sha256 TEXT, "
                    "PRIMARY KEY(snapshot_id,source_key))",
                ):
                    connection.execute(sql)
                for name in sorted(_TABLES):
                    for action in ("UPDATE", "DELETE"):
                        connection.execute(
                            f"CREATE TRIGGER {name}_no_{action.lower()} "
                            f"BEFORE {action} ON {name} "
                            "BEGIN SELECT RAISE(ABORT, 'immutable'); END"
                        )
                connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={_VERSION}")
                # Schema creation must survive a later aborted first capture.
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
            elif app_id != _APPLICATION_ID or version != _VERSION or found != _TABLES:
                raise SmartsHistoryError("Incompatible or ungoverned snapshot ledger")
            for table, columns in _COLUMNS.items():
                observed = tuple(
                    x[1] for x in connection.execute(f"PRAGMA table_info({table})")
                )
                if observed != columns:
                    raise SmartsHistoryError("Snapshot ledger schema drift")
            triggers = {
                x[0] for x in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
            expected = {
                f"{name}_no_{action.lower()}"
                for name in _TABLES for action in ("UPDATE", "DELETE")
            }
            if triggers != expected:
                raise SmartsHistoryError("Snapshot ledger immutability triggers differ")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise SmartsHistoryError("Snapshot ledger integrity check failed")
            return connection
        except Exception:
            connection.close()
            raise
    except sqlite3.Error as exc:
        raise SmartsHistoryError("Private snapshot ledger could not be opened") from exc


def _original_csv(path: Path) -> bytes:
    """Allow only an owner-controlled regular CSV, never a symlink or shared file."""
    target = Path(path).absolute()
    try:
        parent = target.parent.lstat()
        info = target.lstat()
        if (
            target.suffix.lower() != ".csv"
            or not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o077
            or not 0 < info.st_size <= MAX_CSV_BYTES
        ):
            raise SmartsHistoryError("Original CSV must be an owner-only regular file")
        body = target.read_bytes()
    except OSError as exc:
        raise SmartsHistoryError("Original source CSV cannot be read") from exc
    if len(body) != info.st_size:
        raise SmartsHistoryError("Original source CSV changed during read")
    return body


def _published_at(raw: str | None) -> str | None:
    if raw is None:
        return None
    if len(raw) > 40:
        raise SmartsHistoryError("Invalid reported publication timestamp")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SmartsHistoryError("Invalid reported publication timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise SmartsHistoryError("Reported publication timestamp requires an offset")
    return dt.isoformat()


def _audit(
    connection: sqlite3.Connection,
) -> tuple[dict[str, tuple[int, FacilitySnapshot]], dict[str, int]]:
    """Independently replay every retained raw file and candidate change event."""
    previous: dict[str, tuple[int, FacilitySnapshot]] = {}
    counts = {"snapshots": 0, "source_rows": 0, "change_candidates": 0, "blobs": 0}
    used_blobs: set[str] = set()
    for (
        snapshot_id, county, recorded_at, published_at, file_sha, columns_json,
        total_rows, selected_rows, previous_id, raw_csv,
    ) in connection.execute(
        "SELECT s.id,s.county,s.recorded_at,s.reported_publication_at,s.file_sha256,"
        "s.columns_json,s.total_rows,s.selected_rows,s.previous_id,b.raw_csv "
        "FROM snapshot_captures s LEFT JOIN snapshot_blobs b ON s.file_sha256=b.sha256 "
        "ORDER BY s.id"
    ):
        if county not in COUNTIES or type(raw_csv) is not bytes:
            raise SmartsHistoryError("Missing or unsupported captured source bytes")
        if not isinstance(recorded_at, str):
            raise SmartsHistoryError("Invalid source capture timestamp")
        try:
            recorded = datetime.fromisoformat(recorded_at)
            if recorded.tzinfo is None or recorded.utcoffset() is None:
                raise ValueError("missing timezone")
            if published_at is not None and _published_at(published_at) != published_at:
                raise ValueError("inconsistent publication timestamp")
        except (ValueError, TypeError) as exc:
            raise SmartsHistoryError("Invalid source capture timestamp") from exc
        if hashlib.sha256(raw_csv).hexdigest() != file_sha:
            raise SmartsHistoryError("Original source bytes have changed")
        try:
            snapshot = parse_facility_snapshot_bytes(raw_csv, county=county)
        except SmartsSnapshotError as exc:
            raise SmartsHistoryError("Retained source file cannot be parsed") from exc
        if (
            snapshot.file_sha256 != file_sha
            or json.dumps(snapshot.column_names, separators=(",", ":")) != columns_json
            or snapshot.total_rows != total_rows
            or snapshot.selected_rows != selected_rows
        ):
            raise SmartsHistoryError("Snapshot metadata does not match original source")
        stored_rows = {
            key: (digest, app_id, wdid)
            for key, digest, app_id, wdid in connection.execute(
                "SELECT source_key,row_sha256,app_id,wdid FROM snapshot_rows "
                "WHERE snapshot_id=?", (snapshot_id,),
            )
        }
        expected_rows = {
            key: (row.row_sha256, row.app_id, row.wdid)
            for key, row in snapshot.source_rows.items()
        }
        if stored_rows != expected_rows:
            raise SmartsHistoryError("Retained source row hash or identity differs")
        prior = previous.get(county)
        if previous_id != (prior[0] if prior else None):
            raise SmartsHistoryError("Snapshot county chain is incomplete")
        expected_events = (
            {
                event.source_key: (
                    event.outcome, event.previous_row_sha256, event.current_row_sha256
                )
                for event in reconcile_snapshots(prior[1], snapshot)
                if event.outcome != "unchanged"
            }
            if prior else {}
        )
        observed_events = {
            key: (outcome, old, new)
            for key, outcome, old, new in connection.execute(
                "SELECT source_key,outcome,previous_sha256,current_sha256 "
                "FROM snapshot_events WHERE snapshot_id=?", (snapshot_id,),
            )
        }
        if expected_events != observed_events:
            raise SmartsHistoryError("Snapshot transition history is incomplete or altered")
        counts["snapshots"] += 1
        counts["source_rows"] += len(expected_rows)
        counts["change_candidates"] += len(expected_events)
        used_blobs.add(file_sha)
        previous[county] = (snapshot_id, snapshot)
    stored_blobs = {
        row[0] for row in connection.execute("SELECT sha256 FROM snapshot_blobs")
    }
    if stored_blobs != used_blobs:
        raise SmartsHistoryError("Snapshot source bytes are orphaned or incomplete")
    counts["blobs"] = len(stored_blobs)
    return previous, counts


def verify_snapshot_history(path: Path) -> dict[str, int]:
    """Audit a pre-existing private journal without creating or modifying it."""
    connection = _database(path, read_only=True)
    try:
        _, counts = _audit(connection)
        connection.rollback()
        return counts
    finally:
        connection.close()


def append_snapshot(
    *, ledger_path: Path, csv_path: Path, county: str,
    reported_publication_at: str | None = None,
) -> SnapshotHistoryReceipt:
    """Atomically retain one complete original CSV and county-scoped diff."""
    if county not in COUNTIES:
        raise SmartsHistoryError("Unapproved county")
    publication = _published_at(reported_publication_at)
    body = _original_csv(csv_path)
    try:
        current = parse_facility_snapshot_bytes(body, county=county)
    except SmartsSnapshotError as exc:
        raise SmartsHistoryError("Original CSV failed strict facility validation") from exc
    connection = _database(ledger_path, read_only=False)
    try:
        previous, _ = _audit(connection)
        prior = previous.get(county)
        if prior and prior[1].file_sha256 == current.file_sha256:
            connection.rollback()
            return SnapshotHistoryReceipt(
                prior[0], county, current.file_sha256, False, True, 0, 0, 0, 0
            )
        events = reconcile_snapshots(prior[1], current) if prior else ()
        counts = {
            kind: sum(event.outcome == kind for event in events)
            for kind in ("new", "changed", "unchanged", "missing_from_new")
        }
        existing = connection.execute(
            "SELECT raw_csv FROM snapshot_blobs WHERE sha256=?", (current.file_sha256,)
        ).fetchone()
        if existing is not None and existing[0] != body:
            raise SmartsHistoryError("Captured source hash collision or evidence alteration")
        if existing is None:
            connection.execute(
                "INSERT INTO snapshot_blobs VALUES (?,?)", (current.file_sha256, body)
            )
        cursor = connection.execute(
            "INSERT INTO snapshot_captures "
            "(county,recorded_at,reported_publication_at,file_sha256,columns_json,"
            "total_rows,selected_rows,previous_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                county, datetime.now(UTC).isoformat(), publication, current.file_sha256,
                json.dumps(current.column_names, separators=(",", ":")),
                current.total_rows, current.selected_rows, prior[0] if prior else None,
            ),
        )
        snapshot_id = cursor.lastrowid
        if not isinstance(snapshot_id, int):
            raise SmartsHistoryError("Snapshot did not receive a durable ID")
        connection.executemany(
            "INSERT INTO snapshot_rows VALUES (?,?,?,?,?)",
            (
                (snapshot_id, key, row.row_sha256, row.app_id, row.wdid)
                for key, row in sorted(current.source_rows.items())
            ),
        )
        connection.executemany(
            "INSERT INTO snapshot_events VALUES (?,?,?,?,?)",
            (
                (
                    snapshot_id, event.source_key, event.outcome,
                    event.previous_row_sha256, event.current_row_sha256,
                )
                for event in events if event.outcome != "unchanged"
            ),
        )
        connection.commit()
        return SnapshotHistoryReceipt(
            snapshot_id, county, current.file_sha256, prior is None, False,
            counts["new"], counts["changed"], counts["unchanged"],
            counts["missing_from_new"],
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator-authorized offline SMARTS CSV evidence history"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--record", action="store_true")
    modes.add_argument("--verify", action="store_true")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--county", choices=COUNTIES)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--reported-publication-at")
    parser.add_argument("--retain-evidence", action="store_true")
    args = parser.parse_args(argv)
    if args.record and (
        not args.retain_evidence or args.county is None or args.csv is None
    ):
        parser.error("Recording requires --retain-evidence, --county and --csv")
    if args.verify and (
        args.retain_evidence or args.county is not None or args.csv is not None
        or args.reported_publication_at is not None
    ):
        parser.error("Verification takes only --verify and --ledger")
    try:
        if args.record:
            result = append_snapshot(
                ledger_path=args.ledger, csv_path=args.csv, county=args.county,
                reported_publication_at=args.reported_publication_at,
            )
            response: dict[str, object] = {
                "ok": True, "receipt": asdict(result), "source_rows_exposed": False,
                "source_completeness_verified": False,
            }
        else:
            response = {
                "ok": True, "integrity": verify_snapshot_history(args.ledger),
                "source_rows_exposed": False, "source_completeness_verified": False,
            }
    except (SmartsHistoryError, SmartsSnapshotError, sqlite3.Error, OSError):
        print(json.dumps({"ok": False, "error": "SMARTS snapshot history unavailable or invalid"}))
        return 1
    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
